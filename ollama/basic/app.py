import sys
import os

# Add project root to Python path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import streamlit as st
import time
from agents.orchestrator import TransitOrchestrator
from agents.database import DatabaseManager

# ── Teammate's LangChain imports (from ollama/langchain_tools/) ──────────────
LANGCHAIN_AVAILABLE = False
_lc_err_msg = ""
try:
    from langchain_core.messages import SystemMessage, HumanMessage
    from langchain_ollama import ChatOllama

    # Add langchain_tools folder so query_tools and query are importable
    LC_TOOLS_PATH = os.path.join(PROJECT_ROOT, "ollama", "langchain_tools")
    if LC_TOOLS_PATH not in sys.path:
        sys.path.insert(0, LC_TOOLS_PATH)

    from query_tools import TOOL_DICT, SUPPORTED_TOOL_MESSAGE

    # LLM with tools bound — exactly as teammate set it up in langchain_tools/app.py
    _lc_llm = ChatOllama(model="llama3.2", temperature=0).bind_tools(
        list(TOOL_DICT.values())
    )
    LANGCHAIN_AVAILABLE = True
except Exception as _err:
    _lc_err_msg = str(_err)


def _run_langchain(prompt: str) -> str:
    """
    Runs the teammate's LangChain pipeline exactly as written in
    ollama/langchain_tools/app.py. No new agents — uses TOOL_DICT and _lc_llm directly.
    """
    system_instructions = (
        "You are a helpful assistant focused on King County Metro. "
        "Answer without mentioning tools nor dictionaries. "
        f"If you do not have the tools to answer the question, "
        f"reply with '{SUPPORTED_TOOL_MESSAGE}' only."
    )

    messages = [SystemMessage(system_instructions), HumanMessage(prompt)]
    response = _lc_llm.invoke(messages)
    answer = response.content

    if response.tool_calls:
        messages.append(response)
        for tool_call in response.tool_calls:
            selected_tool = TOOL_DICT[tool_call["name"].lower()]
            tool_msg = selected_tool.invoke(tool_call)
            messages.append(tool_msg)
        # Second call to synthesize tool output into plain English
        answer = ChatOllama(model="llama3.2", temperature=0).invoke(messages).content

    return answer


# --- Page config ---
st.set_page_config(
    page_title="King County Transit Chat", page_icon="🚖", layout="centered"
)

# --- Custom CSS (taxi theme + agent system) — UNCHANGED ---
st.markdown(
    """
<style>
.stApp {
    background-color: #ffd700;
    background-image: repeating-linear-gradient(
        135deg,
        #000000 0px,
        #000000 25px,
        #ffd700 25px,
        #ffd700 100px
    );
    color: #1a1a1a;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    user-select: none;
}
.header {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1rem 2rem;
    margin-bottom: 1.5rem;
    background: linear-gradient(90deg, #ffea00, #ffd600);
    border-radius: 20px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    color: #1a1a1a;
    font-weight: 700;
    letter-spacing: 1px;
    animation: pulse 3s ease-in-out infinite;
}
.header-icon { font-size: 3rem; animation: bounce 2s infinite; }
@keyframes pulse { 0%, 100% { filter: drop-shadow(0 0 0 rgba(0,0,0,0)); } 50% { filter: drop-shadow(0 0 15px #ffd600bb); } }
@keyframes bounce { 0%,100%{transform:translateY(0);}50%{transform:translateY(-7px);} }
.header-text { font-size: 2.2rem; }
.header-subtext { font-size: 1rem; margin-top: -0.3rem; font-weight: 600; font-style: italic; color: #333; }
.chat-message {
    max-width: 80%;
    padding: 14px 20px 14px 48px;
    margin-bottom: 14px;
    border-radius: 24px;
    font-size: 1.1rem;
    line-height: 1.4;
    position: relative;
    box-shadow: 0 3px 12px rgba(0,0,0,0.25);
    animation: fadeInUp 0.4s ease forwards;
    user-select: text;
}
.chat-message.user {
    margin-left: auto;
    background-color: #1a1a1a;
    color: #ffd700;
    border-bottom-right-radius: 4px;
}
.chat-message.assistant {
    background-color: #ffd700;
    color: #1a1a1a;
    border: 2px solid #1a1a1a;
    border-bottom-left-radius: 4px;
}
.chat-message.user::before { content: "🛺"; position: absolute; left: 16px; top: 50%; transform: translateY(-50%); font-size: 1.8rem; }
.chat-message.assistant::before { content: "🚖"; position: absolute; left: 16px; top: 50%; transform: translateY(-50%); font-size: 1.8rem; }
@keyframes fadeInUp { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
.agent-step {
    background: rgba(255, 215, 0, 0.3);
    border: 1px solid #1a1a1a;
    border-radius: 8px;
    padding: 8px;
    margin: 4px 0;
    font-size: 0.85em;
    color: #1a1a1a;
}
.reward-badge {
    background: #1a1a1a;
    color: #ffd700;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.75em;
    font-weight: 700;
}
.dataframe { background: rgba(255,255,255,0.95); border-radius: 8px; }
.typing { display: flex; gap: 6px; margin-top: 6px; padding-left: 48px; }
.typing-dot { width: 10px; height: 10px; background: #1a1a1a; border-radius: 50%; opacity: 0.3; animation: blink 1.2s infinite; }
.typing-dot:nth-child(1) { animation-delay: 0s; }
.typing-dot:nth-child(2) { animation-delay: 0.3s; }
.typing-dot:nth-child(3) { animation-delay: 0.6s; }
@keyframes blink { 0%, 80%, 100% { opacity: 0.3; } 40% { opacity: 1; } }
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stSidebarCollapseButton"] { display: none !important; }
</style>
""",
    unsafe_allow_html=True,
)

# --- Header (unchanged) ---
st.markdown(
    """
<div class="header">
    <div class="header-icon">🚖</div>
    <div>
        <div class="header-text">King County Transit Chat</div>
        <div class="header-subtext">AI-powered transit insights from PostgreSQL</div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

st.caption("Ask about routes, schedules, delays, ridership — powered by data agents 🚦")


# --- Load orchestrator (unchanged) ---
@st.cache_resource
def load_orchestrator():
    db = DatabaseManager()
    return TransitOrchestrator(db_manager=db)


try:
    orchestrator = load_orchestrator()
except Exception as e:
    st.error(f"⚠️ Database connection failed: {e}")
    st.info("💡 Check PostgreSQL is running and environment variables are set.")
    st.stop()

# --- Session state (unchanged + lc_messages added) ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Hi! 👋 I'm your AI transit assistant. Ask me about King County buses, routes, crowding, or ridership data!",
        }
    ]
if "lc_messages" not in st.session_state:
    st.session_state.lc_messages = [
        {
            "role": "assistant",
            "content": "Hi! 👋 I'm your LangChain tool-calling assistant. I use bound tools to fetch live transit data. Try: 'What is the operation period?'",
        }
    ]
if "agent_log" not in st.session_state:
    st.session_state.agent_log = []
if "example_text" not in st.session_state:
    st.session_state.example_text = ""
if "staged_query" not in st.session_state:
    st.session_state.staged_query = ""
if "lc_staged_query" not in st.session_state:
    st.session_state.lc_staged_query = ""

# --- Sidebar (unchanged + LangChain status appended) ---
with st.sidebar:
    st.markdown("### 📊 Database Stats")
    try:
        stats = orchestrator.get_data_stats()
        for k, v in stats.items():
            st.metric(k, v)
    except Exception as e:
        st.error(f"Stats unavailable: {e}")

    st.markdown("### 💡 Example Queries")
    examples = [
        "Which stops had highest boardings on weekdays?",
        "Show crowding for Route 1 during AM Peak",
        "Which routes had most delays?",
        "Compare inbound vs outbound load",
        "Predict peak load for Route 677",
        "Show stops in fare zone 24",
    ]
    for ex in examples:
        if st.button(ex, key=ex, use_container_width=True):
            st.session_state.staged_query = ex
            st.rerun()

    st.markdown("### 🤖 Agent Trace")
    for log in st.session_state.agent_log[-5:]:
        st.markdown(
            f'<div class="agent-step">🔧 <b>{log["agent"]}</b>: {log["action"]} '
            f'<span class="reward-badge">R:{log["reward"]:.2f}</span></div>',
            unsafe_allow_html=True,
        )

    # LangChain status — new addition at bottom of sidebar
    st.markdown("---")
    st.markdown("### 🔗 LangChain Status")
    if LANGCHAIN_AVAILABLE:
        st.success("✅ Ready")
        st.caption("Bound tools: " + ", ".join(f"`{k}`" for k in TOOL_DICT))
    else:
        st.warning("⚠️ Not available")
        st.caption(f"`{_lc_err_msg}`")
        st.caption("Fix: `pip install langchain langchain-ollama`")

    # ── Security Tester ───────────────────────────────────────────────────
    # st.markdown("---")
    # with st.expander("🛡️ Security Tester", expanded=False):
    #     st.caption("Test how the app handles malicious or invalid inputs.")

    #     # Pre-built attack test cases
    #     st.markdown("**Quick tests:**")
    #     attack_tests = {
    #         "SQL injection":        "1' OR '1'='1",
    #         "DROP statement":       "DROP TABLE trips",
    #         "DELETE statement":     "DELETE FROM trips WHERE 1=1",
    #         "Stacked query":        "Route 1; DROP TABLE trips;--",
    #         "Comment bypass":       "1'--",
    #         "UNION attack":         "1' UNION SELECT * FROM trips--",
    #         "Empty input":          "",
    #         "Too long (2001 chars)": "a" * 2001,
    #         "Normal safe query":    "Which stops had highest boardings?",
    #     }

    #     selected_test = st.selectbox(
    #         "Pick an attack vector:",
    #         list(attack_tests.keys()),
    #         key="sec_test_select"
    #     )
    #     test_value = attack_tests[selected_test]
    #     st.code(test_value if test_value else "(empty string)", language="text")

    #     if st.button("▶ Run Test", key="sec_run_btn", use_container_width=True):
    #         import re

    #         # ── Same checks used in the real pipeline ────────────────────
    #         BLOCKED = re.compile(
    #             r"\b(DROP|DELETE|UPDATE|INSERT|TRUNCATE|ALTER|EXEC|EXECUTE"
    #             r"|UNION|CREATE|REPLACE|GRANT|REVOKE|pg_read_file)\b",
    #             re.IGNORECASE,
    #         )
    #         results = []

    #         # Check 1: empty
    #         if not test_value.strip():
    #             results.append(("❌ Blocked", "Input is empty"))
    #         # Check 2: length
    #         elif len(test_value) > 2000:
    #             results.append(("❌ Blocked", f"Too long: {len(test_value)} chars (max 2000)"))
    #         # Check 3: destructive keywords
    #         elif BLOCKED.search(test_value):
    #             found = BLOCKED.findall(test_value)
    #             results.append(("❌ Blocked", f"Dangerous keyword detected: {found}"))
    #         else:
    #             results.append(("✅ Passed", "Input looks safe — would proceed to LLM"))

    #         # Check 4: entity injection simulation
    #         # Simulate what analysis_agent does with a route entity
    #         fake_route = re.sub(r"[^\w\s]", "", test_value)[:20]  # strip non-alphanumeric
    #         if fake_route != test_value.strip()[:20]:
    #             results.append(("🔒 Sanitized", f"Entity value cleaned: '{test_value[:20]}' → '{fake_route}'"))
    #         else:
    #             results.append(("✅ Entity OK", f"Entity value unchanged: '{fake_route}'"))

    #         # Display results
    #         st.markdown("**Results:**")
    #         for status, message in results:
    #             if status.startswith("❌"):
    #                 st.error(f"{status} — {message}")
    #             elif status.startswith("🔒"):
    #                 st.warning(f"{status} — {message}")
    #             else:
    #                 st.success(f"{status} — {message}")

    #     # Manual input test
    #     st.markdown("**Or type your own:**")
    #     custom_input = st.text_input("Custom test input:", key="sec_custom_input", placeholder="Type anything...")
    #     if st.button("▶ Test Custom", key="sec_custom_btn", use_container_width=True) and custom_input:
    #         import re
    #         BLOCKED = re.compile(
    #             r"\b(DROP|DELETE|UPDATE|INSERT|TRUNCATE|ALTER|EXEC|EXECUTE"
    #             r"|UNION|CREATE|REPLACE|GRANT|REVOKE|pg_read_file)\b",
    #             re.IGNORECASE,
    #         )
    #         if not custom_input.strip():
    #             st.error("❌ Blocked — Input is empty")
    #         elif len(custom_input) > 2000:
    #             st.error(f"❌ Blocked — Too long ({len(custom_input)} chars)")
    #         elif BLOCKED.search(custom_input):
    #             found = BLOCKED.findall(custom_input)
    #             st.error(f"❌ Blocked — Dangerous keyword: {found}")
    #         else:
    #             st.success("✅ Passed — Input would proceed to pipeline")

    # ── Security Tester (reduced to 5 checks) ───────────────────────────────
    st.markdown("---")
    with st.expander("🛡️ Security Tester", expanded=False):
        st.caption("Test how the app handles malicious or invalid inputs.")

        # Pre-built attack test cases
        attack_tests = {
            "SQL injection": "1' OR '1'='1",
            "DROP statement": "DROP TABLE trips",
            "DELETE statement": "DELETE FROM trips WHERE 1=1",
            "Stacked query": "Route 1; DROP TABLE trips;--",
            "Empty input": "",
            # "Too long (2001 chars)": "a" * 2001,
            # "Normal safe query":    "Which stops had highest boardings?",
        }

        selected_test = st.selectbox(
            "Pick an attack vector:", list(attack_tests.keys()), key="sec_test_select"
        )
        test_value = attack_tests[selected_test]
        st.code(test_value if test_value else "(empty string)", language="text")

        if st.button("▶ Run Test", key="sec_run_btn", use_container_width=True):
            import re

            # Combined destructive/keyword check
            BLOCKED = re.compile(
                r"\b(DROP|DELETE|UPDATE|INSERT|TRUNCATE|ALTER|EXEC|EXECUTE|UNION|CREATE|REPLACE|GRANT|REVOKE|pg_read_file)\b",
                re.IGNORECASE,
            )
            results = []

            # Check 1: empty input
            if not test_value.strip():
                results.append(("❌ Blocked", "Input is empty"))
            # Check 2: length
            elif len(test_value) > 2000:
                results.append(
                    ("❌ Blocked", f"Too long: {len(test_value)} chars (max 2000)")
                )
            # Check 3: dangerous keywords
            elif BLOCKED.search(test_value):
                found = BLOCKED.findall(test_value)
                results.append(("❌ Blocked", f"Dangerous keyword detected: {found}"))
            # Check 4: entity injection / sanitization
            fake_route = re.sub(r"[^\w\s]", "", test_value)[:20]
            if fake_route != test_value.strip()[:20]:
                results.append(
                    (
                        "🔒 Sanitized",
                        f"Entity value cleaned: '{test_value[:20]}' → '{fake_route}'",
                    )
                )
            # Check 5: safe input passes
            else:
                results.append(("✅ Passed", "Input looks safe — would proceed to LLM"))

            # Display results
            st.markdown("**Results:**")
            for status, message in results:
                if status.startswith("❌"):
                    st.error(f"{status} — {message}")
                elif status.startswith("🔒"):
                    st.warning(f"{status} — {message}")
                else:
                    st.success(f"{status} — {message}")
        # Manual input test
        st.markdown("**Or type your own:**")
        custom_input = st.text_input(
            "Custom test input:", key="sec_custom_input", placeholder="Type anything..."
        )
        if (
            st.button("▶ Test Custom", key="sec_custom_btn", use_container_width=True)
            and custom_input
        ):
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


# --- Typing indicator (unchanged) ---
def show_typing():
    st.markdown(
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


# =============================================================================
# TABS — Tab 1 is byte-for-byte identical to original app.py logic
# =============================================================================
tab_agents, tab_langchain = st.tabs(["🤖 Agent Pipeline", "🔗 LangChain Tools"])

# ── TAB 1: Original agent pipeline — NOTHING changed ─────────────────────────
with tab_agents:
    for i, msg in enumerate(st.session_state.messages):
        role = msg["role"]
        content = msg["content"]
        st.markdown(
            f'<div class="chat-message {role}">{content}</div>', unsafe_allow_html=True
        )
        if msg.get("chart"):
            st.plotly_chart(msg["chart"], use_container_width=True, key=f"chart_{i}")
        if msg.get("table") is not None:
            st.dataframe(msg["table"], use_container_width=True, key=f"table_{i}")

    if st.session_state.staged_query:
        user_msg = st.session_state.staged_query
        st.session_state.staged_query = ""
        st.session_state.messages.append({"role": "user", "content": user_msg})
        st.rerun()

    prompt = st.chat_input(
        "Ask about buses, routes, delays, or ridership…", key="chat_input"
    )
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.rerun()

    if st.session_state.messages[-1]["role"] == "user":
        show_typing()
        time.sleep(0.8)
        try:
            result = orchestrator.run(st.session_state.messages[-1]["content"])
            st.session_state.agent_log.extend(result.get("agent_trace", []))
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": result["response"],
                    "chart": result.get("chart"),
                    "table": result.get("table"),
                }
            )
        except Exception as e:
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": f"⚠️ Error processing query: {e}\n\nPlease check database connection and try again.",
                }
            )
        st.rerun()

# ── TAB 2: Teammate's LangChain tool-calling pipeline ────────────────────────
with tab_langchain:
    if not LANGCHAIN_AVAILABLE:
        st.warning(
            f"⚠️ LangChain unavailable: `{_lc_err_msg}`\n\n"
            "Install with:\n```\npip install langchain langchain-ollama\n```"
        )
    else:
        st.info(
            "Uses **LangChain tool-binding** — the LLM decides which tool to call "
            "based on your question, then explains the result in plain English.",
            icon="🔗",
        )

        for i, msg in enumerate(st.session_state.lc_messages):
            role = msg["role"]
            content = msg["content"]
            st.markdown(
                f'<div class="chat-message {role}">{content}</div>',
                unsafe_allow_html=True,
            )

        if st.session_state.lc_staged_query:
            user_msg = st.session_state.lc_staged_query
            st.session_state.lc_staged_query = ""
            st.session_state.lc_messages.append({"role": "user", "content": user_msg})
            st.rerun()

        lc_prompt = st.chat_input("Ask the LangChain tool agent…", key="lc_chat_input")
        if lc_prompt:
            st.session_state.lc_messages.append({"role": "user", "content": lc_prompt})
            st.rerun()

        if st.session_state.lc_messages[-1]["role"] == "user":
            show_typing()
            time.sleep(0.8)
            try:
                answer = _run_langchain(st.session_state.lc_messages[-1]["content"])
                st.session_state.lc_messages.append(
                    {"role": "assistant", "content": answer}
                )
            except Exception as e:
                st.session_state.lc_messages.append(
                    {"role": "assistant", "content": f"⚠️ LangChain error: {e}"}
                )
            st.rerun()

        st.markdown("---")
        st.markdown("#### 🛠️ Bound Tools")
        for name in TOOL_DICT:
            st.markdown(f"- `{name}`")
