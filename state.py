from typing import List, Dict, Any, Optional, TypedDict, Annotated
import operator
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class ResearchEvidence(TypedDict):
    source: str  # 'amazon', 'reddit', 'web'
    content: str
    url: Optional[str]
    metadata: Optional[Dict[str, Any]]

class SentimentAnalysis(TypedDict):
    positive_topics: List[str]
    negative_topics: List[str]
    rating_distribution: Dict[str, int]
    average_rating: float
    total_reviews: int
    
class AgentState(TypedDict):
    product_link: str
    product_query: str
    research_evidence: Annotated[List[ResearchEvidence], operator.add]
    reviews_analysis: Optional[SentimentAnalysis]
    final_report: Optional[str]  # Markdown-formatted report string

    # Conversation state
    messages: Annotated[List[BaseMessage], add_messages]
    summary: str