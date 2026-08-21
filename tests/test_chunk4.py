import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import app as app_module
from ai_service import MAX_HISTORY_MESSAGES
from embed_security import embed_rate_limiter
from providers.base import AIProvider

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ORIGIN = "http://127.0.0.1:9000"


class RecordingProvider(AIProvider):
    def __init__(self):
        self.received_messages = None

    @property
    def name(self):
        return "recording"

    @property
    def model(self):
        return "recording-model"

    @property
    def is_configured(self):
        return True

    def generate(self, messages):
        self.received_messages = messages
        return "controlled answer"


class ChunkFourTests(unittest.TestCase):
    def setUp(self):
        self.provider = RecordingProvider()
        self.provider_patch = patch.object(app_module, "current_provider", return_value=self.provider)
        self.provider_patch.start()
        embed_rate_limiter.reset()
        self.original_limit = embed_rate_limiter.limit
        self.client = TestClient(app_module.app)

    def tearDown(self):
        embed_rate_limiter.limit = self.original_limit
        embed_rate_limiter.reset()
        self.provider_patch.stop()

    def test_embed_script_is_served_and_external_site_uses_only_tiny_snippet(self):
        response = self.client.get("/embed.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/javascript", response.headers["content-type"])

        external_html = (ROOT / "external-test-site" / "index.html").read_text(encoding="utf-8")
        self.assertIn('src="http://127.0.0.1:8000/embed.js"', external_html)
        self.assertIn('data-ags-deployment="northstar-website-default"', external_html)
        self.assertNotIn("DEMO_BUSINESS_KNOWLEDGE", external_html)
        self.assertNotIn("business_knowledge", external_html)
        self.assertNotIn("GEMINI_API_KEY", external_html)

    def test_embed_widget_keeps_visible_history_but_server_owns_model_context(self):
        source = (ROOT / "static" / "embed.js").read_text(encoding="utf-8")
        self.assertIn("ags.chunk5.embed", source)
        self.assertIn("conversationId", source)
        self.assertIn("conversation_id", source)
        self.assertIn("deployment_key", source)
        self.assertIn("/embed-api/chat", source)
        self.assertNotIn("business_knowledge", source)
        self.assertNotIn("messages.slice(-maxModelHistory)", source)
        self.assertNotIn("history:", source)

    def test_allowed_origin_can_use_embed_api_and_gets_cors_header(self):
        response = self.client.post(
            "/embed-api/chat",
            headers={"Origin": ALLOWED_ORIGIN},
            json={"message": "Which one is for dry skin?"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "controlled answer")
        self.assertTrue(response.json()["conversation_id"])
        self.assertEqual(response.headers.get("access-control-allow-origin"), ALLOWED_ORIGIN)
        self.assertIn("Cloud Cream", self.provider.received_messages[0]["content"])

    def test_disallowed_or_missing_origin_is_rejected(self):
        for headers in ({}, {"Origin": "https://evil.example"}):
            response = self.client.post(
                "/embed-api/chat",
                headers=headers,
                json={"message": "Hello"},
            )
            self.assertEqual(response.status_code, 403)

    def test_preflight_allows_only_configured_external_site(self):
        allowed = self.client.options(
            "/embed-api/chat",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.headers.get("access-control-allow-origin"), ALLOWED_ORIGIN)

        denied = self.client.options(
            "/embed-api/chat",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "POST",
            },
        )
        self.assertEqual(denied.status_code, 400)
        self.assertIsNone(denied.headers.get("access-control-allow-origin"))

    def test_embed_backend_loads_and_bounds_server_owned_history(self):
        conversation_id = None
        for i in range(6):
            response = self.client.post(
                "/embed-api/chat",
                headers={"Origin": ALLOWED_ORIGIN},
                json={
                    "conversation_id": conversation_id,
                    "message": f"turn-{i}",
                },
            )
            self.assertEqual(response.status_code, 200)
            conversation_id = response.json()["conversation_id"]

        self.assertEqual(len(self.provider.received_messages), MAX_HISTORY_MESSAGES + 2)
        self.assertEqual(self.provider.received_messages[-1]["content"], "turn-5")
        self.assertNotIn("turn-0", [item["content"] for item in self.provider.received_messages])

    def test_minimum_rate_limit_returns_429(self):
        embed_rate_limiter.limit = 2
        for _ in range(2):
            response = self.client.post(
                "/embed-api/chat",
                headers={"Origin": ALLOWED_ORIGIN},
                json={"message": "Hello"},
            )
            self.assertEqual(response.status_code, 200)

        blocked = self.client.post(
            "/embed-api/chat",
            headers={"Origin": ALLOWED_ORIGIN},
            json={"message": "One more"},
        )
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.headers.get("retry-after"), "60")

    def test_public_embed_mode_disables_client_supplied_knowledge_endpoint(self):
        with patch.dict(os.environ, {"PUBLIC_EMBED_ONLY": "true"}):
            response = self.client.post(
                "/api/chat",
                json={"business_knowledge": "anything", "history": [], "message": "Hello"},
            )
        self.assertEqual(response.status_code, 404)

    def test_provider_abstraction_remains_isolated(self):
        app_source = (ROOT / "app.py").read_text(encoding="utf-8")
        embed_source = (ROOT / "static" / "embed.js").read_text(encoding="utf-8")
        external_source = (ROOT / "external-test-site" / "index.html").read_text(encoding="utf-8")
        forbidden = ["generativelanguage.googleapis.com", "GEMINI_API_KEY", "x-goog-api-key"]
        for term in forbidden:
            self.assertNotIn(term, app_source)
            self.assertNotIn(term, embed_source)
            self.assertNotIn(term, external_source)

    def test_render_blueprint_is_public_embed_only_and_keeps_secrets_out_of_source(self):
        blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")
        self.assertIn("PUBLIC_EMBED_ONLY", blueprint)
        self.assertIn('value: "true"', blueprint)
        self.assertIn("GEMINI_API_KEY", blueprint)
        self.assertIn("DATABASE_URL", blueprint)
        self.assertIn("ALLOWED_EMBED_ORIGINS", blueprint)
        self.assertGreaterEqual(blueprint.count("sync: false"), 3)
        self.assertIn("alembic upgrade head", blueprint)
        self.assertIn("uvicorn app:app --host 0.0.0.0 --port $PORT", blueprint)


if __name__ == "__main__":
    unittest.main()
