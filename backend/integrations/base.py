from __future__ import annotations


class BaseIntegration:
    """Маркерный базовый класс для всех интеграций.

    Конкретный интерфейс определяется в каждом наследнике —
    методы у Google Sheets, Telegram и Weather принципиально разные.
    """
