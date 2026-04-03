from __future__ import annotations

import logging
from typing import Any

from backend.agents.base import BaseAgent
from backend.models.content import ContentItem
from backend.services.content_service import ALL_TOPICS, ContentService
from backend.services.focus_resolver import FocusResolver
from backend.services.llm_service import ContentCandidate, LLMService

logger = logging.getLogger(__name__)


class ContentAgent(BaseAgent):
    """Подбирает контент для утренней сводки: LLM-выборка с fallback на приоритет по топикам."""

    def __init__(
        self,
        content_service: ContentService,
        focus_resolver: FocusResolver,
        llm_service: LLMService,
    ) -> None:
        self._content = content_service
        self._focus_resolver = focus_resolver
        self._llm = llm_service

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        focus = await self._focus_resolver.resolve()
        logger.info("Focus resolved: source=%s, topics=%s", focus.source, focus.topics)

        try:
            items = await self._select_with_llm(focus.description, focus.topics)
        except Exception:
            logger.exception("LLM content selection failed, falling back")
            items = await self._fallback_select(focus.topics)

        return {**state, "content_items": items}

    async def _select_with_llm(
        self, focus_description: str, topics: list[str],
    ) -> list[ContentItem]:
        candidates = await self._content.get_new_candidates(topics, limit=30)
        if not candidates:
            return []

        candidate_dtos = [
            ContentCandidate(
                id=c.id,
                title=c.title,
                topic=c.topic,
                source=c.source,
                type=c.type.value,
            )
            for c in candidates
        ]

        selected_ids = await self._llm.select_content(candidate_dtos, focus_description, n=6)
        if not selected_ids:
            return await self._fallback_select(topics)

        # Фильтруем и сохраняем порядок LLM
        id_order = {id_: i for i, id_ in enumerate(selected_ids)}
        selected = [c for c in candidates if c.id in id_order]
        selected.sort(key=lambda c: id_order[c.id])

        await self._content.mark_queued(selected)
        return selected[:6]

    async def _fallback_select(self, topics: list[str]) -> list[ContentItem]:
        """Текущая логика: приоритет по топикам из БД."""
        return await self._content.select_for_morning(topics, n=6)
