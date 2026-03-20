from __future__ import annotations

import logging
from typing import Any

from backend.agents.base import BaseAgent
from backend.services.content_service import ALL_TOPICS, ContentService
from backend.services.focus_service import FocusService

logger = logging.getLogger(__name__)


class ContentAgent(BaseAgent):
    """Подбирает контент для утренней сводки под текущий фокус пользователя.
    Добавляет в state ключ `content_items`.
    """

    def __init__(self, content_service: ContentService, focus_service: FocusService) -> None:
        self._content = content_service
        self._focus = focus_service

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        priority_topics = await self._resolve_topics()

        try:
            items = await self._content.select_for_morning(priority_topics, n=3)
        except Exception:
            logger.exception("Failed to select content")
            items = []

        return {**state, "content_items": items}

    async def _resolve_topics(self) -> list[str]:
        """Берёт фокус недели и ставит его топик первым."""
        try:
            focus = await self._focus.get_current_week_focus()
            if focus:
                desc = focus.description.lower()
                matched = [t for t in ALL_TOPICS if t in desc]
                if matched:
                    return matched + [t for t in ALL_TOPICS if t not in matched]
        except Exception:
            logger.exception("Failed to resolve topics from focus")
        return ALL_TOPICS
