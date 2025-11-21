from dotenv import load_dotenv
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from langchain_community.tools.tavily_search import TavilySearchResults

from state import AgentState
from nodes import (
    parse_link, fallback_title_extractor,
    researcher_amazon, researcher_reddit, researcher_web,
    harvest_reviews, generate_report, chat_node, summarize_conversation
)

load_dotenv()