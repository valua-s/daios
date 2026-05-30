from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.integrations.news import NewsClient
from backend.integrations.rss import RSSParser
from backend.integrations.vk import VKClient
from backend.integrations.youtube import YouTubeClient
from backend.models.content import ContentItem, ContentStatus, ContentType
from backend.repositories.content_repo import ContentRepository
from backend.services.llm_service import SearchQuery

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
        all_items = []
        for topic, urls in feeds.items():
            for url in urls:
                all_items.extend(await self._rss.fetch(url, topic))

        candidate_urls = [i.url for i in all_items if i.url]
        existing = await self._repo.get_existing_urls(candidate_urls)

        saved = 0
        for item in all_items:
            if not item.url or item.url in existing:
                continue
            await self._repo.create(
                type=ContentType.article,
                url=item.url,
                title=item.title,
                topic=item.topic,
                source="rss",
                status=ContentStatus.new,
            )
            existing.add(item.url)
            saved += 1

        logger.info("RSS: saved %d new items", saved)
        return saved

    async def collect_youtube(self, topics: list[str] | None = None) -> int:
        """Ищет видео на YouTube и сохраняет новые. Возвращает кол-во новых."""
        queries = {t: q for t, q in _YOUTUBE_QUERIES.items() if not topics or t in topics}
        all_videos = []
        for topic, query in queries.items():
            all_videos.extend(await self._youtube.search(query, topic, max_results=3))

        existing = await self._repo.get_existing_urls([v.url for v in all_videos])

        saved = 0
        for video in all_videos:
            if video.url in existing:
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
            existing.add(video.url)
            saved += 1

        logger.info("YouTube: saved %d new items", saved)
        return saved

    async def collect_vk(self, topics: list[str] | None = None) -> int:
        """Ищет видео в VK и сохраняет новые. Возвращает кол-во новых."""
        queries = {t: q for t, q in _VK_QUERIES.items() if not topics or t in topics}
        all_videos = []
        for topic, query in queries.items():
            all_videos.extend(await self._vk.search_videos(query, topic, max_results=3))

        existing = await self._repo.get_existing_urls([v.url for v in all_videos])

        saved = 0
        for video in all_videos:
            if video.url in existing:
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
            existing.add(video.url)
            saved += 1

        logger.info("VK: saved %d new items", saved)
        return saved

    async def collect_news(self, topics: list[str] | None = None) -> int:
        """Ищет статьи через NewsAPI и сохраняет новые. Возвращает кол-во новых."""
        queries = {t: q for t, q in _NEWS_QUERIES.items() if not topics or t in topics}
        all_articles = []
        for topic, query in queries.items():
            all_articles.extend(await self._news.search(query, topic, max_results=3))

        candidate_urls = [a.url for a in all_articles if a.url]
        existing = await self._repo.get_existing_urls(candidate_urls)

        saved = 0
        for article in all_articles:
            if not article.url or article.url in existing:
                continue
            await self._repo.create(
                type=ContentType.article,
                url=article.url,
                title=article.title,
                topic=article.topic,
                source="newsapi",
                status=ContentStatus.new,
            )
            existing.add(article.url)
            saved += 1

        logger.info("NewsAPI: saved %d new items", saved)
        return saved

    async def select_for_morning(
        self, priority_topics: list[str], n: int = 6
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

        return selected

    async def get_new_candidates(
        self, priority_topics: list[str], limit: int = 30,
    ) -> list[ContentItem]:
        """Все new-элементы из БД, приоритет по топикам."""
        ordered = priority_topics + [t for t in ALL_TOPICS if t not in priority_topics]
        candidates: list[ContentItem] = []
        for topic in ordered:
            if len(candidates) >= limit:
                break
            items = await self._repo.get_new_by_topic(topic, limit=limit - len(candidates))
            candidates.extend(items)
        return candidates[:limit]

    async def mark_queued(self, items: list[ContentItem]) -> None:
        """Пометить выбранные элементы как queued."""
        for item in items:
            await self._repo.update(item.id, status=ContentStatus.queued)

    async def collect_dynamic(self, queries: list[SearchQuery]) -> int:
        """Выполнить LLM-сгенерированные запросы через NewsAPI/YouTube."""
        saved = 0
        for q in queries:
            if q.source == "newsapi":
                articles = await self._news.search(q.query, q.topic, max_results=3)
                candidate_urls = [a.url for a in articles if a.url]
                existing = await self._repo.get_existing_urls(candidate_urls)
                for article in articles:
                    if not article.url or article.url in existing:
                        continue
                    await self._repo.create(
                        type=ContentType.article,
                        url=article.url,
                        title=article.title,
                        topic=q.topic,
                        source="newsapi_dynamic",
                        status=ContentStatus.new,
                    )
                    existing.add(article.url)
                    saved += 1
            elif q.source == "youtube":
                videos = await self._youtube.search(q.query, q.topic, max_results=3)
                existing = await self._repo.get_existing_urls([v.url for v in videos])
                for video in videos:
                    if video.url in existing:
                        continue
                    await self._repo.create(
                        type=ContentType.video,
                        url=video.url,
                        title=video.title,
                        topic=q.topic,
                        source="youtube_dynamic",
                        status=ContentStatus.new,
                        duration_minutes=video.duration_minutes,
                    )
                    existing.add(video.url)
                    saved += 1

        logger.info("Dynamic collection: saved %d new items from %d queries", saved, len(queries))
        return saved

    async def mark_shown(self, item_ids: list[int]) -> None:
        for item_id in item_ids:
            await self._repo.mark_shown(item_id)
