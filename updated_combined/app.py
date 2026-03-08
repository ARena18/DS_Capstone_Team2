# ── app.py ────────────────────────────────────────────────────────────────────
# King County Metro Chat Assistant
# ─────────────────────────────────────────────────────────────────────────────

# ── Directory Setup ───────────────────────────────────────────────────────────
from st_copy import copy_button
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_ollama import ChatOllama

from visualization_agent import VisualizationAgent
from planner_query_tools import ALL_TOOLS, query_lib
import sys
import os
import re
import pandas as pd
import streamlit as st

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ── Constants ─────────────────────────────────────────────────────────────────
TOOL_MAP = {tool.name.lower(): tool for tool in ALL_TOOLS}

SYSTEM_PROMPT = """
You are a helpful assistant who only answers about King County Metro.
If the user asks about any other transit systems (e.g. New York transit), state
'I am not authorized to provide information not pertaining to King County Metro.'
Do not answer about any other transit systems.

Respond 'I am not authorized to suggest updates, additions, or overwrites to the database.'
if the user requests database updates, changes, additions, or overwrites.

If a tool can answer the question, you MUST call the tool.

If the user only specifies a day (e.g. on the 21st), respond
'Please specify the day, month, and year for the question or request.'

If the user only specifies a month (e.g. in May), use the first day of the month
for the year 2025 as the start_date and the last day of the month for the year 2025
as the end_date.

Otherwise:
  - If the user does not specify a start_date, use January 1st, 2025 as the baseline.
  - If the user does not specify an end_date, use December 31st, 2025 as the baseline.
  - If the user does not specify a change_date yet it is needed, respond
    'Please specify the service change date for the question or request'.

The route_id should only be the number or name of the route (e.g. 2, 40, E Line).
If the user does not specify a route_id yet the tool needs it, respond
'Please specify the route for the question.' DO NOT USE UNSPECIFIED ROUTES.

The most recent service_change_num is 253. The oldest service_change_num is 243.
If the user does not specify a service_change_num yet the tool needs it, respond
'Please specify the service change number for the question.'
DO NOT USE UNSPECIFIED SERVICE CHANGE NUMBERS.

Tool descriptions:

top_routes_by_ridership — Returns the top routes by boardings for a date range.
  Args: start_date, end_date, top_n (default 10), day_code (optional: WK/SA/SU/HOL),
        direction (optional: I/O/0)

route_ridership_trend — Returns the ridership trend for a route over time.
  Args: route_id, start_date, end_date, aggregation (daily/weekly/monthly, default daily)

busiest_stops — Returns the busiest stops by total boardings or alightings.
  Args: start_date, end_date, route_id (optional), top_n, metric (boardings/alightings)

service_change_impact — Analysis of ridership impact before and after a service change.
  Args: route_id, change_date (YYYY-MM-DD), window_days (default 30)

get_overcrowded_routes — Identifies overcrowded routes by King County Metro's definition.
  Args: service_change_num, time_period (optional, e.g. AM Peak/PM Peak), top_n (default 10)

compare_routes — Compares multiple routes side-by-side.
  Args: route_ids (comma-separated, e.g. "40,7,E Line"), start_date, end_date

declining_routes — Identifies routes with significant ridership decline.
  Args: comparison_months (default 3), threshold_pct (default -10), min_trips (default 100)

crowding_by_time_period — Analyzes crowding patterns by time of day.
  Args: route_id (optional), start_date, end_date

route_by_direction — Compares inbound vs outbound performance for a route.
  Args: route_id, start_date, end_date

ridership_by_day_type — Analyzes ridership by day type (Weekday/Saturday/Sunday/Holiday).
  Args: route_id (optional), start_date, end_date
"""

EXAMPLE_QUERIES = [
    "Which stops had highest boardings on weekdays?",
    "Show crowding for Route 40 during AM Peak",
    "Which routes had most ridership in 2025?",
    "Compare inbound vs outbound load for Route 7",
    "Show top 5 routes by ridership",
    "Show stops in fare zone 24",
]

BLOCKED_KEYWORDS = re.compile(
    r"\b(DROP|DELETE|UPDATE|INSERT|TRUNCATE|ALTER|EXEC|EXECUTE|UNION|"
    r"CREATE|REPLACE|GRANT|REVOKE|pg_read_file)\b",
    re.IGNORECASE,
)

SECURITY_ATTACK_TESTS = {
    "SQL injection":    "1' OR '1'='1",
    "DROP statement":   "DROP TABLE trips",
    "DELETE statement": "DELETE FROM trips WHERE 1=1",
    "Stacked query":    "Route 1; DROP TABLE trips;--",
    "Empty input":      "",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _visualize(tool_name: str | None, df: pd.DataFrame | None):
    """Generate a Plotly figure from a tool result DataFrame, or return None."""
    if tool_name is None or df is None or df.empty:
        return None

    cfg = VisualizationAgent.CHART_CONFIG.get(tool_name)
    if cfg is None:
        return None

    # Graceful column fallback
    if cfg["x"] not in df.columns or cfg["y"] not in df.columns:
        str_cols = [c for c in df.columns if df[c].dtype == object]
        num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        if not str_cols or not num_cols:
            return None
        cfg = {**cfg, "x": str_cols[0], "y": num_cols[0]}

    return viz_agent.generate({"data": df, **cfg})


def get_agent_result(user_input: str) -> dict:
    """
    Run the LLM + tool pipeline for a user message.

    Returns
    -------
    dict with keys:
        text : str             — markdown answer
        df   : DataFrame|None  — table to display
        fig  : Figure|None     — Plotly chart to display
    """
    print("\n*** ────────────────────────────────────────── ***\n")

    messages = [SystemMessage(SYSTEM_PROMPT), HumanMessage(user_input)]

    # ── LLM call ──────────────────────────────────────────────────────────────
    try:
        response = llm.invoke(messages)
        answer = response.content
    except Exception as exc:
        return {"text": f"⚠️ LLM error: {exc}", "df": None, "fig": None}

    used_tool_name: str | None = None
    chosen_df: pd.DataFrame | None = None

    # ── Tool execution ────────────────────────────────────────────────────────
    is_rejected = "I am not authorized" in answer or "Please specify" in answer

    if not is_rejected and response.tool_calls:
        print("Handling tool invocations:", response.tool_calls)
        answer = ""
        try:
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"].lower()
                tool = TOOL_MAP.get(tool_name)
                if tool is None:
                    answer += f"⚠️ Unknown tool: `{tool_name}`\n"
                    continue

                if used_tool_name is None:
                    used_tool_name = tool.name

                st.session_state.agent_log.append(
                    {"tool": tool_name, "action": str(tool_call.get("args", {}))}
                )

                result_text, result_df = tool.invoke(tool_call["args"])
                answer += str(result_text) + "\n"

                if result_df is not None and not result_df.empty and chosen_df is None:
                    chosen_df = result_df

        except Exception as exc:
            answer = f"⚠️ Tool error: {exc}"

    # ── Visualization ─────────────────────────────────────────────────────────
    fig = _visualize(used_tool_name, chosen_df)
    if fig is None and chosen_df is not None:
        print(f"No chart config for tool '{used_tool_name}'.")

    return {"text": answer.strip(), "df": chosen_df, "fig": fig}


def display_messages():
    """Render the full chat history using custom chat bubbles."""
    for idx, msg in enumerate(st.session_state.messages):
        role = "user" if msg["role"] == "user" else "assistant"
        bubble_class = "chat-bubble-user" if role == "user" else "chat-bubble-assistant"
        # Escape content for safe HTML rendering
        safe_content = str(msg["content"]).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        st.markdown(
            f'<div class="{bubble_class}">{safe_content}</div>',
            unsafe_allow_html=True,
        )
        if msg.get("fig") is not None:
            st.plotly_chart(
                msg["fig"], use_container_width=True,
                theme=None, key=f"fig_{idx}"
            )
        copy_button(
            msg["content"],
            icon="st",
            key=f"copy_btn_{idx}",
            tooltip="Copy Message",
            copied_label="Message Copied!",
        )


# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="King County Transit Chat",
    page_icon="🚌",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* ── Base ─────────────────────────────────────── */
    .stApp {
        background-color: #ffeb00;
        color: #1a1a1a;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }

    /* ── Hero banner ──────────────────────────────── */
    .header {
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 1rem 2rem;
        margin-bottom: 1.5rem;
        background: linear-gradient(90deg, #ffeb00, #fefd98, #ffeb00);
        border-radius: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
        font-weight: 700;
        letter-spacing: 1px;
        animation: pulse 3s ease-in-out infinite;
    }
    .header-icon   { font-size: 3rem; }
    .header-text   { font-size: 2.2rem; }
    .header-subtext {
        font-size: 1rem;
        font-weight: 600;
        font-style: italic;
        color: #333;
    }

    /* ── Chat bubbles ─────────────────────────────── */
    .stChatMessage:has(.assistant_message) { background-color: #f5f5da; }
    .stChatMessage:has(.user_message)      { background-color: #fefd98; }

    /* ── Typing indicator ─────────────────────────── */
    .typing { display: flex; gap: 6px; padding: 8px 0 4px 0; }
    .typing-dot {
        width: 10px; height: 10px;
        background: #1a1a1a; border-radius: 50%;
        opacity: 0.3; animation: blink 1.2s infinite;
    }
    .typing-dot:nth-child(1) { animation-delay: 0s;   }
    .typing-dot:nth-child(2) { animation-delay: 0.3s; }
    .typing-dot:nth-child(3) { animation-delay: 0.6s; }

    /* ── Keyframes ────────────────────────────────── */
    @keyframes pulse {
        0%, 100% { filter: drop-shadow(0 0 0   rgba(0,0,0,0));     }
        50%       { filter: drop-shadow(0 0 15px #ffd600bb); }
    }
    @keyframes blink {
        0%, 80%, 100% { opacity: 0.3; }
        40%           { opacity: 1;   }
    }

    /* ── Chat bubbles (custom styled) ────────────── */
    .chat-bubble-user {
        max-width: 80%;
        padding: 14px 20px 14px 48px;
        margin: 6px 0 6px auto;
        border-radius: 24px 24px 4px 24px;
        font-size: 1rem;
        line-height: 1.5;
        position: relative;
        background-color: #1a1a1a;
        color: #ffd700;
        box-shadow: 0 3px 12px rgba(0,0,0,0.25);
        animation: fadeInUp 0.4s ease forwards;
    }
    .chat-bubble-assistant {
        max-width: 80%;
        padding: 14px 20px 14px 48px;
        margin: 6px auto 6px 0;
        border-radius: 24px 24px 24px 4px;
        font-size: 1rem;
        line-height: 1.5;
        position: relative;
        background-color: #fffde7;
        color: #1a1a1a;
        border: 2px solid #1a1a1a;
        box-shadow: 0 3px 12px rgba(0,0,0,0.25);
        animation: fadeInUp 0.4s ease forwards;
    }
    .chat-bubble-user::before {
        content: "🛺";
        position: absolute;
        left: 12px;
        top: 14px;
        font-size: 1.4rem;
    }
    .chat-bubble-assistant::before {
        content: "🚌";
        position: absolute;
        left: 12px;
        top: 14px;
        font-size: 1.4rem;
    }
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(12px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    /* Hide default streamlit chat message container styling */
    .stChatMessage { background: transparent !important; border: none !important; box-shadow: none !important; padding: 0 !important; }
    .stChatMessage:has(.assistant_message) { background: transparent !important; }
    .stChatMessage:has(.user_message)      { background: transparent !important; }

    /* ── Hide Streamlit chrome ────────────────────── */
    #MainMenu, footer, header { visibility: hidden; }

    /* ── Force sidebar permanently visible ────────── */
    [data-testid="stSidebar"] {
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        transform: translateX(0) !important;
        min-width: 320px !important;
        max-width: 320px !important;
        background-color: #1a1a1a !important;
    }
    [data-testid="stSidebar"] section {
        background-color: #1a1a1a !important;
    }
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] div {
        color: #ffeb00 !important;
    }
    [data-testid="stSidebar"] .stButton > button {
        background-color: #2a2a2a !important;
        color: #ffeb00 !important;
        border: 1px solid #555 !important;
        border-radius: 6px !important;
        font-size: 0.8rem !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background-color: #ffeb00 !important;
        color: #1a1a1a !important;
    }
    [data-testid="stSidebar"] code {
        color: #ffeb00 !important;
        background-color: #2a2a2a !important;
    }
    [data-testid="stSidebar"] hr {
        border-color: #444 !important;
    }
    /* Hide Streamlit's own collapse arrow and the sidebar resize handle */
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapseButton"] {
        display: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="header">
        <div class="header-icon">🚌</div>
        <div>
            <div class="header-text">King County Metro Chat</div>
            <div class="header-subtext">
                Smart assistant for routes, schedules &amp; transit insights
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Model & Agents ────────────────────────────────────────────────────────────
viz_agent = VisualizationAgent()

llm = ChatOllama(model="qwen3", temperature=0).bind_tools(ALL_TOOLS)

# ── Session State ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Hi! 👋 I'm your AI transit assistant. "
                "Ask me about King County buses, routes, crowding, or ridership data!"
            ),
        }
    ]
if "agent_log"    not in st.session_state: st.session_state.agent_log    = []
if "staged_query" not in st.session_state: st.session_state.staged_query = ""
if "processing"   not in st.session_state: st.session_state.processing   = False

# ── Chat Area ─────────────────────────────────────────────────────────────────
display_messages()

prompt = st.chat_input("Ask me about King County Metro routes...")

# Handle a staged query (clicked example button) OR a typed prompt
active_prompt = prompt or (st.session_state.staged_query or "")
if st.session_state.staged_query:
    st.session_state.staged_query = ""   # consume it

if active_prompt and not st.session_state.processing:
    st.session_state.messages.append({"role": "user", "content": active_prompt})

    safe_prompt = active_prompt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    st.markdown(f'<div class="chat-bubble-user">{safe_prompt}</div>', unsafe_allow_html=True)

    typing_placeholder = st.empty()
    typing_placeholder.markdown(
        """
        <div class="chat-bubble-assistant">
            <div class="typing">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    result = get_agent_result(active_prompt)

    safe_answer = str(result["text"]).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    typing_placeholder.markdown(f'<div class="chat-bubble-assistant">{safe_answer}</div>', unsafe_allow_html=True)

    if result.get("fig") is not None:
        st.plotly_chart(result["fig"], use_container_width=True, theme=None)

    st.session_state.messages.append(
        {"role": "assistant", "content": result["text"], "fig": result.get("fig")}
    )

    st.rerun()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:

    # ── Database stats ─────────────────────────────────────────────────────
    st.markdown("### 📊 Database Stats")
    try:
        summary = query_lib.get_summary()
        st.metric("Total Trips",    f"{int(summary['total_trips']):,}")
        st.metric("Unique Routes",  str(summary["unique_routes"]))
        st.metric("Date Range",     f"{summary['earliest_date']} → {summary['latest_date']}")
    except Exception as exc:
        st.error(f"Stats unavailable: {exc}")

    st.markdown("---")

    # ── Example queries ────────────────────────────────────────────────────
    st.markdown("### 💡 Example Queries")
    for example in EXAMPLE_QUERIES:
        if st.button(example, key=f"ex_{example}", use_container_width=True):
            st.session_state.staged_query = example
            st.rerun()

    st.markdown("---")

    # ── Agent trace ────────────────────────────────────────────────────────
    st.markdown("### 🤖 Agent Trace")
    recent_logs = st.session_state.agent_log[-5:]
    if recent_logs:
        for log in recent_logs:
            st.markdown(f"🔧 **{log.get('tool', 'tool')}**: {log.get('action', '')}")
    else:
        st.caption("No tool calls yet.")

    st.markdown("---")

    # ── Tools loaded ───────────────────────────────────────────────────────
    st.markdown("### 🛠️ Tools Loaded")
    for tool in ALL_TOOLS:
        st.caption(f"• `{tool.name}`")

    st.markdown("---")

    # ── Security tester ────────────────────────────────────────────────────
    with st.expander("🛡️ Security Tester", expanded=False):
        st.caption("Test how the app handles malicious inputs.")

        selected_test = st.selectbox(
            "Pick an attack vector:",
            list(SECURITY_ATTACK_TESTS.keys()),
            key="sec_test_select",
        )
        test_value = SECURITY_ATTACK_TESTS.get(selected_test, "")
        st.code(test_value if test_value else "(empty string)", language="text")

        if st.button("▶ Run Test", key="sec_run_btn", use_container_width=True):
            if not test_value.strip():
                st.error("❌ Blocked — Input is empty")
            elif len(test_value) > 2000:
                st.error(f"❌ Blocked — Too long: {len(test_value)} chars")
            elif BLOCKED_KEYWORDS.search(test_value):
                found = BLOCKED_KEYWORDS.findall(test_value)
                st.error(f"❌ Blocked — Dangerous keyword(s): {found}")
            else:
                st.success("✅ Passed — Input looks safe")
        # Manual input test
        st.markdown("**Or type your own:**")
        custom_input = st.text_input("Custom test input:", key="sec_custom_input", placeholder="Type anything...")
        if st.button("▶ Test Custom", key="sec_custom_btn", use_container_width=True) and custom_input:
            import re
            BLOCKED = re.compile(
                r"\b(DROP|DELETE|UPDATE|INSERT|TRUNCATE|ALTER|EXEC|EXECUTE"
                r"|UNION|CREATE|REPLACE|GRANT|REVOKE|pg_read_file)\b",
                re.IGNORECASE,
            )
            if not custom_input.strip():
                st.error("❌ Blocked — Input is empty")
            elif len(custom_input) > 2000:
                st.error(f"❌ Blocked — Too long ({len(custom_input)} chars)")
            elif BLOCKED.search(custom_input):
                found = BLOCKED.findall(custom_input)
                st.error(f"❌ Blocked — Dangerous keyword: {found}")
            else:
                st.success("✅ Passed — Input would proceed to pipeline")

visualize = _visualize