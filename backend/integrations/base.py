from __future__ import annotations

from abc import ABC


class BaseIntegration(ABC):
    """Маркерный базовый класс для всех интеграций.
    Конкретный интерфейс определяется в каждом наследнике —
    методы у Google Sheets, Telegram и Weather принципиально разные.
    """
