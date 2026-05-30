from __future__ import annotations

from dataclasses import asdict

from dishka.integrations.litestar import FromDishka
from litestar import Controller, get, post

from backend.services.content_service import ContentService
from backend.services.focus_resolver import FocusResolver
from backend.services.llm_service import ContentCandidate, LLMService


class DebugController(Controller):
    path = "/api/debug"

    @get("/focus-resolve")
    async def focus_resolve(  # noqa: PLR6301
        self, focus_resolver: FromDishka[FocusResolver],
    ) -> dict:
        focus = await focus_resolver.resolve()
        return asdict(focus)

    @post("/llm-queries")
    async def llm_queries(  # noqa: PLR6301
        self,
        focus_resolver: FromDishka[FocusResolver],
        llm_service: FromDishka[LLMService],
    ) -> dict:
        focus = await focus_resolver.resolve()
        queries = await llm_service.generate_search_queries(focus.description, focus.topics)
        return {
            "focus": focus.description,
            "source": focus.source,
            "queries": [asdict(q) for q in queries],
        }

    @post("/llm-select")
    async def llm_select(  # noqa: PLR6301
        self,
        focus_resolver: FromDishka[FocusResolver],
        llm_service: FromDishka[LLMService],
        content_service: FromDishka[ContentService],
    ) -> dict:
        focus = await focus_resolver.resolve()
        candidates = await content_service.get_new_candidates(focus.topics, limit=30)
        candidate_dtos = [
            ContentCandidate(
                id=c.id, title=c.title, topic=c.topic,
                source=c.source, type=c.type.value,
            )
            for c in candidates
        ]
        selected_ids = await llm_service.select_content(candidate_dtos, focus.description, n=6)
        return {
            "focus": focus.description,
            "candidates_count": len(candidates),
            "selected_ids": selected_ids,
        }

    @post("/collect-dynamic")
    async def collect_dynamic(  # noqa: PLR6301
        self,
        focus_resolver: FromDishka[FocusResolver],
        llm_service: FromDishka[LLMService],
        content_service: FromDishka[ContentService],
    ) -> dict:
        focus = await focus_resolver.resolve()
        queries = await llm_service.generate_search_queries(focus.description, focus.topics)
        collected = await content_service.collect_dynamic(queries)
        return {
            "focus": focus.description,
            "queries_count": len(queries),
            "collected": collected,
        }

    @post("/morning-content")
    async def morning_content(  # noqa: PLR6301
        self,
        focus_resolver: FromDishka[FocusResolver],
        llm_service: FromDishka[LLMService],
        content_service: FromDishka[ContentService],
    ) -> dict:
        focus = await focus_resolver.resolve()
        candidates = await content_service.get_new_candidates(focus.topics, limit=30)

        # LLM-выборка с fallback
        items = []
        try:
            candidate_dtos = [
                ContentCandidate(
                    id=c.id, title=c.title, topic=c.topic,
                    source=c.source, type=c.type.value,
                )
                for c in candidates
            ]
            selected_ids = await llm_service.select_content(candidate_dtos, focus.description, n=6)
            if selected_ids:
                id_order = {id_: i for i, id_ in enumerate(selected_ids)}
                items = sorted(
                    [c for c in candidates if c.id in id_order],
                    key=lambda c: id_order[c.id],
                )[:6]
                method = "llm"
            else:
                items = await content_service.select_for_morning(focus.topics, n=6)
                method = "fallback"
        except Exception:
            items = await content_service.select_for_morning(focus.topics, n=6)
            method = "fallback"

        return {
            "focus": focus.description,
            "method": method,
            "items": [
                {
                    "id": item.id,
                    "title": item.title,
                    "topic": item.topic,
                    "source": item.source,
                    "type": item.type.value if hasattr(item.type, "value") else item.type,
                    "url": item.url,
                }
                for item in items
            ],
        }
