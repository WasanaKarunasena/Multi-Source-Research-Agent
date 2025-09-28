# backend/server.py
import os
import json
import subprocess
from typing import List, Dict, Any

import requests
import feedparser
from dotenv import load_dotenv

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

# === MCP SDK ===
from mcp.server.fastmcp import FastMCP

# ---------- config ----------
load_dotenv()
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

def detect_ollama_model() -> str:
    """
    Detect installed Ollama models. Returns first available model.
    Fallback: llama3:8b
    """
    try:
        proc = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            check=False
        )
        lines = proc.stdout.strip().splitlines()
        if len(lines) > 1:  # first line is header
            first_model = lines[1].split()[0]  # NAME column
            return first_model
    except Exception as e:
        print("⚠️ Ollama detection failed:", e)
    return "llama3:8b"

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL") or detect_ollama_model()
print(f"✅ Using Ollama model: {OLLAMA_MODEL}")

# ---------- shared fetchers ----------
def fetch_arxiv(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    url = (
        "http://export.arxiv.org/api/query"
        f"?search_query=all:{requests.utils.quote(query)}&start=0&max_results={max_results}"
    )
    feed = feedparser.parse(url)
    results = []
    for e in feed.entries:
        results.append({
            "source": "arXiv",
            "title": getattr(e, "title", ""),
            "summary": (getattr(e, "summary", "") or "")[:600],
            "link": getattr(e, "link", ""),
            "published": getattr(e, "published", "")
        })
    return results

def fetch_news(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    if not NEWS_API_KEY:
        return []
    url = (
        "https://newsapi.org/v2/everything"
        f"?q={requests.utils.quote(query)}&pageSize={max_results}&language=en&sortBy=publishedAt&apiKey={NEWS_API_KEY}"
    )
    resp = requests.get(url, timeout=30)
    if resp.status_code != 200:
        return []
    data = resp.json()
    results = []
    for a in data.get("articles", []):
        results.append({
            "source": f"News: {a.get('source', {}).get('name', '')}",
            "title": a.get("title", ""),
            "summary": a.get("description", "") or (a.get("content", "") or "")[:600],
            "url": a.get("url", ""),
            "published": a.get("publishedAt", "")
        })
    return results

BLOG_FEEDS = [
    "https://openai.com/blog/rss",
    "https://machinelearningmastery.com/feed",
    "https://towardsdatascience.com/feed"
]

def fetch_blogs(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    q = (query or "").lower()
    results = []
    for feed_url in BLOG_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[: max_results * 2]:
            title = getattr(entry, "title", "")
            summary = getattr(entry, "summary", "")
            if q in title.lower() or q in summary.lower():
                results.append({
                    "source": f"Blog: {feed.feed.get('title', 'RSS')}",
                    "title": title,
                    "summary": (summary or "")[:600],
                    "link": getattr(entry, "link", ""),
                    "published": getattr(entry, "published", "")
                })
                if len(results) >= max_results:
                    break
    return results

def summarize_with_ollama(text: str) -> str:
    try:
        prompt = (
            "You are a research assistant. Summarize and cluster the following items. "
            "Highlight 2025 developments, notable papers, and themes. Keep it under 200 words.\n\n"
            f"{text}"
        )
        proc = subprocess.run(
            ["ollama", "run", OLLAMA_MODEL],
            input=prompt.encode("utf-8"),
            capture_output=True,
            check=False
        )
        return proc.stdout.decode("utf-8", errors="ignore").strip()
    except Exception as e:
        return f"(Ollama error) {e}"

def aggregate(query: str, max_results: int = 5) -> Dict[str, Any]:
    arxiv = fetch_arxiv(query, max_results)
    news = fetch_news(query, max_results)
    blogs = fetch_blogs(query, max_results)

    lines = []
    for bucket, items in (("arXiv", arxiv), ("News", news), ("Blogs", blogs)):
        for it in items:
            title = it.get("title", "")
            summary = it.get("summary", "")
            lines.append(f"[{bucket}] {title}\n{summary}\n")
    summary = summarize_with_ollama("\n".join(lines)) if lines else "No results to summarize."

    return {
        "arxiv": arxiv,
        "news": news,
        "blogs": blogs,
        "summary": summary
    }

# ---------- MCP server ----------
mcp = FastMCP("multi-source-research")

@mcp.tool()
def search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Multi-source research across arXiv, NewsAPI, and blogs."""
    return aggregate(query, max_results)

# FIXED: MCP resource now only uses 'query' to match parameters
@mcp.resource("research://{query}")
def research_resource(query: str) -> str:
    data = aggregate(query)  # uses default max_results=5
    return json.dumps(data, ensure_ascii=False, indent=2)

# ---------- FastAPI app ----------
app = FastAPI(title="Multi-Source Research (MCP + HTTP)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/search")
def http_search(q: str = Query(""), max_results: int = Query(5)):
    return aggregate(q, max_results)

# Expose MCP as HTTP transport
app.mount("/mcp", mcp.streamable_http_app())
