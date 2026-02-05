import streamlit as st
import random
import time
import ollama

# --- Page config ---
st.set_page_config(page_title="King County Transit Chat", page_icon="🚖", layout="centered")

# --- Custom CSS for updated diagonal zebra background + glassmorphism error ---
st.markdown(
    """
    <style>
    /* App background: yellow with thick diagonal black stripes */
    .stApp {
        background-color: #ffd700; /* taxi yellow */
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

    /* Header container */
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
    @keyframes pulse {
        0%, 100% { filter: drop-shadow(0 0 0 rgba(0,0,0,0)); }
        50% { filter: drop-shadow(0 0 15px #ffd600bb); }
    }
    @keyframes bounce { 0%,100%{transform:translateY(0);}50%{transform:translateY(-7px);} }
    .header-text { font-size: 2.2rem; }
    .header-subtext { font-size: 1rem; margin-top: -0.3rem; font-weight: 600; font-style: italic; color: #333; }

    /* Chat container scroll */
    .chat-container { max-height: 520px; overflow-y: auto; padding-right: 10px; margin-bottom: 1.5rem; }
    .chat-container::-webkit-scrollbar { width: 8px; }
    .chat-container::-webkit-scrollbar-thumb { background-color: #1a1a1a; border-radius: 10px; }
    .chat-container::-webkit-scrollbar-track { background: transparent; }

    /* Message bubbles */
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

    /* User bubble */
    .chat-message.user {
        margin-left: auto;
        background-color: #1a1a1a; /* black */
        color: #ffd700; /* yellow text */
        border-bottom-right-radius: 4px;
    }
    /* Assistant bubble */
    .chat-message.assistant {
        background-color: #ffd700; /* yellow */
        color: #1a1a1a; /* black text */
        border: 2px solid #1a1a1a;
        border-bottom-left-radius: 4px;
    }

    /* Bubble icons */
    .chat-message.user::before { content: "🛺 "; position: absolute; left: 16px; top: 50%; transform: translateY(-50%); font-size: 1.8rem; }
    .chat-message.assistant::before { content: "🚖 "; position: absolute; left: 16px; top: 50%; transform: translateY(-50%); font-size: 1.8rem; }

    /* Fade-in animation */
    @keyframes fadeInUp { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }

    /* Typing indicator */
    .typing { display: flex; gap: 6px; margin-top: 6px; padding-left: 48px; }
    .typing-dot {
        width: 10px; height: 10px; background: #1a1a1a;
        border-radius: 50%; opacity: 0.3; animation: blink 1.2s infinite;
    }
    .typing-dot:nth-child(1) { animation-delay: 0s; }
    .typing-dot:nth-child(2) { animation-delay: 0.3s; }
    .typing-dot:nth-child(3) { animation-delay: 0.6s; }
    @keyframes blink { 0%, 80%, 100% { opacity: 0.3; } 40% { opacity: 1; } }

    /* Glassmorphism error messages */
    /* Glassmorphism error messages - improved visibility */
.stAlert {
    background: rgba(220, 20, 60, 0);  /* dark red with high opacity */
    /*backdrop-filter: blur(10px);*/
    color: #000000;  /* bright white text */
    font-weight: 700;
    border-radius: 14px;
    padding: 12px 20px;
    margin: 12px 0;
    border: 1px solid rgba(255, 255, 255, 0.6);
    box-shadow: 0 4px 15px rgba(0,0,0,0.4); /* stronger shadow */
    text-align: center;
}

    /* Hide Streamlit footer/menu/header */
    #MainMenu, footer, header { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Header ---
st.markdown(
    """
    <div class="header">
        <div class="header-icon">🚖</div>
        <div>
            <div class="header-text">King County Transit Chat</div>
            <div class="header-subtext">Smart assistant for routes, schedules & transit insights</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption("Ask me anything about King County transit — routes, schedules, delays, or ridership data 🚦")

# --- Initialize chat history ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi! 👋 I’m your transit assistant. Ask me about buses, routes, or any transit question!"}
    ]

# --- Chat container ---
chat_container = st.container()
with chat_container:
    for msg in st.session_state.messages:
        role = msg["role"]
        content = msg["content"]
        st.markdown(f'<div class="chat-message {role}">{content}</div>', unsafe_allow_html=True)

# --- Typing indicator ---
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

# --- Chat input ---
prompt = st.chat_input("Ask about buses, routes, traffic, or transit trends…")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()

if st.session_state.messages[-1]["role"] == "user":
    show_typing()
    time.sleep(1.2)

    try:
        response = ollama.chat(
            model="llama2",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful, concise assistant focused on King County transit. "
                        "Answer clearly about routes, schedules, delays, ridership, and transportation trends."
                    )
                },
                *st.session_state.messages
            ]
        )

        assistant_text = response["message"]["content"]

    except Exception:
        assistant_text = (
            "⚠️ I’m having trouble connecting to the local transit AI engine. "
            "Please make sure Ollama is running."
        )

    st.session_state.messages.append(
        {"role": "assistant", "content": assistant_text}
    )
    st.rerun()