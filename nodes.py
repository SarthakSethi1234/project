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

@trace
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

@trace
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
@trace
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

# Now we will define three parallel research agents that gather information from different sources. they all  willrun parallely in the research subgraph.

def researcher_amazon(state: AgentState) -> Dict[str, Any]:
    """Searches Amazon and e-commerce reviews."""
    product_query = state.get("product_query") or state.get("product_link", "product")
    evidence = perform_search(product_query, "amazon")
    return {"research_evidence": evidence}

def researcher_reddit(state: AgentState) -> Dict[str, Any]:
    """Searches Reddit for real opinions."""
    product_query = state.get("product_query") or state.get("product_link", "product")
    evidence = perform_search(product_query, "reddit")
    return {"research_evidence": evidence}

def researcher_web(state: AgentState) -> Dict[str, Any]:
    """Searches general web for blogs and videos."""
    product_query = state.get("product_query") or state.get("product_link", "product")
    evidence = perform_search(product_query, "web")
    return {"research_evidence": evidence}

@trace
def harvest_reviews(state: AgentState) -> Dict[str, Any]:
    """Analyzes sentiment and topics using LLM."""

    # Check if we have evidence
    if not state['research_evidence']:
        return {"reviews_analysis": None}


    llm = get_llm()

    evidence_text = "\n".join([f"[{e['source']}] {e['content']}" for e in state['research_evidence']])

    prompt = ChatPromptTemplate.from_template(
        """Analyze the following product research evidence and extract sentiment insights.
        Return a valid JSON object with keys: positive_topics (list), negative_topics (list), 
        rating_distribution (dict 1-5 stars, estimate if needed), average_rating (float), total_reviews (int estimate).

        Evidence:
        {evidence}
        """
    )
    chain = prompt | llm
    try:
        res = chain.invoke({"evidence": evidence_text[:10000]})
        content = clean_json(res.content)
        data = json.loads(content)
        return {"reviews_analysis": data}
    except Exception as e:
        print(f"Error in harvesting reviews: {e}")
        return {"reviews_analysis": None}

@trace
def generate_report(state: AgentState) -> Dict[str, Any]:
    """Generates the final markdown-formatted report using LLM."""
    print("--- Generating Report ---")

    llm = get_llm()

    evidence_text = "\n".join([f"[{e['source']}] {e['content']}" for e in state['research_evidence']])
    analysis_text = json.dumps(state.get("reviews_analysis") or {})

    prompt = ChatPromptTemplate.from_template(
        """You are a product research analyst. Generate a comprehensive, concise, evidence-based product report for '{product}'.

            Use the following structure:

            1. Product Summary
            Product Name: [Extract from evidence]
            Category: [Determine category]
            Overall Verdict: 2–3 sentence summary describing usefulness, value, and tradeoffs.

            2. Key Insights
            Strengths: [List 3–5 key strengths based on evidence]
            Weaknesses: [List 3–5 key weaknesses]
            Most Mentioned Issues: [List 2–4 frequently mentioned problems]

            3. Ratings Snapshot
            Average Rating: [X.X / 5.0]
            Total Reviews Analyzed: [Number]
            Rating Distribution: 5★: X% | 4★: X% | 3★: X% | 2★: X% | 1★: X%

            4. Source Breakdown
            Amazon/E-commerce: top praises, complaints, patterns
            Reddit: community sentiment, frequent pain points, notable insights
            Web/Expert reviews: expert impressions, long-term notes

            5. Supporting Evidence
            Include 5–8 verbatim quotes from the evidence in this format:
            [Source – context] "Exact quote"

            6. Recommendation
            Best For: [3–4 specific user types]
            Avoid If: [3–4 scenarios]

            7. Confidence Score
            Analysis Confidence: [X%]
            Based on evidence strength, diversity, and reliability
            Data Summary: Number of sources used: Amazon: [X], Reddit: [Y], Web: [Z]

            Instructions:
            Follow the structure exactly.
            Only use provided evidence.
            Be concise, clear, and data-driven.
            Do not fabricate information.
            Keep the report informative and actionable.

            Evidence Input:
            {evidence}

            Sentiment Analysis:
            {analysis}"""
    )

    chain = prompt | llm

    res = chain.invoke({
        "product": state["product_query"],
        "evidence": evidence_text[:20000],
        "analysis": analysis_text
    })

    report = res.content.strip()

    # Clean markdown code blocks if present
    if report.startswith("```markdown"):
        report = report[11:]
    elif report.startswith("```"):
        report = report[3:]
    if report.endswith("```"):
        report = report[:-3]

    report = report.strip()

    return {
        "final_report": report,
        "messages": [AIMessage(content=report)]
    }

# Chat Nodes & Persistence Stage

@trace
def chat_node(state: AgentState) -> Dict[str, Any]:
    """Answers user questions based on the generated report and web search."""
    llm = get_llm()

    # Define tools
    tools = [TavilySearchResults(max_results=3)]
    llm_with_tools = llm.bind_tools(tools)

    report = state.get("final_report", "No report available.")
    summary = state.get("summary", "")

    system_msg = f"""You are a helpful product research assistant. 
    You have generated a detailed report about a product. 
    Answer the user's follow-up questions based on this report.

    If the user asks for information NOT in the report (like current price, new models, or specific details), 
    use the 'tavily_search_results_json' tool to find the answer.

    Report Content:
    {report}

    Conversation Summary:
    {summary}
    """

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_msg),
        MessagesPlaceholder(variable_name="messages"),
    ])

    chain = prompt | llm_with_tools
    response = chain.invoke({"messages": state["messages"]})

    return {"messages": [response]}

@trace
def summarize_conversation(state: AgentState) -> Dict[str, Any]:
    """Summarizes the conversation and removes old messages to save memory """
    llm = get_llm()
    summary = state.get("summary", "")
    messages = state["messages"]

    if summary:
        summary_prompt = f"Previous summary: {summary}\n\nNew lines of conversation:\n"
    else:
        summary_prompt = "Summarize the conversation so far:\n"

    # Create prompt for summarization
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Distill the following conversation into a concise summary."),
        ("user", summary_prompt),
        MessagesPlaceholder(variable_name="messages"),
    ])

    chain = prompt | llm
    res = chain.invoke({"messages": messages})
    new_summary = res.content

    # Keep last 2 messages
    cutoff = max(0, len(messages) - 2)
    while cutoff > 0 and isinstance(messages[cutoff], ToolMessage):
        cutoff -= 1

    delete_messages = [RemoveMessage(id=m.id) for m in messages[:cutoff]]

    return {
        "summary": new_summary,
        "messages": delete_messages
    }
