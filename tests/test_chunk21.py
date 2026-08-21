import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ai_service import AIService, MAX_HISTORY_MESSAGES, UNKNOWN_ANSWER, build_instructions, build_messages
from providers import get_provider
from providers.base import AIProvider, UnsupportedProviderError
from providers.gemini import GeminiProvider, GEMINI_CHAT_URL


class FakeProvider(AIProvider):
    def __init__(self):
        self.received_messages = None

    @property
    def name(self):
        return "fake"

    @property
    def model(self):
        return "fake-model"

    @property
    def is_configured(self):
        return True

    def generate(self, messages):
        self.received_messages = messages
        return "fake answer"


class ChunkTwoPointOneTests(unittest.TestCase):
    def test_instructions_keep_business_facts_grounded(self):
        text = build_instructions("Shipping: 2-4 days")
        self.assertIn("Shipping: 2-4 days", text)
        self.assertIn(UNKNOWN_ANSWER, text)
        self.assertIn("Use ONLY", text)
        self.assertIn("recent conversation", text)

    def test_messages_include_history_before_current_message(self):
        history = [
            {"role": "user", "content": "Which one is for dry skin?"},
            {"role": "assistant", "content": "House Blend."},
        ]
        messages = build_messages(
            "House Blend: $18, for dry skin",
            history,
            "How much does this one cost?",
        )
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")
        self.assertEqual(messages[2]["role"], "assistant")
        self.assertEqual(messages[-1], {"role": "user", "content": "How much does this one cost?"})

    def test_history_is_bounded(self):
        history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"}
            for i in range(MAX_HISTORY_MESSAGES + 4)
        ]
        messages = build_messages("Product: A", history, "current")
        self.assertEqual(len(messages), MAX_HISTORY_MESSAGES + 2)
        self.assertEqual(messages[1]["content"], "m4")

    def test_ai_service_depends_only_on_provider_interface(self):
        provider = FakeProvider()
        service = AIService(provider)
        answer = service.answer(
            business_knowledge="House Blend: $18",
            history=[{"role": "assistant", "content": "House Blend"}],
            current_message="How much?",
        )
        self.assertEqual(answer, "fake answer")
        self.assertEqual(provider.received_messages[-1]["content"], "How much?")

    @patch.dict(os.environ, {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "test-key"}, clear=False)
    def test_provider_registry_returns_gemini_adapter(self):
        provider = get_provider()
        self.assertIsInstance(provider, GeminiProvider)
        self.assertEqual(provider.name, "gemini")

    def test_unknown_provider_is_rejected_by_registry(self):
        with self.assertRaises(UnsupportedProviderError):
            get_provider("not-implemented")

    @patch("providers.gemini.httpx.Client")
    def test_gemini_adapter_owns_transport_auth_and_response_parsing(self, client_cls):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [{"message": {"content": "The House Blend costs $18."}}]
        }
        client = MagicMock()
        client.post.return_value = response
        client_cls.return_value.__enter__.return_value = client

        provider = GeminiProvider(api_key="test-key", model="gemini-test-model")
        answer = provider.generate([
            {"role": "system", "content": "Use business knowledge."},
            {"role": "user", "content": "How much?"},
        ])

        self.assertEqual(answer, "The House Blend costs $18.")
        client.post.assert_called_once()
        args, kwargs = client.post.call_args
        self.assertEqual(args[0], GEMINI_CHAT_URL)
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(kwargs["json"]["model"], "gemini-test-model")
        self.assertEqual(kwargs["json"]["messages"][-1]["content"], "How much?")

    @patch("providers.gemini.httpx.Client")
    def test_gemini_adapter_strips_api_key_whitespace(self, client_cls):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
        "choices": [{"message": {"content": "ok"}}]
        }

        client = MagicMock()
        client.post.return_value = response
        client_cls.return_value.__enter__.return_value = client

        provider = GeminiProvider(
        api_key=" test-key \r\n",
        model="gemini-test-model",
        )

        provider.generate([
        {"role": "user", "content": "hello"},
        ])

        _, kwargs = client.post.call_args

        self.assertEqual(
        kwargs["headers"]["Authorization"],
        "Bearer test-key",
        )


if __name__ == "__main__":
    unittest.main()
