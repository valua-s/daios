from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from backend.core.config import Settings

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from typing import Any

logger = logging.getLogger(__name__)

VALID_SOURCES = {"newsapi", "youtube"}
_WORDS_PER_ARTICLE = 90
_MIN_DIGEST_WORDS = 250
_MAX_DIGEST_WORDS = 1200
_SCORE_BATCH_SIZE = 20
_SCORE_BATCH_DELAY = 3.0
_RETRY_DELAYS = (5.0, 15.0)


@dataclass
class SearchQuery:
    query: str
    topic: str
    source: str  # "newsapi" | "youtube"


@dataclass
class DigestArticle:
    index: int
    title: str
    summary: str
    source: str
    topic: str


@dataclass
class ContentCandidate:
    id: int
    title: str
    topic: str | None
    source: str | None
    type: str  # "article" | "video"


class SearchQueryList(BaseModel):
    q: list[SearchQuery]


class SelectedContentIds(BaseModel):
    ids: list[int]


class RelevanceScore(BaseModel):
    index: int
    score: int


class RelevanceScores(BaseModel):
    scores: list[RelevanceScore]


def _block_text(block: object) -> str:
    if isinstance(block, dict):
        return str(cast("dict[str, object]", block).get("text", ""))
    return str(block)


def _as_text(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [_block_text(block) for block in content]
        return "\n".join(p for p in parts if p).strip()
    return str(content).strip()


class LLMService:
    """OpenRouter LLM wrapper — генерация запросов, выбор контента и сводка новостей."""

    def __init__(self, cfg: Settings, http_client: httpx.AsyncClient) -> None:
        self._llm: ChatOpenAI = ChatOpenAI(
            model=cfg.llm_model_agents,  # ty:ignore[unknown-argument]
            openai_api_key=cfg.openai_api_key.get_secret_value(),  # ty:ignore[invalid-argument-type]
            openai_api_base=cfg.openai_base_url,
            temperature=0,
            max_completion_tokens=16000,
            http_async_client=http_client,
        )
        self._schema = {}

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
            'Each query targets either "newsapi" (articles) or "youtube" (videos).\n\n'
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

        response = cast(
            "SearchQueryList",
            await self._llm.with_structured_output(SearchQueryList).ainvoke([system, human]),
        )
        results: list[SearchQuery] = []
        for item in response.q:
            item.source = item.source.lower()
            if item.query and item.topic in topics and item.source in VALID_SOURCES:
                results.append(item)

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

        table_lines = [f"{c.id} | {c.type} | {c.topic or '-'} | {c.source or '-'} | {c.title}" for c in candidates]
        table = "\n".join(table_lines)

        system = SystemMessage(content=(
            "You are a strict content curator. You MUST follow instructions exactly. "
            "You MUST return valid JSON only — no markdown, no explanation, no extra text."
        ))
        human = HumanMessage(content=(
            f"My current focus: {focus_description}\n\n"  # noqa: S608
            f"Content candidates (id | type | topic | source | title):\n{table}\n\n"
            f"TASK: Select EXACTLY {n} items (no more, no less) for today's digest.\n\n"
            "Selection criteria (in priority order):\n"
            "1. Relevance to my current focus\n"
            "2. Diversity of topics (don't pick all from one topic)\n"
            "3. Mix of content types (articles and videos)\n"
            "4. Freshness and practical value\n\n"
            f"IMPORTANT: You MUST return EXACTLY {n} IDs. Not {n - 1}, not {n + 1}, exactly {n}.\n"
            f"Response format — a JSON object with field 'ids': an array of exactly {n} "
            "integer IDs, ordered by relevance:\n"
            '{"ids": [1, 2, 3, 4, 5, 6]}'
        ))

        response = cast(
            "SelectedContentIds",
            await self._llm.with_structured_output(SelectedContentIds).ainvoke([system, human]),
        )

        valid_ids = {c.id for c in candidates}
        selected = [int(item) for item in response.ids if int(item) in valid_ids]

        # Дедупликация с сохранением порядка
        seen: set[int] = set()
        unique: list[int] = []
        for id_ in selected:
            if id_ not in seen:
                seen.add(id_)
                unique.append(id_)

        logger.info("LLM selected %d content items", len(unique))
        return unique[:n]

    async def score_relevance(
        self, articles: list[DigestArticle], focus_description: str,
    ) -> dict[int, int]:
        """Оценивает каждую новость 0-10 по релевантности интересам. Возвращает index -> score."""
        scores: dict[int, int] = {}
        for start in range(0, len(articles), _SCORE_BATCH_SIZE):
            if start:
                await asyncio.sleep(_SCORE_BATCH_DELAY)
            batch = articles[start:start + _SCORE_BATCH_SIZE]
            label = f"Relevance batch {batch[0].index}-{batch[-1].index}"
            batch_scores = await self._retry(
                lambda b=batch: self._score_batch(b, focus_description), label,
            )
            scores.update(batch_scores or {})

        missing = [a.index for a in articles if a.index not in scores]
        if missing:
            logger.warning("Relevance scoring missed %d articles: %s", len(missing), missing)
        logger.info("LLM scored %d of %d articles", len(scores), len(articles))
        return scores

    @staticmethod
    async def _retry(call: Callable[[], Awaitable[Any]], label: str) -> Any:
        """Повторяет вызов модели: бесплатные модели регулярно отдают 429 от провайдера."""
        for delay in (*_RETRY_DELAYS, None):
            try:
                return await call()
            except Exception:
                if delay is None:
                    logger.exception("%s failed after %d attempts", label, len(_RETRY_DELAYS) + 1)
                    return None
                logger.warning("%s failed, retry in %.0fs", label, delay)
                await asyncio.sleep(delay)
        return None

    async def _score_batch(
        self, articles: list[DigestArticle], focus_description: str,
    ) -> dict[int, int]:
        table = "\n".join(
            f"[{a.index}] ({a.topic}) {a.title}" + (f" — {a.summary[:200]}" if a.summary else "")
            for a in articles
        )

        system = SystemMessage(content=(
            "You are a strict relevance classifier. You MUST follow instructions exactly. "
            "You MUST return valid JSON only — no markdown, no explanation, no extra text."
        ))
        human = HumanMessage(content=(
            f"Reader's interests: {focus_description}\n\n"
            f"News items (index | topic | title | summary):\n{table}\n\n"
            f"TASK: Score EVERY item from [{articles[0].index}] to [{articles[-1].index}] "
            "by how relevant it is to the reader's interests.\n\n"
            "Scale:\n"
            "- 9-10: directly about the reader's interests, substantial news\n"
            "- 7-8: clearly related, worth reading\n"
            "- 4-6: same broad field but off-target (e.g. generic sports when the reader runs, "
            "consumer gadgets when the reader follows AI research)\n"
            "- 0-3: unrelated — celebrities, weather, pets, match schedules, marketing announcements\n\n"
            "The item's declared topic is a guess from a search query, not a fact — judge by the title "
            "and summary themselves.\n"
            f"You MUST return a score for all {len(articles)} indexes.\n"
            'Response format — a JSON object: {"scores": [{"index": 1, "score": 8}, ...]}'
        ))

        response = cast(
            "RelevanceScores",
            await self._llm.with_structured_output(RelevanceScores).ainvoke([system, human]),
        )
        valid = {a.index for a in articles}
        return {s.index: s.score for s in response.scores if s.index in valid}

    async def write_news_digest(
        self, articles: list[DigestArticle], focus_description: str,
    ) -> str:
        """Пишет литературную сводку по новостям на русском языке."""
        if not articles:
            return ""

        target_words = min(
            max(len(articles) * _WORDS_PER_ARTICLE, _MIN_DIGEST_WORDS), _MAX_DIGEST_WORDS,
        )
        table = "\n".join(
            f"[{a.index}] ({a.topic} · {a.source}) {a.title}"
            + (f" — {a.summary}" if a.summary else "")
            for a in articles
        )

        system = SystemMessage(content=(
            "You are a Russian-speaking columnist writing a daily news digest. "
            "You write literary, flowing Russian prose — not bullet lists, not translations "
            "of headlines word by word. You never invent facts that are absent from the input."
        ))
        human = HumanMessage(content=(
            f"Reader's current focus: {focus_description}\n\n"
            f"Today's news items (English sources):\n{table}\n\n"
            "TASK: Write a single digest in RUSSIAN that retells all of these news items.\n\n"
            "Rules:\n"
            f"- Cover EVERY item from [1] to [{articles[-1].index}]. Losing a news item is a failure\n"
            "- Mark each retold item with its number in square brackets, e.g. [3]\n"
            "- Group related items into thematic paragraphs with smooth transitions\n"
            "- Translate meaning into natural Russian, keep proper names and terms recognisable\n"
            "- Literary but precise tone: an intelligent morning column, no clickbait, no emoji\n"
            "- Open with one short paragraph about the overall picture of the day\n"
            f"- About {target_words} words total — do not pad with filler or philosophy\n"
            "- Plain text only: no markdown, no HTML, no headings, no lists\n"
        ))

        response = await self._retry(
            lambda: self._llm.ainvoke([system, human]), "News digest",
        )
        if response is None:
            return ""
        text = _as_text(response.content)
        logger.info("LLM digest written: %d chars for %d articles", len(text), len(articles))
        return text
