# app.py

# ── Directory Setup ────────────────────────────────────────────────────
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ── Imports ─────────────────────────────────────────────────────────
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_ollama import ChatOllama
import pandas as pd
import streamlit as st
from st_copy import copy_button

from visualization_agent import CHART_CONFIG, VisualizationAgent
from planner_query_tools import *

# ── Variables & Functions ─────────────────────────────────────────────────────────────────
TOOL_MAP = {tool.name.lower(): tool for tool in ALL_TOOLS}

# streamlit: display messages
def display_messages():
    """Display all messages in the chat history"""
    button_count = 0  # count for unique copy buttons

    for msg in st.session_state.messages:
        author = "user" if msg["role"] == "user" else "assistant"
        with st.chat_message(author):
            st.html(f"<span class='{author}_message'></span>")
            st.write(msg["content"])

            # Render chart if present
            if msg.get("fig") is not None:
                st.plotly_chart(msg["fig"], width="stretch", theme=None, key=f"fig_{button_count}")

            # Add a copy button
            button_key = f"copy_btn_{button_count}"
            copy_button(
                msg["content"],
                icon="st",  # use Streamlit's code-block icon
                key=button_key,
                tooltip="Copy Message",
                copied_label="Message Copied!",
            )
            button_count += 1

# visualization: create visualization
def visualize(tool_name: str, df: pd.DataFrame):
    """Choose sensible x/y/chart_type for each tool and call VisualizationAgent."""
    
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

# modeling: run agent, handle tool calls, and generate visualization
def get_agent_result(user_input: str) -> dict:
    """
    Returns dict with keys:
      - text: str  (markdown answer)
      - df: pd.DataFrame or None  (table to display)
      - fig: plotly figure or None  (chart to display)
    """
    print("\n*** ---------------------------------------------------- ***\n")   # to separate responses for each prompt

    # Configure the invocation array
    systemInstructions = """
        You are a helpful assistant who only answers about King County Metro.
        If the user asks about any other transit systems (e.g. New York transit), state 'I am not authorized to provide information not pertaining to King County Metro.' Do not answer about any other transit systems.
        Respond 'I am not authorized to suggest updates, additions, or overwrites to the database.' if the user requests database updates, changes, additions, or overwrites.
        
        If a tool can answer the question, you MUST call the tool.
        
        If the user only specifes a day (e.g. on the 21st), respond 'Please specify the day, month, and year for the question or request.'
        If the user does not specify a start_date, use January 1st, 2025 as the baseline for the tool arguments.
        If the user does not specify an end_date, you MUST use December 31st, 2025 as the baseline for the tool arguments.
        If the user only specifies a month (e.g in May) without mentioning to start (e.g. from May) or end (e.g. until May) at that month, use the first day of the month for the year 2025 as the start_date and the last day of the month for the year 2025 as the end_date.

        If the user does not specify a change_date yet it is needed for the tool, respond 'Please specify the service change date for the question or request'.
        
        The route_id should only be the number or name of the route (e.g. 2, 40, E Line).
        If the user does not specify a route_id yet the tool needs it as an argument, respond 'Please specify the route for the question.' DO NOT USE UNSPECIFIED ROUTES.
        
        The most recent service_change_num is 253. The oldest service_change_num is 243.
        If the user does not specify a service_change_num yet the tool needs it as an argument, respond 'Please specify the service change number for the question.' DO NOT USE UNSPECIFIED SERVICE CHANGE NUMBERS.

        Here is a description of all the tools:

        top_routes_by_ridership returns the top routes by boardings for a date range.
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            top_n: Number of routes to return (default 10)
            day_code: Optional filter ('WK', 'SA', 'SU', 'HOL')
            direction: Optional filter ('I', 'O', '0')

        route_ridership_trend returns the ridership trend for a route over time.
        Args:
            route_id: Route identifier (e.g., '40', '7', 'E Line')
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            aggregation: 'daily', 'weekly', or 'monthly' (default 'daily')

        busiest_stops returns the busiest stops by total boardings or total alightings.
        Args:
                start_date: Start date
                end_date: End date
                route_id: Optional route filter
                top_n: Number of stops to return
                metric: 'boardings' or 'alightings' (default 'boardings')
        
        service_change_impact returns an analysis of ridership impact before and after a service change.
        Args:
            route_id: Route identifier
            change_date: Date of service change (YYYY-MM-DD)
            window_days: Days before/after to compare (default 30)

        get_overcrowded_routes identifies overcrowded routes based on King County Metro's definition
        Args:
            service_change_num: Service change period identifier (e.g. )
            time_period: Optional filter (e.g., 'AM Peak', 'PM Peak')
            top_n: Number of routes (default 10)

        compare_routes compares multiple routes side-by-side.
        Args:
            route_ids: Comma-separated route IDs (e.g., "40,7,E Line")
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        declining_routes identifies routes with significant ridership decline.
        Args:
            comparison_months: Months to compare (default 3)
            threshold_pct: Decline threshold as negative % (default -10)
            min_trips: Minimum trips to include (default 100)

        crowding_by_time_period analyzes crowding patterns by time of day.
        Args:
            route_id: Optional route filter
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        route_by_direction compares inbound vs outbound performance for a route.
        Args:
            route_id: Route identifier
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        ridership_by_day_type analyzes ridership by day type (Weekday/Saturday/Sunday/Holiday).            
        Args:
            route_id: Optional route filter
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)                    
    """
    systemMessages = [SystemMessage(systemInstructions),
                        HumanMessage(user_input)]

    try:
        response = llm.invoke(systemMessages)
        answer = response.content
    except Exception as e:
        answer = f"⚠️ I'm sorry, I encountered anLLM error: {e}."

    # Initialize variables for visualization
    #all_dfs = []
    used_tool_name = None
    chosen_df = None
    fig = None

    # Generate answer from LLM and tools
    if ("I am not authorized" not in answer) and ("Please specify" not in answer):  # If NOT Reject or Request Behavior
        # If the model calls a tool, handle the tool call
        if response.tool_calls:
            print("Handling tool invocation...")
            print(response.tool_calls)
        
            answer = ""
            try:
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"].lower()
                    selected_tool = TOOL_MAP[tool_name]
                    if used_tool_name is None:
                        used_tool_name = selected_tool.name

                    st.session_state.agent_log.append(
                        {"tool": tool_name, "action": str(tool_call.get("args", {}))}
                    )

                    # Execute tool with args ONLY
                    result_text, result_df = selected_tool.invoke(tool_call["args"])
                    answer += str(result_text) + "\n"

                    if result_df is not None and not result_df.empty and chosen_df is None:
                        chosen_df = result_df
            except Exception as e:
                answer = f"I'm sorry, I encountered an error during tool invocation: {e}."

    # Pick the first DataFrame and visualize it
    print("Handling visualization...")
    print(used_tool_name)
    fig = visualize(used_tool_name, chosen_df) if chosen_df is not None else None
    if fig is None:
        if chosen_df is not None:
            print(f"Could not visualize result from tool '{used_tool_name}'.")
            print(chosen_df.head())
        else:
            print("The tool does not return a DataFrame, so no visualization will be generated.")

    return {"text": answer, "df": chosen_df, "fig": fig}

# ── Page Configuration ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="King County Transit Chat", page_icon="🚌", layout="wide"
)
st.title("🚌 King County Metro Chat Assistant")
st.subheader("Your AI assistant for retrieving King Country Metro transit data")

st.markdown(
"""
<style>
.stApp {
    background-color: #ffeb00;
    color: #1a1a1a;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}
.header {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1rem 2rem;
    margin-bottom: 1.5rem;
    background: linear-gradient(90deg, #ffeb00, #fefd98, #ffeb00);
    border-radius: 20px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    color: #1a1a1a;
    font-weight: 700;
    letter-spacing: 1px;
    animation: pulse 3s ease-in-out infinite;
}
.header-icon { font-size: 3rem; }
.header-text { font-size: 2.2rem; }
.header-subtext {
    font-size: 1rem;
    font-weight: 600;
    font-style: italic;
    color: #333;
}

/* Message Bubbles */
.stChatMessage:has(.assistant_message) {
    background-color: #f5f5da
}
.stChatMessage:has(.user_message) {
    background-color: #fefd98;
}

/* Typing Indicator */
.typing { display: flex; gap: 6px; padding: 8px 0 4px 0; }
.typing-dot { width: 10px; height: 10px; background: #1a1a1a; border-radius: 50%; opacity: 0.3; animation: blink 1.2s infinite; }
.typing-dot:nth-child(1) { animation-delay: 0s; }
.typing-dot:nth-child(2) { animation-delay: 0.3s; }
.typing-dot:nth-child(3) { animation-delay: 0.6s; }

/* KeyFrames */
@keyframes pulse {
    0%, 100% { filter: drop-shadow(0 0 0 rgba(0,0,0,0)); }
    50% { filter: drop-shadow(0 0 15px #ffd600bb); }
}
@keyframes bounce {
    0%,100%{ transform:translateY(0); }
    50%{ transform:translateY(-7px); }
}
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); }
}
@keyframes blink {
    0%, 80%, 100% { opacity: 0.3; }
    40% { opacity: 1; }
}

/* Hide Streamlit footer/menu/header */
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
        <div class="header-text">King County Metro Chat</div>
        <div class="header-subtext">Smart assistant for routes, schedules & transit insights</div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

# ── Configure Models ─────────────────────────────────
viz_agent = VisualizationAgent()

llm = ChatOllama(
    model="qwen3",
    temperature=0
).bind_tools(ALL_TOOLS)

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

# ── MAIN: Process Chat ────────────────────────────────────────────────────────────────
display_messages()  # Render all messages

prompt = st.chat_input("Ask me about King County Metro routes...")
if prompt and not st.session_state.processing:
    # Handle user message
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
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

        # Get result
        result = get_agent_result(prompt)

        # Add assistant response
        typing_placeholder.write(result["text"])
        st.session_state.messages.append({
            "role": "assistant",
            "content": result["text"],
            "fig": result.get("fig"),
        })

    st.rerun()
