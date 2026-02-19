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

# --- Page config ---
st.set_page_config(page_title="King County Transit Chat", page_icon="🚖", layout="centered")

# --- Custom CSS (taxi theme + agent system) ---
st.markdown("""
<style>
/* App background: yellow with thick diagonal black stripes */
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

/* Header */
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

/* Chat messages */
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

/* Agent trace badge */
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

/* Data tables and charts */
.dataframe { background: rgba(255,255,255,0.95); border-radius: 8px; }

/* Typing indicator */
.typing { display: flex; gap: 6px; margin-top: 6px; padding-left: 48px; }
.typing-dot { width: 10px; height: 10px; background: #1a1a1a; border-radius: 50%; opacity: 0.3; animation: blink 1.2s infinite; }
.typing-dot:nth-child(1) { animation-delay: 0s; }
.typing-dot:nth-child(2) { animation-delay: 0.3s; }
.typing-dot:nth-child(3) { animation-delay: 0.6s; }
@keyframes blink { 0%, 80%, 100% { opacity: 0.3; } 40% { opacity: 1; } }

/* Hide Streamlit branding and sidebar collapse button entirely */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stSidebarCollapseButton"] { display: none !important; }

</style>
""", unsafe_allow_html=True)

# --- Header ---
st.markdown("""
<div class="header">
    <div class="header-icon">🚖</div>
    <div>
        <div class="header-text">King County Transit Chat</div>
        <div class="header-subtext">AI-powered transit insights from PostgreSQL</div>
    </div>
</div>
""", unsafe_allow_html=True)

st.caption("Ask about routes, schedules, delays, ridership — powered by data agents 🚦")

# --- Load orchestrator ---
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

# --- Initialize session state ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi! 👋 I'm your AI transit assistant. Ask me about King County buses, routes, crowding, or ridership data!"}
    ]
if "agent_log" not in st.session_state:
    st.session_state.agent_log = []
if "example_text" not in st.session_state:
    st.session_state.example_text = ""
if "staged_query" not in st.session_state:
    st.session_state.staged_query = ""

# --- Sidebar: always visible, no toggle ---
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
            unsafe_allow_html=True
        )

# --- Display chat messages ---
for i, msg in enumerate(st.session_state.messages):
    role = msg["role"]
    content = msg["content"]
    st.markdown(f'<div class="chat-message {role}">{content}</div>', unsafe_allow_html=True)
    if msg.get("chart"):
        st.plotly_chart(msg["chart"], 
            use_container_width=True,
            key=f"chart_{i}")   # ✅ added unique key)
    if msg.get("table") is not None:
        st.dataframe(msg["table"],
            use_container_width=True,
            key=f"table_{i}"
        )

# --- Typing indicator function ---
def show_typing():
    st.markdown("""
    <div class="chat-message assistant">
        <div class="typing">
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# --- Chat input ---
# Auto-send staged query immediately (no manual typing needed)
if st.session_state.staged_query:
    user_msg = st.session_state.staged_query
    st.session_state.staged_query = ""
    st.session_state.messages.append({"role": "user", "content": user_msg})
    st.rerun()

prompt = st.chat_input(
    "Ask about buses, routes, delays, or ridership…",
    key="chat_input",
)
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()

# Process last message if it's from user
if st.session_state.messages[-1]["role"] == "user":
    show_typing()
    time.sleep(0.8)
    try:
        result = orchestrator.run(st.session_state.messages[-1]["content"])
        st.session_state.agent_log.extend(result.get("agent_trace", []))
        st.session_state.messages.append({
            "role": "assistant",
            "content": result["response"],
            "chart": result.get("chart"),
            "table": result.get("table"),
        })
    except Exception as e:
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"⚠️ Error processing query: {e}\n\nPlease check database connection and try again."
        })
    st.rerun()