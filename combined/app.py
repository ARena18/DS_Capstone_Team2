import sys
import os
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langchain_ollama import ChatOllama
import streamlit as st
import pandas as pd

from visualization_agent import VisualizationAgent
from planner_query_tools import *

# ── Try st_copy (optional) ────────────────────────────────────────────────────
try:
    HAS_COPY = True
except Exception:
    HAS_COPY = False

# ── Variables ─────────────────────────────────────────────────────────────────
TOOL_MAP = {tool.name.lower(): tool for tool in ALL_TOOLS}
viz_agent = VisualizationAgent()

llm = ChatOllama(model="llama3.2", temperature=0).bind_tools(ALL_TOOLS)

SYSTEM_INSTRUCTIONS = """
You are a helpful assistant who only answers about King County Metro.
If the user asks about any other transit systems (e.g. New York transit), state 'I am not authorized to provide information not pertaining to King County Metro.'
Respond 'I am not authorized to suggest updates, additions, or overwrites to the database.' if the user requests database updates, changes, additions, or overwrites.

If a tool can answer the question, you MUST call the tool.

If the user only specifies a day (e.g. on the 21st), respond 'Please specify the day, month, and year for the question or request.'
If the user only specifies a month (e.g in May), use the first day of the month for the year 2025 as the start_date and the last day of the month for the year 2025 as the end_date.
Otherwise:
    If the user does not specify a start_date, use January 1st, 2025 as the baseline for the tool arguments.
    If the user does not specify an end_date, you MUST use December 31st, 2025 as the baseline for the tool arguments.
    If the user does not specify a change_date yet it is needed for the tool, respond 'Please specify the service change date for the question or request'.

The route_id should only be the number or name of the route (e.g. 2, 40, E Line).
If the user does not specify a route_id yet the tool needs it as an argument, respond 'Please specify the route for the question.' DO NOT USE UNSPECIFIED ROUTES.

The most recent service_change_num is 253. The oldest service_change_num is 243.
If the user does not specify a service_change_num yet the tool needs it as an argument, respond 'Please specify the service change number for the question.' DO NOT USE UNSPECIFIED SERVICE CHANGE NUMBERS.

Tools available:
- top_routes_by_ridership: top routes by boardings. Args: start_date, end_date, top_n, day_code, direction
- route_ridership_trend: ridership trend for a route. Args: route_id, start_date, end_date, aggregation
- busiest_stops: busiest stops. Args: start_date, end_date, route_id, top_n, metric
- service_change_impact: ridership before/after service change. Args: route_id, change_date, window_days
- get_overcrowded_routes: overcrowded routes. Args: service_change_num, time_period, top_n
- compare_routes: compare multiple routes. Args: route_ids, start_date, end_date
- declining_routes: routes with ridership decline. Args: comparison_months, threshold_pct, min_trips
- crowding_by_time_period: crowding by time of day. Args: route_id, start_date, end_date
- route_by_direction: inbound vs outbound. Args: route_id, start_date, end_date
- ridership_by_day_type: ridership by day type. Args: route_id, start_date, end_date
"""

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="King County Transit Chat", page_icon="🚌", layout="centered"
)

st.markdown(
    """
<style>
.stApp {
    background-color: #ffd700;
    background-image: repeating-linear-gradient(
        135deg,
        #000000 0px, #000000 25px,
        #ffd700 25px, #ffd700 100px
    );
    color: #1a1a1a;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}
.header {
    display: flex; align-items: center; gap: 1rem;
    padding: 1rem 2rem; margin-bottom: 1.5rem;
    background: linear-gradient(90deg, #ffea00, #ffd600);
    border-radius: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    color: #1a1a1a; font-weight: 700; letter-spacing: 1px;
}
.header-icon { font-size: 3rem; }
.header-text { font-size: 2.2rem; }
.header-subtext { font-size: 1rem; font-weight: 600; font-style: italic; color: #333; }
.chat-message {
    max-width: 85%; padding: 14px 20px 14px 48px; margin-bottom: 14px;
    border-radius: 24px; font-size: 1rem; line-height: 1.5;
    position: relative; box-shadow: 0 3px 12px rgba(0,0,0,0.25);
    animation: fadeInUp 0.4s ease forwards; user-select: text;
}
.chat-message.user {
    margin-left: auto; background-color: #1a1a1a; color: #ffd700;
    border-bottom-right-radius: 4px;
}
.chat-message.assistant {
    background-color: #fffde7; color: #1a1a1a;
    border: 2px solid #1a1a1a; border-bottom-left-radius: 4px;
}
.chat-message.user::before { content: "🛺 "; position: absolute; left: 12px; top: 14px; font-size: 1.5rem; }
.chat-message.assistant::before { content: "🚌 "; position: absolute; left: 12px; top: 14px; font-size: 1.5rem; }
@keyframes fadeInUp { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
.typing { display: flex; gap: 6px; padding: 8px 0 4px 0; }
.typing-dot { width: 10px; height: 10px; background: #1a1a1a; border-radius: 50%; opacity: 0.3; animation: blink 1.2s infinite; }
.typing-dot:nth-child(1) { animation-delay: 0s; }
.typing-dot:nth-child(2) { animation-delay: 0.3s; }
.typing-dot:nth-child(3) { animation-delay: 0.6s; }
@keyframes blink { 0%, 80%, 100% { opacity: 0.3; } 40% { opacity: 1; } }
#MainMenu, footer, header { visibility: hidden; }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="header">
    <div class="header-icon">🚌</div>
    <div>
        <div class="header-text">King County Transit Chat</div>
        <div class="header-subtext">Smart assistant for routes, schedules & transit insights</div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

# ── Session state ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Hi! 👋 I'm your AI transit assistant. Ask me about King County buses, routes, crowding, or ridership data!",
        }
    ]
if "agent_log" not in st.session_state:
    st.session_state.agent_log = []
if "staged_query" not in st.session_state:
    st.session_state.staged_query = ""
if "processing" not in st.session_state:
    st.session_state.processing = False

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📊 Database Stats")
    try:
        from planner_query_tools import query_lib

        summary = query_lib.get_summary()
        st.metric("Total Trips", f"{int(summary['total_trips']):,}")
        st.metric("Unique Routes", str(summary["unique_routes"]))
        st.metric(
            "Date Range", f"{summary['earliest_date']} → {summary['latest_date']}"
        )
    except Exception as e:
        st.error(f"Stats unavailable: {e}")

    st.markdown("### 💡 Example Queries")
    examples = [
        "Which stops had highest boardings on weekdays?",
        "Show crowding for Route 40 during AM Peak",
        "Which routes had most ridership in 2025?",
        "Compare inbound vs outbound load for Route 7",
        "Show top 5 routes by ridership",
        "Show stops in fare zone 24",
    ]
    for ex in examples:
        if st.button(ex, key=ex, use_container_width=True):
            st.session_state.staged_query = ex
            st.rerun()

    st.markdown("### 🤖 Agent Trace")
    for log in st.session_state.agent_log[-5:]:
        st.markdown(
            f"🔧 **{log.get('tool', 'tool')}**: {log.get('action', '')}",
            unsafe_allow_html=False,
        )

    st.markdown("---")
    st.markdown("### 🛠️ Tools Loaded")
    for t in ALL_TOOLS:
        st.caption(f"• `{t.name}`")

    st.markdown("---")
    with st.expander("🛡️ Security Tester", expanded=False):
        st.caption("Test how the app handles malicious inputs.")
        attack_tests = {
            "SQL injection": "1' OR '1'='1",
            "DROP statement": "DROP TABLE trips",
            "DELETE statement": "DELETE FROM trips WHERE 1=1",
            "Stacked query": "Route 1; DROP TABLE trips;--",
            "Empty input": "",
        }
        selected_test = st.selectbox(
            "Pick an attack vector:", list(attack_tests.keys()), key="sec_test_select"
        )
        test_value = attack_tests[selected_test]
        st.code(test_value if test_value else "(empty string)", language="text")
        if st.button("▶ Run Test", key="sec_run_btn", use_container_width=True):
            import re

            BLOCKED = re.compile(
                r"\b(DROP|DELETE|UPDATE|INSERT|TRUNCATE|ALTER|EXEC|EXECUTE|UNION|CREATE|REPLACE|GRANT|REVOKE|pg_read_file)\b",
                re.IGNORECASE,
            )
            if not test_value.strip():
                st.error("❌ Blocked — Input is empty")
            elif len(test_value) > 2000:
                st.error(f"❌ Blocked — Too long: {len(test_value)} chars")
            elif BLOCKED.search(test_value):
                found = BLOCKED.findall(test_value)
                st.error(f"❌ Blocked — Dangerous keyword: {found}")
            else:
                st.success("✅ Passed — Input looks safe")


# ── Core: invoke LLM + tools, return structured result ────────────────────────
def run_agent(user_input: str) -> dict:
    """
    Returns dict with keys:
      - text: str  (markdown answer)
      - df: pd.DataFrame or None  (table to display)
      - fig: plotly figure or None  (chart to display)
    """
    messages = [SystemMessage(SYSTEM_INSTRUCTIONS), HumanMessage(user_input)]

    try:
        response = llm.invoke(messages)
    except Exception as e:
        return {"text": f"⚠️ LLM error: {e}", "df": None, "fig": None}

    # No tool call — plain text answer
    if not response.tool_calls:
        return {
            "text": response.content or "I couldn't generate a response.",
            "df": None,
            "fig": None,
        }

    # ── Execute every tool call ───────────────────────────────────────────────
    all_text = []
    all_dfs = []

    messages.append(response)  # append AIMessage with tool_calls

    for tool_call in response.tool_calls:
        tool_name = tool_call["name"].lower()
        selected_tool = TOOL_MAP.get(tool_name)

        if selected_tool is None:
            all_text.append(f"⚠️ Unknown tool: {tool_name}")
            continue

        st.session_state.agent_log.append(
            {"tool": tool_name, "action": str(tool_call.get("args", {}))}
        )

        try:
            # invoke() returns a ToolMessage when called with the full tool_call dict
            tool_msg = selected_tool.invoke(tool_call)
            tool_output = (
                tool_msg.content if hasattr(tool_msg, "content") else str(tool_msg)
            )
        except Exception as e:
            tool_output = f"⚠️ Tool error ({tool_name}): {e}"

        messages.append(ToolMessage(content=tool_output, tool_call_id=tool_call["id"]))
        all_text.append(tool_output)

        # ── Try to extract a DataFrame from the tool result ───────────────
        df = _extract_df_from_tool(tool_name, tool_call.get("args", {}))
        if df is not None and not df.empty:
            all_dfs.append((tool_name, df))

    # ── Let LLM synthesize a human-friendly summary ───────────────────────
    try:
        summary_llm = ChatOllama(model="llama3.2", temperature=0)
        final = summary_llm.invoke(messages)
        summary_text = final.content or "\n\n".join(all_text)
    except Exception:
        summary_text = "\n\n".join(all_text)

    # ── Pick the first DataFrame and try to visualize it ──────────────────
    combined_df = None
    fig = None
    if all_dfs:
        tool_name_used, combined_df = all_dfs[0]
        fig = _auto_visualize(tool_name_used, combined_df)

    return {"text": summary_text, "df": combined_df, "fig": fig}


def _extract_df_from_tool(tool_name: str, args: dict) -> pd.DataFrame | None:
    """Directly call the underlying query_lib method to get a DataFrame."""
    try:
        from planner_query_tools import query_lib

        if tool_name == "top_routes_by_ridership":
            return query_lib.get_top_routes_by_ridership(**args)
        elif tool_name == "route_ridership_trend":
            return query_lib.get_route_ridership_trend(**args)
        elif tool_name == "busiest_stops":
            return query_lib.get_busiest_stops(**args)
        elif tool_name == "get_overcrowded_routes":
            return query_lib.get_overcrowded_routes(**args)
        elif tool_name == "compare_routes":
            # route_ids may come as comma-separated string
            raw = args.get("route_ids", "")
            if isinstance(raw, str):
                args = {**args, "route_ids": [r.strip() for r in raw.split(",")]}
            return query_lib.compare_routes(**args)
        elif tool_name == "declining_routes":
            return query_lib.identify_declining_routes(**args)
        elif tool_name == "crowding_by_time_period":
            return query_lib.get_crowding_by_time_period(**args)
        elif tool_name == "route_by_direction":
            return query_lib.get_route_by_direction(**args)
        elif tool_name == "ridership_by_day_type":
            return query_lib.get_ridership_by_day_type(**args)
        elif tool_name == "service_change_impact":
            result = query_lib.analyze_service_change_impact(**args)
            # Convert impact dict to simple DataFrame
            rows = []
            for period in ["before_period", "after_period"]:
                d = result.get(period, {})
                d["period"] = period.replace("_period", "")
                rows.append(d)
            return pd.DataFrame(rows)
    except Exception as e:
        print(f"[_extract_df_from_tool] {tool_name} failed: {e}")
    return None


def _auto_visualize(tool_name: str, df: pd.DataFrame):
    """Choose sensible x/y/chart_type for each tool and call VisualizationAgent."""
    CHART_CONFIG = {
        "top_routes_by_ridership": {
            "x": "route",
            "y": "total_boardings",
            "chart_type": "bar",
            "title": "Top Routes by Ridership",
        },
        "route_ridership_trend": {
            "x": "period",
            "y": "total_boardings",
            "chart_type": "line",
            "title": "Ridership Trend Over Time",
        },
        "busiest_stops": {
            "x": "stop_nm",
            "y": "total_boardings",
            "chart_type": "bar",
            "title": "Busiest Stops",
        },
        "get_overcrowded_routes": {
            "x": "route",
            "y": "overcrowded_trips",
            "chart_type": "bar",
            "title": "Overcrowded Routes",
        },
        "compare_routes": {
            "x": "route",
            "y": "total_boardings",
            "chart_type": "bar",
            "title": "Route Comparison",
        },
        "declining_routes": {
            "x": "route",
            "y": "boardings_pct_change",
            "chart_type": "bar",
            "title": "Declining Routes (% Change)",
        },
        "crowding_by_time_period": {
            "x": "time_period",
            "y": "pct_crowded",
            "chart_type": "bar",
            "title": "Crowding by Time Period",
        },
        "route_by_direction": {
            "x": "direction_label",
            "y": "total_boardings",
            "chart_type": "bar",
            "title": "Ridership by Direction",
        },
        "ridership_by_day_type": {
            "x": "day_type",
            "y": "total_boardings",
            "chart_type": "bar",
            "title": "Ridership by Day Type",
        },
        "service_change_impact": {
            "x": "period",
            "y": "avg_boardings_per_trip",
            "chart_type": "bar",
            "title": "Service Change Impact",
        },
    }

    cfg = CHART_CONFIG.get(tool_name)
    if cfg is None:
        return None

    # Fall back gracefully if expected columns are missing
    if cfg["x"] not in df.columns or cfg["y"] not in df.columns:
        # Try first string col as x, first numeric col as y
        str_cols = [c for c in df.columns if df[c].dtype == object]
        num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        if not str_cols or not num_cols:
            return None
        cfg = {**cfg, "x": str_cols[0], "y": num_cols[0]}

    result = {"data": df, **cfg}
    return viz_agent.generate(result)


# ── Display all messages ──────────────────────────────────────────────────────
def display_messages():
    for i, msg in enumerate(st.session_state.messages):
        role = msg["role"]
        content = msg["content"]

        st.markdown(
            f'<div class="chat-message {role}">{content}</div>', unsafe_allow_html=True
        )

        # Render table if present
        if msg.get("df") is not None:
            st.dataframe(msg["df"], use_container_width=True, key=f"df_{i}")

        # Render chart if present
        if msg.get("fig") is not None:
            st.plotly_chart(msg["fig"], use_container_width=True, key=f"fig_{i}")

        # Copy button
        if HAS_COPY:
            try:
                from st_copy import copy_button

                copy_button(
                    content,
                    icon="st",
                    key=f"copy_{i}",
                    tooltip="Copy",
                    copied_label="Copied!",
                )
            except Exception:
                pass


# ── Handle staged query from sidebar ─────────────────────────────────────────
if st.session_state.staged_query and not st.session_state.processing:
    user_msg = st.session_state.staged_query
    st.session_state.staged_query = ""
    st.session_state.messages.append({"role": "user", "content": user_msg})
    # Don't rerun — fall through to processing block below

# ── Render all messages ───────────────────────────────────────────────────────
display_messages()

# ── If last message is user → process ────────────────────────────────────────
if st.session_state.messages[-1]["role"] == "user" and not st.session_state.processing:
    st.session_state.processing = True

    # Show typing indicator
    typing_placeholder = st.empty()
    typing_placeholder.markdown(
        """
    <div class="chat-message assistant">
        <div class="typing">
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    time.sleep(0.4)

    user_input = st.session_state.messages[-1]["content"]

    result = run_agent(user_input)

    typing_placeholder.empty()
    st.session_state.processing = False

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": result["text"],
            "df": result["df"],
            "fig": result["fig"],
        }
    )

    st.rerun()

# ── Chat input ────────────────────────────────────────────────────────────────
prompt = st.chat_input("Ask me about King County Metro routes...")
if prompt and not st.session_state.processing:
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()


# import sys, os, time
# # Add the project root (the folder containing 'agents' and 'combined') to sys.path
# PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# if PROJECT_ROOT not in sys.path:
#     sys.path.insert(0, PROJECT_ROOT)

# # app.py
# from langchain_core.messages import SystemMessage, HumanMessage
# from langchain_ollama import ChatOllama
# import streamlit as st
# from st_copy import copy_button

# from visualization_agent import VisualizationAgent

# #from query_info import SCHEMA, query_db
# from planner_query_tools import *

# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# # ── Teammate's LangChain imports (from ollama/langchain_tools/) ──────────────
# LANGCHAIN_AVAILABLE = False
# _lc_err_msg = ""
# try:
#     from langchain_core.messages import SystemMessage, HumanMessage
#     from langchain_ollama import ChatOllama

#     # Add langchain_tools folder so query_tools and query are importable
#     LC_TOOLS_PATH = os.path.join(PROJECT_ROOT, "ollama", "langchain_tools")
#     if LC_TOOLS_PATH not in sys.path:
#         sys.path.insert(0, LC_TOOLS_PATH)

#     from query_tools import get_operation_period, TOOL_DICT, SUPPORTED_TOOL_MESSAGE

#     # LLM with tools bound — exactly as teammate set it up in langchain_tools/app.py
#     _lc_llm = ChatOllama(model="llama3.2", temperature=0).bind_tools(list(TOOL_DICT.values()))
#     LANGCHAIN_AVAILABLE = True
# except Exception as _err:
#     _lc_err_msg = str(_err)


# def _run_langchain(prompt: str) -> str:
#     """
#     Runs the teammate's LangChain pipeline exactly as written in
#     ollama/langchain_tools/app.py. No new agents — uses TOOL_DICT and _lc_llm directly.
#     """
#     system_instructions = (
#         "You are a helpful assistant focused on King County Metro. "
#         "Answer without mentioning tools nor dictionaries. "
#         f"If you do not have the tools to answer the question, "
#         f"reply with '{SUPPORTED_TOOL_MESSAGE}' only."
#     )

#     messages = [SystemMessage(system_instructions), HumanMessage(prompt)]
#     response = _lc_llm.invoke(messages)
#     answer = response.content

#     if response.tool_calls:
#         messages.append(response)
#         for tool_call in response.tool_calls:
#             selected_tool = TOOL_DICT[tool_call["name"].lower()]
#             tool_msg = selected_tool.invoke(tool_call)
#             messages.append(tool_msg)
#         # Second call to synthesize tool output into plain English
#         answer = ChatOllama(model="llama3.2", temperature=0).invoke(messages).content

#     return answer

# # --- Variables & Functions ---
# TOOL_MAP = {tool.name.lower(): tool for tool in ALL_TOOLS}

# MAX_FIX_ATTEMPTS = 5

# def display_messages():
#     """Display all messages in the chat history"""
#     button_count = 0    # count for unique copy buttons

#     for msg in st.session_state.messages:
#         author = "user" if msg["role"] == "user" else "assistant"
#         with st.chat_message(author):
#             st.write(msg["content"])

#             # Add a copy button
#             button_key = f"copy_btn_{button_count}"
#             copy_button(
#                 msg["content"],
#                 icon="st",  # use Streamlit's code-block icon
#                 key=button_key,
#                 tooltip="Copy Message",
#                 copied_label="Message Copied!"
#             )
#             button_count += 1

# def extractQuery(response):
#     """Extract SQL statement from LLM's response"""
#     statement = response.content.replace("\n", " ")
#     start_index = statement.rfind("SELECT")
#     end_index = start_index + statement[start_index:].rfind(";")
#     statement = statement[start_index:end_index]
#     return statement


# # -- Configure the LLM ---
# llm = ChatOllama(
#     model="llama3.2",
#     #model="qwen3",
#     temperature=0,
# ).bind_tools(ALL_TOOLS)

# # --- Configure Streamlit page ---
# st.set_page_config(page_title="King County Transit Chat", page_icon="🚌", layout="centered")
# st.title("🚌 Transit Data Chat Assistant")
# st.subheader("Your AI assistant for retrieving King Country Metro transit data")

# # --- Custom CSS ---
# st.markdown(
#     """
#     <style>
#     /* App background: yellow with thick diagonal black stripes */
#     .stApp {
#         background-color: #ffd700; /* taxi yellow */
#         background-image: repeating-linear-gradient(
#         135deg,
#         #000000 0px,
#         #000000 25px,
#         #ffd700 25px,
#         #ffd700 100px
#         );
#         color: #1a1a1a;
#         font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
#         user-select: none;
#     }

#     /* Header container */
#     .header {
#         display: flex;
#         align-items: center;
#         gap: 1rem;
#         padding: 1rem 2rem;
#         margin-bottom: 1.5rem;
#         background: linear-gradient(90deg, #ffea00, #ffd600);
#         border-radius: 20px;
#         box-shadow: 0 4px 15px rgba(0,0,0,0.5);
#         color: #1a1a1a;
#         font-weight: 700;
#         letter-spacing: 1px;
#         animation: pulse 3s ease-in-out infinite;
#     }
#     .header-icon { font-size: 3rem; animation: bounce 2s infinite; }
#     @keyframes pulse {
#         0%, 100% { filter: drop-shadow(0 0 0 rgba(0,0,0,0)); }
#         50% { filter: drop-shadow(0 0 15px #ffd600bb); }
#     }
#     @keyframes bounce { 0%,100%{transform:translateY(0);}50%{transform:translateY(-7px);} }
#     .header-text { font-size: 2.2rem; }
#     .header-subtext { font-size: 1rem; margin-top: -0.3rem; font-weight: 600; font-style: italic; color: #333; }

#     /* Chat container scroll */
#     .chat-container { max-height: 520px; overflow-y: auto; padding-right: 10px; margin-bottom: 1.5rem; }
#     .chat-container::-webkit-scrollbar { width: 8px; }
#     .chat-container::-webkit-scrollbar-thumb { background-color: #1a1a1a; border-radius: 10px; }
#     .chat-container::-webkit-scrollbar-track { background: transparent; }

#     /* Message bubbles */
#     .chat-message {
#         max-width: 80%;
#         padding: 14px 20px 14px 48px;
#         margin-bottom: 14px;
#         border-radius: 24px;
#         font-size: 1.1rem;
#         line-height: 1.4;
#         position: relative;
#         box-shadow: 0 3px 12px rgba(0,0,0,0.25);
#         animation: fadeInUp 0.4s ease forwards;
#         user-select: text;
#     }

#     /* User bubble */
#     .chat-message.user {
#         margin-left: auto;
#         background-color: #1a1a1a; /* black */
#         color: #ffd700; /* yellow text */
#         border-bottom-right-radius: 4px;
#     }
#     /* Assistant bubble */
#     .chat-message.assistant {
#         background-color: #ffd700; /* yellow */
#         color: #1a1a1a; /* black text */
#         border: 2px solid #1a1a1a;
#         border-bottom-left-radius: 4px;
#     }

#     /* Bubble icons */
#     .chat-message.user::before { content: "🛺 "; position: absolute; left: 16px; top: 50%; transform: translateY(-50%); font-size: 1.8rem; }
#     .chat-message.assistant::before { content: "🚌 "; position: absolute; left: 16px; top: 50%; transform: translateY(-50%); font-size: 1.8rem; }

#     /* Fade-in animation */
#     @keyframes fadeInUp { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }

#     /* Typing indicator */
#     .typing { display: flex; gap: 6px; margin-top: 6px; padding-left: 48px; }
#     .typing-dot {
#         width: 10px; height: 10px; background: #1a1a1a;
#         border-radius: 50%; opacity: 0.3; animation: blink 1.2s infinite;
#     }
#     .typing-dot:nth-child(1) { animation-delay: 0s; }
#     .typing-dot:nth-child(2) { animation-delay: 0.3s; }
#     .typing-dot:nth-child(3) { animation-delay: 0.6s; }
#     @keyframes blink { 0%, 80%, 100% { opacity: 0.3; } 40% { opacity: 1; } }

#     /* Glassmorphism error messages */
#     /* Glassmorphism error messages - improved visibility */
# .stAlert {
#     background: rgba(220, 20, 60, 0);  /* dark red with high opacity */
#     /*backdrop-filter: blur(10px);*/
#     color: #000000;  /* bright white text */
#     font-weight: 700;
#     border-radius: 14px;
#     padding: 12px 20px;
#     margin: 12px 0;
#     border: 1px solid rgba(255, 255, 255, 0.6);
#     box-shadow: 0 4px 15px rgba(0,0,0,0.4); /* stronger shadow */
#     text-align: center;
# }

#     /* Hide Streamlit footer/menu/header */
#     #MainMenu, footer, header { visibility: hidden; }
#     </style>
#     """,
#     unsafe_allow_html=True,
# )

# # Header
# st.markdown(
#     """
#     <div class="header">
#         <div class="header-icon">🚌</div>
#         <div>
#             <div class="header-text">King County Transit Chat</div>
#             <div class="header-subtext">Smart assistant for routes, schedules & transit insights</div>
#         </div>
#     </div>
#     """,
#     unsafe_allow_html=True)

# # --- Session state (unchanged + lc_messages added) ---
# if "messages" not in st.session_state:
#     st.session_state.messages = [
#         {"role": "assistant", "content": "Hi! 👋 I'm your AI transit assistant. Ask me about King County buses, routes, crowding, or ridership data!"}
#     ]
# if "lc_messages" not in st.session_state:
#     st.session_state.lc_messages = [
#         {"role": "assistant", "content": "Hi! 👋 I'm your LangChain tool-calling assistant. I use bound tools to fetch live transit data. Try: 'What is the operation period?'"}
#     ]
# if "agent_log" not in st.session_state:
#     st.session_state.agent_log = []
# if "example_text" not in st.session_state:
#     st.session_state.example_text = ""
# if "staged_query" not in st.session_state:
#     st.session_state.staged_query = ""
# if "lc_staged_query" not in st.session_state:
#     st.session_state.lc_staged_query = ""
# if "fix_attempts" not in st.session_state:
#     st.session_state.fix_attempts = 0
# # --- Sidebar (unchanged + LangChain status appended) ---
# with st.sidebar:
#     st.markdown("### 📊 Database Stats")
#     try:
#         from planner_query_tools import query_lib
#         summary = query_lib.get_summary()
#         st.metric("Total Trips", f"{int(summary['total_trips']):,}")
#         st.metric("Unique Routes", str(summary['unique_routes']))
#         st.metric("Date Range", f"{summary['earliest_date']} → {summary['latest_date']}")
#     except Exception as e:
#         st.error(f"Stats unavailable: {e}")

#     st.markdown("### 💡 Example Queries")
#     examples = [
#         "Which stops had highest boardings on weekdays?",
#         "Show crowding for Route 1 during AM Peak",
#         "Which routes had most delays?",
#         "Compare inbound vs outbound load",
#         "Predict peak load for Route 677",
#         "Show stops in fare zone 24",
#     ]
#     for ex in examples:
#         if st.button(ex, key=ex, use_container_width=True):
#             st.session_state.staged_query = ex
#             st.rerun()

#     st.markdown("### 🤖 Agent Trace")
#     for log in st.session_state.agent_log[-5:]:
#         st.markdown(
#             f'<div class="agent-step">🔧 <b>{log["agent"]}</b>: {log["action"]} '
#             f'<span class="reward-badge">R:{log["reward"]:.2f}</span></div>',
#             unsafe_allow_html=True
#         )

#     # LangChain status — new addition at bottom of sidebar
#     st.markdown("---")
#     st.markdown("### 🔗 LangChain Status")
#     if LANGCHAIN_AVAILABLE:
#         st.success("✅ Ready")
#         st.caption("Bound tools: " + ", ".join(f"`{k}`" for k in TOOL_DICT))
#     else:
#         st.warning("⚠️ Not available")
#         st.caption(f"`{_lc_err_msg}`")
#         st.caption("Fix: `pip install langchain langchain-ollama`")

#     # ── Security Tester (reduced to 5 checks) ───────────────────────────────
#     st.markdown("---")
#     with st.expander("🛡️ Security Tester", expanded=False):
#         st.caption("Test how the app handles malicious or invalid inputs.")

#         # Pre-built attack test cases
#         attack_tests = {
#             "SQL injection":        "1' OR '1'='1",
#             "DROP statement":       "DROP TABLE trips",
#             "DELETE statement":     "DELETE FROM trips WHERE 1=1",
#             "Stacked query":        "Route 1; DROP TABLE trips;--",
#             "Empty input":          "",
#             # "Too long (2001 chars)": "a" * 2001,
#             # "Normal safe query":    "Which stops had highest boardings?",
#         }

#         selected_test = st.selectbox(
#             "Pick an attack vector:",
#             list(attack_tests.keys()),
#             key="sec_test_select"
#         )
#         test_value = attack_tests[selected_test]
#         st.code(test_value if test_value else "(empty string)", language="text")

#         if st.button("▶ Run Test", key="sec_run_btn", use_container_width=True):
#             import re

#             # Combined destructive/keyword check
#             BLOCKED = re.compile(
#                 r"\b(DROP|DELETE|UPDATE|INSERT|TRUNCATE|ALTER|EXEC|EXECUTE|UNION|CREATE|REPLACE|GRANT|REVOKE|pg_read_file)\b",
#                 re.IGNORECASE,
#             )
#             results = []

#             # Check 1: empty input
#             if not test_value.strip():
#                 results.append(("❌ Blocked", "Input is empty"))
#             # Check 2: length
#             elif len(test_value) > 2000:
#                 results.append(("❌ Blocked", f"Too long: {len(test_value)} chars (max 2000)"))
#             # Check 3: dangerous keywords
#             elif BLOCKED.search(test_value):
#                 found = BLOCKED.findall(test_value)
#                 results.append(("❌ Blocked", f"Dangerous keyword detected: {found}"))
#             # Check 4: entity injection / sanitization
#             fake_route = re.sub(r"[^\w\s]", "", test_value)[:20]
#             if fake_route != test_value.strip()[:20]:
#                 results.append(("🔒 Sanitized", f"Entity value cleaned: '{test_value[:20]}' → '{fake_route}'"))
#             # Check 5: safe input passes
#             else:
#                 results.append(("✅ Passed", "Input looks safe — would proceed to LLM"))

#             # Display results
#             st.markdown("**Results:**")
#             for status, message in results:
#                 if status.startswith("❌"):
#                     st.error(f"{status} — {message}")
#                 elif status.startswith("🔒"):
#                     st.warning(f"{status} — {message}")
#                 else:
#                     st.success(f"{status} — {message}")
#         # Manual input test
#         st.markdown("**Or type your own:**")
#         custom_input = st.text_input("Custom test input:", key="sec_custom_input", placeholder="Type anything...")
#         if st.button("▶ Test Custom", key="sec_custom_btn", use_container_width=True) and custom_input:
#             import re
#             BLOCKED = re.compile(
#                 r"\b(DROP|DELETE|UPDATE|INSERT|TRUNCATE|ALTER|EXEC|EXECUTE"
#                 r"|UNION|CREATE|REPLACE|GRANT|REVOKE|pg_read_file)\b",
#                 re.IGNORECASE,
#             )
#             if not custom_input.strip():
#                 st.error("❌ Blocked — Input is empty")
#             elif len(custom_input) > 2000:
#                 st.error(f"❌ Blocked — Too long ({len(custom_input)} chars)")
#             elif BLOCKED.search(custom_input):
#                 found = BLOCKED.findall(custom_input)
#                 st.error(f"❌ Blocked — Dangerous keyword: {found}")
#             else:
#                 st.success("✅ Passed — Input would proceed to pipeline")

# # --- Typing indicator (unchanged) ---
# def show_typing():
#     st.markdown("""
#     <div class="chat-message assistant">
#         <div class="typing">
#             <div class="typing-dot"></div>
#             <div class="typing-dot"></div>
#             <div class="typing-dot"></div>
#         </div>
#     </div>
#     """, unsafe_allow_html=True)

# # =============================================================================
# # TABS — Tab 1 is byte-for-byte identical to original app.py logic
# # =============================================================================
# tab_langchain = st.tabs(["🔗 LangChain Tools"]) #"🤖 Agent Pipeline",

# # # ── TAB 1: Original agent pipeline — NOTHING changed ─────────────────────────
# # with tab_agents:

# #     for i, msg in enumerate(st.session_state.messages):
# #         role = msg["role"]
# #         content = msg["content"]
# #         st.markdown(f'<div class="chat-message {role}">{content}</div>', unsafe_allow_html=True)
# #         if msg.get("chart"):
# #             st.plotly_chart(msg["chart"], use_container_width=True, key=f"chart_{i}")
# #         if msg.get("table") is not None:
# #             st.dataframe(msg["table"], use_container_width=True, key=f"table_{i}")

# #     if st.session_state.staged_query:
# #         user_msg = st.session_state.staged_query
# #         st.session_state.staged_query = ""
# #         st.session_state.messages.append({"role": "user", "content": user_msg})
# #         st.rerun()

# #     prompt = st.chat_input("Ask about buses, routes, delays, or ridership…", key="chat_input")
# #     if prompt:
# #         st.session_state.messages.append({"role": "user", "content": prompt})
# #         st.rerun()

# #     if st.session_state.messages[-1]["role"] == "user":
# #         show_typing()
# #         time.sleep(0.8)
# #         try:
# #             result = orchestrator.run(st.session_state.messages[-1]["content"])
# #             st.session_state.agent_log.extend(result.get("agent_trace", []))
# #             st.session_state.messages.append({
# #                 "role": "assistant",
# #                 "content": result["response"],
# #                 "chart": result.get("chart"),
# #                 "table": result.get("table"),
# #             })
# #         except Exception as e:
# #             st.session_state.messages.append({
# #                 "role": "assistant",
# #                 "content": f"⚠️ Error processing query: {e}\n\nPlease check database connection and try again."
# #             })
# #         st.rerun()

# # ── TAB 2: Teammate's LangChain tool-calling pipeline ────────────────────────
# #with tab_langchain:

# if not LANGCHAIN_AVAILABLE:
#     st.warning(
#         f"⚠️ LangChain unavailable: `{_lc_err_msg}`\n\n"
#         "Install with:\n```\npip install langchain langchain-ollama\n```"
#     )
# else:
#     st.info(
#         "Uses **LangChain tool-binding** — the LLM decides which tool to call "
#         "based on your question, then explains the result in plain English.",
#         icon="🔗"
#     )

#     for i, msg in enumerate(st.session_state.lc_messages):
#         role = msg["role"]
#         content = msg["content"]
#         st.markdown(f'<div class="chat-message {role}">{content}</div>', unsafe_allow_html=True)

#     if st.session_state.lc_staged_query:
#         user_msg = st.session_state.lc_staged_query
#         st.session_state.lc_staged_query = ""
#         st.session_state.lc_messages.append({"role": "user", "content": user_msg})
#         st.rerun()

#     lc_prompt = st.chat_input("Ask the LangChain tool agent…", key="lc_chat_input")
#     if lc_prompt:
#         st.session_state.lc_messages.append({"role": "user", "content": lc_prompt})
#         st.rerun()

#     if st.session_state.lc_messages[-1]["role"] == "user":
#         show_typing()
#         time.sleep(0.8)
#         try:
#             answer = _run_langchain(st.session_state.lc_messages[-1]["content"])
#             st.session_state.lc_messages.append({"role": "assistant", "content": answer})
#         except Exception as e:
#             st.session_state.lc_messages.append({
#                 "role": "assistant",
#                 "content": f"⚠️ LangChain error: {e}"
#             })
#         st.rerun()

#     st.markdown("---")
#     st.markdown("#### 🛠️ Bound Tools")
#     for name in TOOL_DICT:
#         st.markdown(f"- `{name}`")

# # Initialize chat history
# if "messages" not in st.session_state:
#     st.session_state.messages = [
#         {
#             "role": "assistant",
#             "content": "Hi! I'm your transit data assistant. Ask me anything about King County Metro transit routes. How can I help you today?"
#         }
#     ]

# display_messages()

# # --- Handle new user input ---
# prompt = st.chat_input("Ask me about King County Metro routes ...")

# if prompt:
#     # Add user message to history
#     st.session_state.messages.append({"role": "user", "content": prompt})

#     # Show user message
#     with st.chat_message("user"):
#         st.write(prompt)

#     # Show thinking indicator while processing
#     with st.chat_message("assistant"):
#         placeholder = st.empty()
#         placeholder.write("🤔 Thinking...")

#         # Call Ollama through ChatOllama
#         try:
#             print("\n*** ---------------------------------------------------- ***\n")   # to separate responses for each prompt

#             # Configure the invocation array
#             systemInstructions = """
#                 You are a helpful assistant who only answers about King County Metro.
#                 If the user asks about any other transit systems (e.g. New York transit), state 'I am not authorized to provide information not pertaining to King County Metro.' Do not answer about any other transit systems.
#                 Respond 'I am not authorized to suggest updates, additions, or overwrites to the database.' if the user requests database updates, changes, additions, or overwrites.

#                 If a tool can answer the question, you MUST call the tool.

#                 If the user only specifes a day (e.g. on the 21st), respond 'Please specify the day, month, and year for the question or request.'
#                 If the user only specifies a month (e.g in May), use the first day of the month for the year 2025 as the start_date and the last day of the month for the year 2025 as the end_date.
#                 Otherwise:
#                     If the user does not specify a start_date, use January 1st, 2025 as the baseline for the tool arguments.
#                     If the user does not specify an end_date, you MUST use December 31st, 2025 as the baseline for the tool arguments.
#                     If the user does not specify a change_date yet it is needed for the tool, respond 'Please specify the service change date for the question or request'.

#                 The route_id should only be the number or name of the route (e.g. 2, 40, E Line).
#                 If the user does not specify a route_id yet the tool needs it as an argument, respond 'Please specify the route for the question.' DO NOT USE UNSPECIFIED ROUTES.

#                 The most recent service_change_num is 253. The oldest service_change_num is 243.
#                 If the user does not specify a service_change_num yet the tool needs it as an argument, respond 'Please specify the service change number for the question.' DO NOT USE UNSPECIFIED SERVICE CHANGE NUMBERS.

#                 Here is a description of all the tools:

#                 top_routes_by_ridership returns the top routes by boardings for a date range.
#                 Args:
#                     start_date: Start date (YYYY-MM-DD)
#                     end_date: End date (YYYY-MM-DD)
#                     top_n: Number of routes to return (default 10)
#                     day_code: Optional filter ('WK', 'SA', 'SU', 'HOL')
#                     direction: Optional filter ('I', 'O', '0')

#                 route_ridership_trend returns the ridership trend for a route over time.
#                 Args:
#                     route_id: Route identifier (e.g., '40', '7', 'E Line')
#                     start_date: Start date (YYYY-MM-DD)
#                     end_date: End date (YYYY-MM-DD)
#                     aggregation: 'daily', 'weekly', or 'monthly' (default 'daily')

#                 busiest_stops returns the busiest stops by total boardings or total alightings.
#                 Args:
#                         start_date: Start date
#                         end_date: End date
#                         route_id: Optional route filter
#                         top_n: Number of stops to return
#                         metric: 'boardings' or 'alightings' (default 'boardings')

#                 service_change_impact returns an analysis of ridership impact before and after a service change.
#                 Args:
#                     route_id: Route identifier
#                     change_date: Date of service change (YYYY-MM-DD)
#                     window_days: Days before/after to compare (default 30)

#                 get_overcrowded_routes identifies overcrowded routes based on King County Metro's definition
#                 Args:
#                     service_change_num: Service change period identifier (e.g. )
#                     time_period: Optional filter (e.g., 'AM Peak', 'PM Peak')
#                     top_n: Number of routes (default 10)

#                 compare_routes compares multiple routes side-by-side.
#                 Args:
#                     route_ids: Comma-separated route IDs (e.g., "40,7,E Line")
#                     start_date: Start date (YYYY-MM-DD)
#                     end_date: End date (YYYY-MM-DD)

#                 declining_routes identifies routes with significant ridership decline.
#                 Args:
#                     comparison_months: Months to compare (default 3)
#                     threshold_pct: Decline threshold as negative % (default -10)
#                     min_trips: Minimum trips to include (default 100)

#                 crowding_by_time_period analyzes crowding patterns by time of day.
#                 Args:
#                     route_id: Optional route filter
#                     start_date: Start date (YYYY-MM-DD)
#                     end_date: End date (YYYY-MM-DD)

#                 route_by_direction compares inbound vs outbound performance for a route.
#                 Args:
#                     route_id: Route identifier
#                     start_date: Start date (YYYY-MM-DD)
#                     end_date: End date (YYYY-MM-DD)

#                 ridership_by_day_type analyzes ridership by day type (Weekday/Saturday/Sunday/Holiday).
#                 Args:
#                     route_id: Optional route filter
#                     start_date: Start date (YYYY-MM-DD)
#                     end_date: End date (YYYY-MM-DD)
#             """
#             systemMessages = [SystemMessage(systemInstructions),
#                               HumanMessage(prompt)]

#             # Get response from LLM
#             response = llm.invoke(systemMessages)
#             print(response)
#             answer = response.content

#             if ("I am not authorized" not in answer) and ("Please specify" not in answer):
#                 if response.tool_calls: # If the model calls a tool, handle the tool call
#                     print("Handling tool invocation...")

#                     answer = ""
#                     for tool_call in response.tool_calls:
#                         tool_name = tool_call["name"].lower()
#                         selected_tool = TOOL_MAP[tool_name]

#                         # Execute tool with args ONLY
#                         tool_result = selected_tool.invoke(tool_call["args"])
#                         answer += str(tool_result) + "\n"

#                     print(response.tool_calls)

#         except Exception as e:
#             answer = f"I'm sorry, I encountered an error: {e}. Please try asking your question again."

#         # Replace thinking indicator with actual response
#         placeholder.write(answer)

#         # Add assistant response to history
#         st.session_state.messages.append({"role": "assistant", "content": answer})

#     # Refresh the page to show updated chat
#     st.rerun()
