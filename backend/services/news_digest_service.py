from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from operator import itemgetter

from backend.integrations.news import NewsArticle, NewsProvider
from backend.services.content_service import ContentService
from backend.services.focus_resolver import FocusResolver
from backend.services.llm_service import DigestArticle, LLMService

logger = logging.getLogger(__name__)

_TOPIC_QUERIES: dict[str, str] = {
    "python": "python programming",
    "ai": "artificial intelligence",
    "running": "running marathon training",
    "economics": "economy markets finance",
    "politics": "world politics",
}

_MAX_TOPICS = 4
_PER_SOURCE = 5
_MAX_CANDIDATES = 40
_MAX_DIGEST_ARTICLES = 10
_FRESH_HOURS = 24
_TITLE_KEY_LENGTH = 60


@dataclass
class NewsDigest:
    text: str
    articles: list[NewsArticle]


def _topic_query(topic: str) -> str:
    return _TOPIC_QUERIES.get(topic, topic.replace("_", " "))


def _title_key(title: str) -> str:
    return " ".join(title.lower().split())[:_TITLE_KEY_LENGTH]


def _sort_key(article: NewsArticle) -> datetime:
    return article.published_at or datetime.min.replace(tzinfo=UTC)


def _to_dtos(articles: list[NewsArticle]) -> list[DigestArticle]:
    return [
        DigestArticle(
            index=i, title=a.title, summary=a.summary, source=a.source, topic=a.topic,
        )
        for i, a in enumerate(articles, 1)
    ]


class NewsDigestService:
    """Собирает свежие новости по интересам и пишет по ним сводку на русском."""

    def __init__(
        self,
        providers: list[NewsProvider],
        content_service: ContentService,
        focus_resolver: FocusResolver,
        llm_service: LLMService,
    ) -> None:
        self._providers = providers
        self._content = content_service
        self._focus = focus_resolver
        self._llm = llm_service

    async def build(self) -> NewsDigest | None:
        focus = await self._focus.resolve()
        topics = focus.topics[:_MAX_TOPICS]

        collected = await self._collect(topics)
        if not collected:
            logger.info("News digest skipped: no articles from providers")
            return None

        unseen = await self._content.filter_unseen(collected)
        if not unseen:
            logger.info("News digest skipped: all %d articles already seen", len(collected))
            return None

        relevant, judged = await self._select_relevant(unseen, focus.description)
        if not relevant:
            logger.info("News digest skipped: nothing passed relevance score")
            return None

        text = await self._llm.write_news_digest(_to_dtos(relevant), focus.description)
        if not text:
            logger.warning("News digest skipped: empty text from LLM")
            return None

        await self._content.save_digest_articles(unseen if judged else relevant)
        logger.info("News digest built: %d of %d articles, topics=%s", len(relevant), len(unseen), topics)
        return NewsDigest(text=text, articles=relevant)

    async def _select_relevant(
        self, articles: list[NewsArticle], focus_description: str,
    ) -> tuple[list[NewsArticle], bool]:
        """Оставляет новости с высоким скором. Второе значение — удалось ли оценить."""
        try:
            scores = await self._llm.score_relevance(_to_dtos(articles), focus_description)
        except Exception:
            logger.exception("Relevance scoring failed, keeping all collected articles")
            return articles[:_MAX_DIGEST_ARTICLES], False

        if not scores:
            logger.warning("Relevance scoring returned nothing, keeping all collected articles")
            return articles[:_MAX_DIGEST_ARTICLES], False

        ranked = [(scores.get(i, 0), a) for i, a in enumerate(articles, 1)]
        ranked.sort(key=itemgetter(0), reverse=True)
        logger.info("Relevance scores: %s", [score for score, _ in ranked])

        if ranked[0][0] <= 0:
            logger.info("Nothing relevant: top score is %d", ranked[0][0])
            return [], True

        kept = ranked[:_MAX_DIGEST_ARTICLES]
        for score, article in ranked[_MAX_DIGEST_ARTICLES:]:
            logger.info("Dropped (%d): %s", score, article.title[:80])
        logger.info(
            "Relevance filter: top %d of %d, scores %d..%d",
            len(kept), len(articles), kept[0][0], kept[-1][0],
        )
        return [article for _, article in kept], True

    async def _collect(self, topics: list[str]) -> list[NewsArticle]:
        batches = await asyncio.gather(*[
            self._search_topics(provider, topics)
            for provider in self._providers
            if provider.enabled
        ])
        since = datetime.now(tz=UTC) - timedelta(hours=_FRESH_HOURS)

        seen_urls: set[str] = set()
        seen_titles: set[str] = set()
        unique: list[NewsArticle] = []
        for article in [a for batch in batches for a in batch]:
            title_key = _title_key(article.title)
            if not article.title or not article.url:
                continue
            if article.published_at is not None and article.published_at < since:
                continue
            if article.url in seen_urls or title_key in seen_titles:
                continue
            seen_urls.add(article.url)
            seen_titles.add(title_key)
            unique.append(article)

        unique.sort(key=_sort_key, reverse=True)
        return unique[:_MAX_CANDIDATES]

    @staticmethod
    async def _search_topics(
        provider: NewsProvider, topics: list[str],
    ) -> list[NewsArticle]:
        """Топики внутри провайдера — последовательно, чтобы не ловить 429."""
        articles: list[NewsArticle] = []
        for topic in topics:
            articles.extend(await provider.search(_topic_query(topic), topic, _PER_SOURCE))
        return articles
