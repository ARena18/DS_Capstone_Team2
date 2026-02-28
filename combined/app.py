# app.py
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_ollama import ChatOllama
import streamlit as st
from st_copy import copy_button

#from query_info import SCHEMA, query_db
from planner_query_tools import top_routes_by_ridership, route_ridership_trend, busiest_stops, service_change_impact

# --- Variables & Functions ---
ALL_TOOLS = [top_routes_by_ridership, route_ridership_trend, busiest_stops, service_change_impact]
TOOL_MAP = {t.name.lower(): t for t in ALL_TOOLS}

MAX_FIX_ATTEMPTS = 5

def display_messages():
    """Display all messages in the chat history"""
    button_count = 0    # count for unique copy buttons

    for msg in st.session_state.messages:
        author = "user" if msg["role"] == "user" else "assistant"
        with st.chat_message(author):
            st.write(msg["content"])

            # Add a copy button
            button_key = f"copy_btn_{button_count}"
            copy_button(
                msg["content"],
                icon="st",  # use Streamlit's code-block icon
                key=button_key,
                tooltip="Copy Message",
                copied_label="Message Copied!"
            )
            button_count += 1

def extractQuery(response):
    """Extract SQL statement from LLM's response"""
    statement = response.content.replace("\n", " ")
    start_index = statement.rfind("SELECT")
    end_index = start_index + statement[start_index:].rfind(";")
    statement = statement[start_index:end_index]
    return statement


# -- Configure the LLM ---
llm = ChatOllama(
    model="llama3.2",
    temperature=0,
).bind_tools(ALL_TOOLS)

# --- Configure Streamlit page ---
st.set_page_config(page_title="King County Transit Chat", page_icon="🚌", layout="centered")
st.title("🚌 Transit Data Chat Assistant")
st.subheader("Your AI assistant for retrieving King Country Metro transit data")

# --- Custom CSS ---
st.markdown(
    """
    <style>
    /* App background: yellow with thick diagonal black stripes */
    .stApp {
        background-color: #ffd700; /* taxi yellow */
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
    .chat-message.assistant::before { content: "🚌 "; position: absolute; left: 16px; top: 50%; transform: translateY(-50%); font-size: 1.8rem; }

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

# Header
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

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant", 
            "content": "Hi! I'm your transit data assistant. Ask me anything about King County Metro transit routes. How can I help you today?"
        }
    ]

display_messages()

# --- Handle new user input ---
prompt = st.chat_input("Ask me about King County Metro routes ...")

if prompt:
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Show user message
    with st.chat_message("user"):
        st.write(prompt)

    # Show thinking indicator while processing
    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.write("🤔 Thinking...")

        # Call Ollama through ChatOllama
        try:
            print("\n*** ---------------------------------------------------- ***\n")   # to separate responses for each prompt
            
            # Configure the invocation array
            systemInstructions = """
                You are a helpful assistant who only answers about King County Metro.
                If the user asks about any other transit systems (e.g. New York transit), state 'I am not authorized to provide information not pertaining to King County Metro.' Do not answer about any other transit systems.
                Respond 'I am not authorized to suggest updates, additions, or overwrites to the database.' if the user requests database updates, changes, additions, or overwrites.
                
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
                    aggregation: 'daily', 'weekly', or 'monthly'

                busiest_stops returns the busiest stops by total boardings or total alightings.
                Args:
                        start_date: Start date
                        end_date: End date
                        route_id: Optional route filter
                        top_n: Number of stops to return
                        metric: 'boardings' or 'alightings'
                
                service_change_impact returns an analysis of ridership impact before and after a service change.
                Args:
                    route_id: Route identifier
                    change_date: Date of service change (YYYY-MM-DD)
                    window_days: Days before/after to compare (default 30)
                
                If a tool can answer the question, you MUST call the tool.
                If the user only specifies a month, use the first day of the month for the year 2025 as the start_date and the last day of the month for the year 2025 as the end_date.
                Otherwise:
                    If the user does not specify a start_date, use January 1st, 2025 as the baseline for the tool arguments.
                    If the user does not specify an end_date, you MUST use December 31st, 2025 as the baseline for the tool arguments.
                
                If the user does not specify a change_date, use June 15th, 2025 as the baseline for the tool arguments.
                The route id should only be the number or name of the route (e.g. 2, 40, E Line).
            """
            systemMessages = [SystemMessage(systemInstructions),
                              HumanMessage(prompt)]
            
            # Get response from LLM
            response = llm.invoke(systemMessages)
            print("Tool Response:\n", response)
            answer = response.content

            if "I am not authorized" not in answer:
                if response.tool_calls: # If the model calls a tool, handle the tool call
                    print("Handling tool invocation...")
                    toolMessages = [HumanMessage(prompt), response]

                    answer = ""
                    for tool_call in response.tool_calls:
                        tool_name = tool_call["name"].lower()
                        selected_tool = TOOL_MAP[tool_name]

                        # Execute tool with args ONLY
                        tool_result = selected_tool.invoke(tool_call["args"])
                        answer += str(tool_result) + "\n"

                    print(response.tool_calls)


        except Exception as e:
            answer = f"I'm sorry, I encountered an error: {e}. Please try asking your question again."

        # Replace thinking indicator with actual response
        placeholder.write(answer)

        # Add assistant response to history
        st.session_state.messages.append({"role": "assistant", "content": answer})

    # Refresh the page to show updated chat
    st.rerun()