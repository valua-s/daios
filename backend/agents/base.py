from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """Общий интерфейс для всех LangGraph-агентов.

    Каждый агент реализует один метод run() — нода в графе.
    Агент получает state, делает своё дело, возвращает обновлённый state.
    """

    @abstractmethod
    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Выполнить задачу агента.

        Args:
            state: Текущий state LangGraph-графа.

        Returns:
            Обновлённый state с результатами работы агента.
        """
        ...

    @property
    def name(self) -> str:
        
        """Имя агента для логов и отладки."""
        return self.__class__.__name__
