import os
import requests
from bs4 import BeautifulSoup
from typing import Any, Dict, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, HumanMessage, RemoveMessage, ToolMessage, AIMessage
from tavily import TavilyClient
from langchain_community.tools.tavily_search import TavilySearchResults
import json

from state import AgentState, ResearchEvidence, SentimentAnalysis

def clean_json(text: str) -> str:
    """Cleans markdown code blocks from JSON string. which I dont understand"""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

def get_llm():
    """Returns the LLM instance."""
    api_key = os.environ.get("OPENAI_API_KEY")
    return ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=api_key)


def get_tavily():
    """Returns the Tavily client."""
    api_key = os.environ.get("TAVILY_API_KEY")
    return TavilyClient(api_key=api_key)

def parse_link(state: AgentState) -> Dict[str, Any]:
    """Extracts product name/metadata from the link using BeautifulSoup + LLM."""
    # gets the url from the state
    link = state["product_link"]

    # we used headers here because some websites block requests without them
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9'
    }
    response = requests.get(link, headers=headers, timeout=10)

    # we check if we were able to download the HTML of the product page (Status 200 = Success)
    if response.status_code != 200:
        return {"product_query": None}

    # We use BeautifulSoup to parse the HTML and extract the <title> of the product from it
    soup = BeautifulSoup(response.content, 'html.parser')
    title = soup.title.string if soup.title else ""

    # Specific logic for Amazon to get cleaner titles
    if "amazon" in link:
        product_title_elem = soup.find("span", {"id": "productTitle"})
        if product_title_elem:
            title = product_title_elem.get_text().strip()

    if not title:
        return {"product_query": None}

    # The title often has extra stuff so here we use LLM to extract just the title.
    llm = get_llm()
    if llm:
        prompt = ChatPromptTemplate.from_template(
            "Extract the precise product name from this webpage title. Return ONLY the product name, no extra text.\nTitle: {title}"
        )
        chain = prompt | llm
        product_name = chain.invoke({"title": title}).content.strip()
    else:
        product_name = title[:100]

    print(f"Identified Product: {product_name}")
    return {"product_query": product_name}

def fallback_title_extractor(state: AgentState) -> Dict[str, Any]:
    """This node is a backup plan if parse_link() fails to extract the product name. It tries to guess the product name from the URL structure itself."""
    link = state["product_link"]

    # Extracts the Amazon ASIN (product ID) an does some crazy string parsing to get the product name which I don't understand.
    if "amazon" in link and "/dp/" in link:
        parts = link.split("/dp/")
        if len(parts) > 1:
            guess = parts[1].split("/")[0].split("?")[0]
            return {"product_query": f"Amazon Product {guess}"}

    guess = link.split("/")[-1].replace("-", " ").replace("_", " ").split("?")[0]
    if not guess:
        guess = "Product from URL"
    return {"product_query": guess}

# Research Subgraph Nodes

# This is the core search function used by all three researchers (Amazon, Reddit, Web). It uses the Tavily API to find relevant information about the product.
def perform_search(query: str, source_type: str) -> List[ResearchEvidence]:
    """Performs search and returns list of ResearchEvidence."""

    tavily = get_tavily()

    search_query = query
    if source_type == "amazon":
        # Targets verified feedback, specs, and direct comparisons
        search_query += " 'verified purchase' review 'pros and cons' features technical specifications price comparison"

    elif source_type == "reddit":
        # Targets community consensus, common issues, and real usage
        search_query += " site:reddit.com discussion 'is it worth it' issues solved 'long term review' complaints"

    elif source_type == "web":
        # Targets expert analysis, benchmarks, and deep-dives
        search_query += " 'in-depth review' benchmarks 'hands-on' alternatives 'vs' blog transcript"

    results = tavily.search(query=search_query, search_depth="advanced", max_results=5)

    evidence = []
    for res in results.get("results", []):
        evidence.append(ResearchEvidence(
            source=source_type,
            content=res.get("content", ""),
            url=res.get("url", ""),
            metadata={"title": res.get("title", "")}
        ))
    return evidence
