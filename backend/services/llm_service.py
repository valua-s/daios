from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from backend.core.config import Settings

logger = logging.getLogger(__name__)

VALID_SOURCES = {"newsapi", "youtube"}


@dataclass
class SearchQuery:
    query: str
    topic: str
    source: str  # "newsapi" | "youtube"


@dataclass
class ContentCandidate:
    id: int
    title: str
    topic: str | None
    source: str | None
    type: str  # "article" | "video"


class LLMService:
    """OpenRouter LLM wrapper — генерация поисковых запросов и выбор контента."""

    def __init__(self, cfg: Settings) -> None:
        self._llm = ChatOpenAI(
            model=cfg.model_agents,  # ty:ignore[unknown-argument]
            openai_api_key=cfg.openai_api_key.get_secret_value(),  # ty:ignore[invalid-argument-type]
            openai_api_base=cfg.openai_base_url,
            temperature=0.3,
            max_tokens=1024,
        )

    async def generate_search_queries(
        self, focus_description: str, topics: list[str],
    ) -> list[SearchQuery]:
        """Генерирует 4-6 поисковых запросов под фокус пользователя."""
        system = SystemMessage(content=(
            "You are a strict content curator assistant. "
            "You MUST follow instructions exactly. "
            "You MUST return valid JSON only — no markdown, no explanation, no extra text."
        ))
        human = HumanMessage(content=(
            f"My current focus: {focus_description}\n"
            f"My active topics: {', '.join(topics)}\n\n"
            "TASK: Generate EXACTLY 6 search queries to find content that helps me with my focus.\n"
            "Each query targets either \"newsapi\" (articles) or \"youtube\" (videos).\n\n"
            "Rules:\n"
            "- EXACTLY 6 queries, no more, no less\n"
            "- Mix topics, sources, and languages (Russian and English)\n"
            "- At least one query per active topic\n"
            "- Queries should be specific and actionable (3-6 words)\n"
            "- Tag each query with the most relevant topic from my active topics\n\n"
            "Response format — a JSON array of exactly 6 objects:\n"
            '[{"query": "search string", "topic": "python", "source": "newsapi"}, '
            '{"query": "search string", "topic": "ai", "source": "youtube"}, ...]'
        ))

        response = await self._llm.ainvoke([system, human])
        raw = _extract_json_array(response.content)
        if raw is None:
            logger.warning("LLM returned no valid JSON for search queries")
            return []

        results: list[SearchQuery] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            query = str(item.get("query", "")).strip()
            topic = str(item.get("topic", "")).strip()
            source = str(item.get("source", "")).strip().lower()
            if query and topic in topics and source in VALID_SOURCES:
                results.append(SearchQuery(query=query, topic=topic, source=source))

        logger.info("LLM generated %d search queries", len(results))
        return results

    async def select_content(
        self,
        candidates: list[ContentCandidate],
        focus_description: str,
        n: int = 6,
    ) -> list[int]:
        """Выбирает n лучших кандидатов, возвращает их ID в порядке релевантности."""
        if not candidates:
            return []

        table_lines = []
        for c in candidates:
            table_lines.append(f"{c.id} | {c.type} | {c.topic or '-'} | {c.source or '-'} | {c.title}")
        table = "\n".join(table_lines)

        system = SystemMessage(content=(
            "You are a strict content curator. You MUST follow instructions exactly. "
            "You MUST return valid JSON only — no markdown, no explanation, no extra text."
        ))
        human = HumanMessage(content=(
            f"My current focus: {focus_description}\n\n"
            f"Content candidates (id | type | topic | source | title):\n{table}\n\n"
            f"TASK: Select EXACTLY {n} items (no more, no less) for today's digest.\n\n"
            "Selection criteria (in priority order):\n"
            "1. Relevance to my current focus\n"
            "2. Diversity of topics (don't pick all from one topic)\n"
            "3. Mix of content types (articles and videos)\n"
            "4. Freshness and practical value\n\n"
            f"IMPORTANT: You MUST return EXACTLY {n} IDs. Not {n-1}, not {n+1}, exactly {n}.\n"
            f"Response format — a JSON array of exactly {n} integer IDs, ordered by relevance:\n"
            f"[1, 2, 3, 4, 5, 6]"
        ))

        response = await self._llm.ainvoke([system, human])
        raw = _extract_json_array(response.content)
        if raw is None:
            logger.warning("LLM returned no valid JSON for content selection")
            return []

        valid_ids = {c.id for c in candidates}
        selected = [int(item) for item in raw if isinstance(item, (int, float)) and int(item) in valid_ids]

        # Дедупликация с сохранением порядка
        seen: set[int] = set()
        unique: list[int] = []
        for id_ in selected:
            if id_ not in seen:
                seen.add(id_)
                unique.append(id_)

        logger.info("LLM selected %d content items", len(unique))
        return unique[:n]


def _extract_json_array(text: str) -> list | None:
    """Извлекает JSON-массив из ответа LLM."""
    if not isinstance(text, str):
        return None
    match = re.search(r"\[.*]", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group())
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse JSON from LLM response: %s", text[:200])
    return None
