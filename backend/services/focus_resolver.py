from __future__ import annotations

import logging
from dataclasses import dataclass

from backend.services.content_service import ALL_TOPICS
from backend.services.focus_service import FocusService
from backend.services.settings_service import SettingsService

logger = logging.getLogger(__name__)


@dataclass
class FocusContext:
    description: str
    topics: list[str]
    source: str  # "week_focus" | "month_focus" | "interests"


class FocusResolver:
    """Определяет текущий фокус: неделя → месяц → интересы."""

    def __init__(self, focus_service: FocusService, settings_service: SettingsService) -> None:
        self._focus = focus_service
        self._settings = settings_service

    async def resolve(self) -> FocusContext:
        # 1. Фокус недели
        week = await self._focus.get_current_week_focus()
        if week:
            topics = _extract_topics(week.description)
            return FocusContext(
                description=week.description,
                topics=topics,
                source="week_focus",
            )

        # 2. Фокус месяца
        month = await self._focus.get_current_month_focus()
        if month:
            topics = _extract_topics(month.description)
            return FocusContext(
                description=month.description,
                topics=topics,
                source="month_focus",
            )

        # 3. Интересы пользователя
        interests = await self._settings.get_interests()
        enabled = [k for k, v in interests.items() if v]
        if not enabled:
            enabled = list(ALL_TOPICS)

        description = "Общие интересы: " + ", ".join(enabled)
        return FocusContext(
            description=description,
            topics=enabled,
            source="interests",
        )


def _extract_topics(description: str) -> list[str]:
    """Извлекает топики из описания фокуса, остальные — в конец."""
    desc_lower = description.lower()
    matched = [t for t in ALL_TOPICS if t in desc_lower]
    rest = [t for t in ALL_TOPICS if t not in matched]
    if matched:
        return matched + rest
    return list(ALL_TOPICS)
