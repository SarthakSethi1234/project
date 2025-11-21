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

# Research Subgraph
research_builder = StateGraph(AgentState)
research_builder.add_node("researcher_amazon", researcher_amazon)
research_builder.add_node("researcher_reddit", researcher_reddit)
research_builder.add_node("researcher_web", researcher_web)

research_builder.add_edge(START, "researcher_amazon")
research_builder.add_edge(START, "researcher_reddit")
research_builder.add_edge(START, "researcher_web")

research_builder.add_edge("researcher_amazon", END)
research_builder.add_edge("researcher_reddit", END)
research_builder.add_edge("researcher_web", END)

research_subgraph = research_builder.compile()

# for a new chat go to link parser for a continued chat go to chat node
def route_start(state: AgentState):
    if state.get("messages") and len(state["messages"]) > 0:
        return "chat_node"
    return "parse_link"


def check_parser_success(state: AgentState):
    if state.get("product_query"):
        return "success"
    return "fail"


def route_chat(state: AgentState):
    messages = state.get("messages", [])
    last_message = messages[-1]

    if hasattr(last_message, "tool_calls") and len(last_message.tool_calls) > 0:
        return "tools"

    if len(messages) > 5:
        return "summarize"

    return "end"
