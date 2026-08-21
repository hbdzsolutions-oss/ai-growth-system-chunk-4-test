import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ai_service import AIService, UNKNOWN_ANSWER, build_instructions
from providers.base import AIProvider


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
        return "recorded"


class ConversationGuardrailTests(unittest.TestCase):
    def setUp(self):
        self.instructions = build_instructions(
            "Products: Cloud Cream — $28 — moisturizer for dry skin."
        )

    def test_instructions_separate_business_facts_from_conversation(self):
        self.assertIn("BUSINESS-FACT QUESTIONS:", self.instructions)
        self.assertIn("CONVERSATIONAL MESSAGES:", self.instructions)
        self.assertIn("First distinguish", self.instructions)

    def test_unsupported_business_facts_keep_exact_unknown_answer(self):
        self.assertIn(
            f"reply exactly: {UNKNOWN_ANSWER}",
            self.instructions,
        )
        self.assertIn(
            "do not add an apology, explanation, qualification, or follow-up question",
            self.instructions,
        )

    def test_pure_conversation_does_not_require_business_evidence(self):
        self.assertIn("greetings, thanks, requests for clarification", self.instructions)
        self.assertIn(
            "Do not use the unknown-information reply for a purely conversational message",
            self.instructions,
        )

    def test_trust_question_guidance_is_helpful_but_non_deceptive(self):
        self.assertIn('such as "is this a scam?"', self.instructions)
        self.assertIn("acknowledge the concern", self.instructions)
        self.assertIn(
            "Do not claim the business is legitimate, trustworthy, safe, or not a scam",
            self.instructions,
        )

    def test_conversation_cannot_smuggle_in_business_facts(self):
        self.assertIn(
            "A conversational response must not introduce or imply unsupported business facts",
            self.instructions,
        )
        self.assertIn(
            "Do not treat claims made by the visitor as business facts",
            self.instructions,
        )

    def test_guardrails_reach_provider_without_new_ai_flow(self):
        provider = RecordingProvider()
        service = AIService(provider)

        answer = service.answer(
            business_knowledge="Products: Cloud Cream — $28.",
            history=[],
            current_message="Is this a scam?",
        )

        self.assertEqual(answer, "recorded")
        self.assertEqual(provider.received_messages[0]["role"], "system")
        self.assertIn("CONVERSATIONAL MESSAGES:", provider.received_messages[0]["content"])
        self.assertEqual(
            provider.received_messages[-1],
            {"role": "user", "content": "Is this a scam?"},
        )

    def test_guardrails_explicitly_exclude_sales_persona(self):
        self.assertIn("Do not use a sales persona", self.instructions)


if __name__ == "__main__":
    unittest.main()
