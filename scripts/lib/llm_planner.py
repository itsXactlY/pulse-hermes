"""LLM-based intelligent query planner for PULSE.

Uses an LLM (OpenRouter, Ollama, or OpenAI) for smart query planning
instead of heuristic keyword matching. Falls back to heuristic planner
if no LLM is available.
"""

import json
import os
import subprocess
from typing import Any, Dict, List, Optional

from . import http, log
from .schema import QueryPlan, SubQuery

SYSTEM_PROMPT = """You are a research query planner. Given a topic and available sources,
generate an optimal search plan.

Available sources and what they're best for:
- reddit: Community discussions, opinions, Q&A, unfiltered takes
- hackernews: Tech/startup news, developer consensus, deep technical discussions
- polymarket: Prediction markets, betting odds, probability estimates
- github: Repos, code, issues, PRs, developer activity
- web: General web search, news articles, blog posts
- news: NewsAPI articles from major publications
- youtube: Video content, tutorials, interviews, deep dives
- arxiv: Academic papers, ML/AI research, scientific publications
- lobsters: Curated tech links, systems programming, quality-focused community
- rss: Technical blogs, engineering blogs, expert opinions

Output ONLY valid JSON, no markdown fences:
{
  "intent": "general|prediction|comparison|person_research|product_research|news_tracking|learning|academic",
  "subqueries": [
    {
      "label": "short_label",
      "search_query": "the actual search query",
      "ranking_query": "query used for relevance ranking",
      "sources": ["source1", "source2"],
      "weight": 1.0
    }
  ],
  "source_weights": {"source_name": 1.0},
  "notes": ["any observations about the topic"]
}

Rules:
- Generate 2-4 subqueries for default depth, 1-2 for quick, 4-6 for deep
- Each subquery should target different aspects of the topic
- Include all available sources across subqueries
- Weight sources higher where they're most relevant
- For prediction topics, weight polymarket higher
- For tech topics, weight hackernews, lobsters, and github higher
- For academic/research topics, weight arxiv and hackernews higher
- For people, search github (activity), reddit (opinions), and web (coverage)
- For blog/opinion topics, weight rss and lobsters higher
- ranking_query should be the original topic for consistency
"""


def _source_log(msg: str):
    log.source_log("Planner-LLM", msg)


def _check_ollama() -> Optional[str]:
    """Check if Ollama is running and return best model."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")[1:]  # Skip header
            models = []
            for line in lines:
                parts = line.split()
                if parts:
                    models.append(parts[0])
            if models:
                return models[0]  # Return first available model
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _call_ollama(
    model: str,
    prompt: str,
    timeout: int = 30,
) -> Optional[str]:
    """Call Ollama API."""
    try:
        result = subprocess.run(
            ["ollama", "run", model, prompt],
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, Exception) as e:
        _source_log(f"Ollama error: {e}")
    return None


def _call_openrouter(
    api_key: str,
    model: str,
    prompt: str,
    timeout: int = 30,
) -> Optional[str]:
    """Call OpenRouter API."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 1000,
    }

    try:
        result = http.post(url, json_data=data, headers=headers, timeout=timeout)
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        _source_log(f"OpenRouter error: {e}")
    return None


def _call_openai(
    api_key: str,
    model: str,
    prompt: str,
    timeout: int = 30,
) -> Optional[str]:
    """Call OpenAI API."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 1000,
    }

    try:
        result = http.post(url, json_data=data, headers=headers, timeout=timeout)
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        _source_log(f"OpenAI error: {e}")
    return None


def _extract_json(text: str) -> Optional[dict]:
    """Extract JSON from LLM response (handles markdown fences)."""
    if not text:
        return None

    # Remove markdown fences
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)

    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        # Try to find JSON object in text
        import re
        match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


def _get_llm_response(
    config: Dict[str, Any],
    prompt: str,
) -> Optional[str]:
    """Try available LLM providers in order."""
    # 1. OpenRouter (cheapest, broadest model selection)
    openrouter_key = config.get("OPENROUTER_API_KEY")
    if openrouter_key:
        _source_log("Using OpenRouter for query planning")
        return _call_openrouter(
            openrouter_key,
            "google/gemini-2.0-flash-lite-001",  # Fast and cheap
            prompt,
        )

    # 2. OpenAI
    openai_key = config.get("OPENAI_API_KEY")
    if openai_key:
        _source_log("Using OpenAI for query planning")
        return _call_openai(openai_key, "gpt-4o-mini", prompt)

    # 3. Ollama (local, free)
    ollama_model = _check_ollama()
    if ollama_model:
        _source_log(f"Using Ollama ({ollama_model}) for query planning")
        full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"
        return _call_ollama(ollama_model, full_prompt)

    _source_log("No LLM available for planning, using heuristic")
    return None


def plan_query(
    topic: str,
    available_sources: List[str],
    depth: str = "default",
    config: Optional[Dict[str, Any]] = None,
    requested_sources: Optional[List[str]] = None,
) -> QueryPlan:
    """Generate a query plan using LLM or heuristic fallback.

    Args:
        topic: Research topic
        available_sources: Available source names
        depth: Research depth
        config: Configuration dict with API keys
        requested_sources: User-requested specific sources
    """
    if config is None:
        config = {}

    # Filter to requested sources
    if requested_sources:
        sources = [s for s in requested_sources if s in available_sources]
    else:
        sources = available_sources

    if not sources:
        sources = available_sources

    # Build LLM prompt
    prompt = f"""Topic: {topic}
Available sources: {', '.join(sources)}
Depth: {depth}
Requested sources: {requested_sources or 'all available'}

Generate a query plan for researching this topic."""

    # Try LLM planning
    response = _get_llm_response(config, prompt)
    if response:
        parsed = _extract_json(response)
        if parsed and "subqueries" in parsed:
            try:
                subqueries = []
                for sq in parsed["subqueries"]:
                    sq_sources = [s for s in sq.get("sources", sources) if s in sources]
                    if not sq_sources:
                        sq_sources = sources
                    subqueries.append(SubQuery(
                        label=sq.get("label", "query"),
                        search_query=sq.get("search_query", topic),
                        ranking_query=sq.get("ranking_query", topic),
                        sources=sq_sources,
                        weight=float(sq.get("weight", 1.0)),
                    ))

                if subqueries:
                    source_weights = {}
                    for sw in parsed.get("source_weights", {}):
                        if sw in sources:
                            source_weights[sw] = float(parsed["source_weights"][sw])
                    for s in sources:
                        if s not in source_weights:
                            source_weights[s] = 0.7

                    _source_log(f"LLM plan: {len(subqueries)} subqueries, intent={parsed.get('intent', 'unknown')}")
                    return QueryPlan(
                        intent=parsed.get("intent", "general"),
                        freshness_mode="strict" if parsed.get("intent") == "news_tracking" else "relaxed",
                        raw_topic=topic,
                        subqueries=subqueries,
                        source_weights=source_weights,
                        notes=parsed.get("notes", []),
                    )
            except (KeyError, ValueError, TypeError) as e:
                _source_log(f"LLM plan parsing failed: {e}, falling back to heuristic")

    # Fallback: use heuristic planner
    from . import planner as heuristic_planner
    return heuristic_planner.plan_query(
        topic=topic,
        available_sources=sources,
        depth=depth,
        requested_sources=requested_sources,
    )
