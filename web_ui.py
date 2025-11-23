import streamlit as st
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from graph import app

# Page configuration
st.set_page_config(
    page_title="Product Research Agent",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Page configuration
st.set_page_config(
    page_title="Product Research Agent",
    page_icon="🔍",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom CSS for clean interface with better report formatting
st.markdown("""
<style>
    /* Hide sidebar */
    [data-testid="stSidebar"] {
        display: none;
    }
    
    /* Main container */
    .main {
        max-width: 900px;
        padding: 2rem 1rem;
    }
    
    /* Input styling */
    .stTextInput > div > div > input {
        font-size: 16px;
        padding: 12px;
    }
    
    /* Button styling */
    .stButton > button {
        width: 100%;
        padding: 12px;
        font-size: 16px;
        font-weight: 500;
    }
    
    /* Header styling */
    h1 {
        font-weight: 600;
        margin-bottom: 8px;
        font-size: 2.5rem;
        color: #1a1a1a;
    }
    
    .subtitle {
        color: #666;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    /* Report container with better formatting */
    .report-container {
        padding: 2rem 0;
        margin-top: 2rem;
        line-height: 1.6;
        color: #ffffff;
    }
    
    /* Markdown formatting improvements */
    .report-container h1 {
        font-size: 2rem;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
        border-bottom: 2px solid #404040;
        padding-bottom: 0.5rem;
        color: #ffffff;
    }
    
    .report-container h2 {
        font-size: 1.5rem;
        margin-top: 1.5rem;
        margin-bottom: 0.8rem;
        color: #f0f0f0;
    }
    
    .report-container h3 {
        font-size: 1.2rem;
        margin-top: 1rem;
        margin-bottom: 0.6rem;
        color: #e0e0e0;
    }
    
    .report-container p {
        color: #ffffff;
        margin-bottom: 1rem;
    }
    
    .report-container ul {
        margin-left: 1.5rem;
        margin-bottom: 1rem;
        color: #ffffff;
    }
    
    .report-container li {
        margin-bottom: 0.5rem;
        color: #ffffff;
    }
    
    .report-container strong {
        color: #ffffff;
        font-weight: 600;
    }
    
    .report-container hr {
        margin: 2rem 0;
        border: none;
        border-top: 1px solid #eee;
    }
    
    .report-container blockquote {
        border-left: 4px solid #e0e0e0;
        padding-left: 1rem;
        margin-left: 0;
        color: #666;
        font-style: italic;
    }
    
    /* API status at top */
    .api-status {
        background-color: #f8f9fa;
        padding: 12px 16px;
        border-radius: 6px;
        margin-bottom: 1.5rem;
        font-size: 14px;
        color: #666;
    }
    
    .api-status-ok {
        color: #28a745;
    }
    
    .api-status-error {
        color: #dc3545;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.title("Product Research Agent")
st.markdown('<p class="subtitle">Enter a product URL to generate a comprehensive research report</p>', unsafe_allow_html=True)

# API Status (compact, at top)
openai_ok = bool(os.environ.get("OPENAI_API_KEY"))
tavily_ok = bool(os.environ.get("TAVILY_API_KEY"))

if openai_ok and tavily_ok:
    st.markdown('<div class="api-status"><span class="api-status-ok">✓</span> API keys configured</div>', unsafe_allow_html=True)
else:
    missing = []
    if not openai_ok:
        missing.append("OPENAI_API_KEY")
    if not tavily_ok:
        missing.append("TAVILY_API_KEY")
    st.markdown(f'<div class="api-status"><span class="api-status-error">✗</span> Missing: {", ".join(missing)}</div>', unsafe_allow_html=True)

# Session State Initialization
if "report" not in st.session_state:
    st.session_state.report = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# Input section
url = st.text_input(
    "Product URL",
    placeholder="https://www.amazon.com/product-url or any e-commerce link",
    label_visibility="collapsed"
)

# Generate button
if st.button("Generate Report", type="primary"):
    if not url:
        st.warning("Please enter a product URL")
    else:
        # Check API keys
        if not openai_ok:
            st.error("OPENAI_API_KEY not found. Please set it in your .env file.")
            st.stop()
        
        if not tavily_ok:
            st.error("TAVILY_API_KEY not found. Please set it in your .env file.")
            st.stop()
        
        # Show progress
        with st.spinner("Analyzing product... This may take 15-30 seconds"):
            try:
                # Initialize state
                initial_state = {
                    "product_link": url,
                    "research_evidence": [],
                    "messages": [],
                    "summary": ""
                }
                
                # Run the agent
                # Use a thread_id for persistence
                thread_id = "web_session_1"
                config = {"configurable": {"thread_id": thread_id}}
                
                result = app.invoke(initial_state, config=config)
                
                # Get report
                report = result.get("final_report")
                
                if report:
                    # Store report in session state to persist across reruns
                    st.session_state.report = report
                    st.session_state.thread_config = config
                    st.session_state.messages = [] # Reset chat on new report
                    st.rerun()
                else:
                    st.error("No report generated. Please try again.")
                    
            except Exception as e:
                st.error(f"Error: {str(e)}")
                st.error("Please check your API keys and try again.")

# Display Report if available
if st.session_state.get("report"):
    st.markdown("---")
    st.markdown(f'<div class="report-container">{st.session_state.report}</div>', unsafe_allow_html=True)

    
    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    # Chat input
    if prompt := st.chat_input("Ask about the product..."):
        # Add user message to UI
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            
        # Get response from agent
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                from langchain_core.messages import HumanMessage
                
                # Invoke graph with new message
                response = app.invoke(
                    {"messages": [HumanMessage(content=prompt)]}, 
                    config=st.session_state.thread_config
                )
                
                # Get latest AI response
                if response.get("messages"):
                    last_msg = response["messages"][-1]
                    ai_response = last_msg.content
                    st.markdown(ai_response)
                    
                    # Add AI message to UI
                    st.session_state.messages.append({"role": "assistant", "content": ai_response})
                    
                    # Check for summary
                    if response.get("summary") and len(response["messages"]) <= 2:
                        st.caption("Conversation summarized to save memory")
    
    # Reset Button
    if st.session_state.get("report"):
        if st.sidebar.button("New Research"):
            st.session_state.report = None
            st.session_state.messages = []
            st.rerun()
