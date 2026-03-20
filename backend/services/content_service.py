from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.integrations.news import NewsClient
from backend.integrations.rss import RSSParser
from backend.integrations.vk import VKClient
from backend.integrations.youtube import YouTubeClient
from backend.models.content import ContentItem, ContentStatus, ContentType
from backend.repositories.content_repo import ContentRepository

logger = logging.getLogger(__name__)

# RSS-ленты по топикам. Расширяются через настройки в v1.
_RSS_FEEDS: dict[str, list[str]] = {
    "python": [
        "https://realpython.com/atom.xml",
        "https://blog.python.org/feeds/posts/default",
    ],
    "ai": [
        "https://huggingface.co/blog/feed.xml",
        "https://tldr.tech/ai/rss",
    ],
    "running": [
        "https://www.runnersworld.com/feeds/all",
    ],
    "economics": [
        "https://feeds.bbci.co.uk/news/business/rss.xml",
    ],
}

# YouTube-запросы по топикам
_YOUTUBE_QUERIES: dict[str, str] = {
    "python": "python programming tutorial 2024",
    "ai": "artificial intelligence news 2024",
    "running": "бег тренировка советы",
    "economics": "экономика финансы новости",
}

# VK-запросы по топикам
_VK_QUERIES: dict[str, str] = {
    "running": "бег тренировка пробежка",
    "python": "python программирование",
}

# NewsAPI-запросы по топикам
_NEWS_QUERIES: dict[str, str] = {
    "python": "python разработка программирование",
    "ai": "искусственный интеллект нейросети",
    "running": "бег марафон тренировки",
    "economics": "экономика финансы рынки",
}

ALL_TOPICS = list(_RSS_FEEDS.keys())


class ContentService:
    """Сбор и подбор контента для показа пользователю."""

    def __init__(
        self,
        session: AsyncSession,
        rss_parser: RSSParser,
        youtube_client: YouTubeClient,
        vk_client: VKClient,
        news_client: NewsClient,
    ) -> None:
        self._repo = ContentRepository(session)
        self._session = session
        self._rss = rss_parser
        self._youtube = youtube_client
        self._vk = vk_client
        self._news = news_client

    async def collect_rss(self, topics: list[str] | None = None) -> int:
        """Парсит RSS-ленты и сохраняет новые статьи. Возвращает кол-во новых."""
        feeds = {t: v for t, v in _RSS_FEEDS.items() if not topics or t in topics}
        saved = 0
        for topic, urls in feeds.items():
            for url in urls:
                for item in await self._rss.fetch(url, topic):
                    if not item.url or await self._repo.get_by_url(item.url):
                        continue
                    await self._repo.create(
                        type=ContentType.article,
                        url=item.url,
                        title=item.title,
                        topic=item.topic,
                        source="rss",
                        status=ContentStatus.new,
                    )
                    saved += 1
        await self._session.commit()
        logger.info("RSS: saved %d new items", saved)
        return saved

    async def collect_youtube(self, topics: list[str] | None = None) -> int:
        """Ищет видео на YouTube и сохраняет новые. Возвращает кол-во новых."""
        queries = {t: q for t, q in _YOUTUBE_QUERIES.items() if not topics or t in topics}
        saved = 0
        for topic, query in queries.items():
            for video in await self._youtube.search(query, topic, max_results=3):
                if await self._repo.get_by_url(video.url):
                    continue
                await self._repo.create(
                    type=ContentType.video,
                    url=video.url,
                    title=video.title,
                    topic=video.topic,
                    source="youtube",
                    status=ContentStatus.new,
                    duration_minutes=video.duration_minutes,
                )
                saved += 1
        await self._session.commit()
        logger.info("YouTube: saved %d new items", saved)
        return saved

    async def collect_vk(self, topics: list[str] | None = None) -> int:
        """Ищет видео в VK и сохраняет новые. Возвращает кол-во новых."""
        queries = {t: q for t, q in _VK_QUERIES.items() if not topics or t in topics}
        saved = 0
        for topic, query in queries.items():
            for video in await self._vk.search_videos(query, topic, max_results=3):
                if await self._repo.get_by_url(video.url):
                    continue
                await self._repo.create(
                    type=ContentType.video,
                    url=video.url,
                    title=video.title,
                    topic=video.topic,
                    source="vk",
                    status=ContentStatus.new,
                    duration_minutes=video.duration_minutes,
                )
                saved += 1
        await self._session.commit()
        logger.info("VK: saved %d new items", saved)
        return saved

    async def collect_news(self, topics: list[str] | None = None) -> int:
        """Ищет статьи через NewsAPI и сохраняет новые. Возвращает кол-во новых."""
        queries = {t: q for t, q in _NEWS_QUERIES.items() if not topics or t in topics}
        saved = 0
        for topic, query in queries.items():
            for article in await self._news.search(query, topic, max_results=3):
                if not article.url or await self._repo.get_by_url(article.url):
                    continue
                await self._repo.create(
                    type=ContentType.article,
                    url=article.url,
                    title=article.title,
                    topic=article.topic,
                    source="newsapi",
                    status=ContentStatus.new,
                )
                saved += 1
        await self._session.commit()
        logger.info("NewsAPI: saved %d new items", saved)
        return saved

    async def select_for_morning(
        self, priority_topics: list[str], n: int = 3
    ) -> list[ContentItem]:
        """Выбирает n материалов для утреннего показа, приоритет по топикам.
        Переводит отобранные в статус queued.
        """
        # Приоритизированные топики первыми, остальные — в конце
        ordered = priority_topics + [t for t in ALL_TOPICS if t not in priority_topics]
        selected: list[ContentItem] = []
        for topic in ordered:
            if len(selected) >= n:
                break
            items = await self._repo.get_new_by_topic(topic, limit=n - len(selected))
            selected.extend(items)

        for item in selected:
            await self._repo.update(item.id, status=ContentStatus.queued)
        await self._session.commit()
        return selected

    async def mark_shown(self, item_ids: list[int]) -> None:
        for item_id in item_ids:
            await self._repo.mark_shown(item_id)
        await self._session.commit()
