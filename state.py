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