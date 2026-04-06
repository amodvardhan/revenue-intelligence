"""Story 3.1 — OpenAI model identifier comes from settings, not hardcoded in request path."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.query_engine.llm import complete_nl_plan


class _FakeResponse:
    status_code = 200

    def json(self) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"needs_clarification": false, "intent": "rollup", "hierarchy": "org", "revenue_date_from": "2026-01-01", "revenue_date_to": "2026-01-31", "interpretation": "test"}'
                    }
                }
            ]
        }


class _FakeClient:
    def __init__(self, **kwargs: object) -> None:
        self.captured: dict | None = None

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(self, url: str, headers: dict | None = None, json: dict | None = None) -> _FakeResponse:
        self.captured = json
        return _FakeResponse()


@pytest.mark.asyncio
async def test_complete_nl_plan_uses_openai_model_from_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeClient()
    monkeypatch.setattr(
        "app.services.query_engine.llm.httpx.AsyncClient",
        lambda **kw: fake,
    )
    monkeypatch.setattr(
        "app.services.query_engine.llm.get_settings",
        lambda: SimpleNamespace(
            OPENAI_API_KEY="sk-test",
            OPENAI_MODEL="custom-model-from-env",
            QUERY_TIMEOUT_SECONDS=30,
        ),
    )
    out = await complete_nl_plan("total revenue January 2026")
    assert out.get("intent") == "rollup"
    assert fake.captured is not None
    assert fake.captured.get("model") == "custom-model-from-env"
