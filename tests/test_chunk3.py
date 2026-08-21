import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import app as app_module
from ai_service import MAX_HISTORY_MESSAGES
from providers.base import AIProvider

ROOT = Path(__file__).resolve().parents[1]


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


class ChunkThreeTests(unittest.TestCase):
    def setUp(self):
        self.provider = RecordingProvider()
        self.provider_patch = patch.object(app_module, "current_provider", return_value=self.provider)
        self.provider_patch.start()
        self.client = TestClient(app_module.app)

    def tearDown(self):
        self.provider_patch.stop()

    def test_owner_and_store_surfaces_are_separate(self):
        root = self.client.get("/", follow_redirects=False)
        self.assertEqual(root.status_code, 307)
        self.assertEqual(root.headers["location"], "/owner")

        owner = self.client.get("/owner")
        store = self.client.get("/store")
        self.assertEqual(owner.status_code, 200)
        self.assertIn("BUSINESS BRAIN", owner.text)
        self.assertIn("Business Knowledge", owner.text)
        self.assertIn("Conversations", owner.text)
        self.assertEqual(store.status_code, 200)
        self.assertIn("Northstar Botanics", store.text)
        self.assertIn("chatLauncher", store.text)

    def test_store_widget_reuses_existing_chat_endpoint_and_owner_is_now_dashboard(self):
        source = (ROOT / "static" / "store.js").read_text(encoding="utf-8")
        owner_source = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn("fetch('/api/chat'", source)
        self.assertIn("ags.chunk3.storeConversationMessages", source)
        self.assertIn("const MAX_MODEL_HISTORY = 8", source)
        self.assertIn("messages.slice(-MAX_MODEL_HISTORY)", source)
        self.assertIn("/owner-api/conversations", owner_source)
        self.assertIn("/owner-api/knowledge", owner_source)
        self.assertNotIn("GEMINI_API_KEY", owner_source)

    def test_api_chat_still_uses_provider_neutral_service_and_bounded_history(self):
        history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"message-{i}"}
            for i in range(MAX_HISTORY_MESSAGES)
        ]
        response = self.client.post(
            "/api/chat",
            json={
                "business_knowledge": "Cloud Cream — $28 — for dry skin.",
                "history": history,
                "message": "How much did you say it costs?",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"answer": "controlled answer"})
        self.assertEqual(self.provider.received_messages[0]["role"], "system")
        self.assertEqual(len(self.provider.received_messages), MAX_HISTORY_MESSAGES + 2)
        self.assertEqual(self.provider.received_messages[-1]["content"], "How much did you say it costs?")

    def test_frontend_and_app_do_not_gain_gemini_specific_transport_logic(self):
        app_source = (ROOT / "app.py").read_text(encoding="utf-8")
        store_source = (ROOT / "static" / "store.js").read_text(encoding="utf-8")

        forbidden = [
            "generativelanguage.googleapis.com",
            "GEMINI_API_KEY",
            "Authorization: Bearer",
        ]
        for term in forbidden:
            self.assertNotIn(term, app_source)
            self.assertNotIn(term, store_source)

    def test_store_is_mock_only_and_contains_no_ecommerce_integration(self):
        store_html = (ROOT / "static" / "store.html").read_text(encoding="utf-8")
        store_js = (ROOT / "static" / "store.js").read_text(encoding="utf-8")

        self.assertIn("controlled mock storefront", store_html.lower())
        self.assertNotIn("shopify", store_js.lower())
        self.assertNotIn("stripe", store_js.lower())
        self.assertNotIn("checkout", store_js.lower())


if __name__ == "__main__":
    unittest.main()
