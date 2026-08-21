import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import app as app_module
from ags.agent_core.default_agent import WEBSITE_ASSISTANT
from ags.agent_core.registry import AgentRegistry
from ags.application.chat_orchestrator import ChatOrchestrator
from ags.business_brain.ingestion import KnowledgeIngestionService
from ags.business_brain.loaders import ManualTextLoader, WebsiteLoader
from ags.business_context.ports import ConversationNotFoundError
from ags.config import Settings
from ags.infrastructure.embeddings.local_hash import LocalHashEmbeddingProvider
from ags.infrastructure.persistence.bootstrap import create_schema, seed_foundation
from ags.infrastructure.persistence.database import Database, normalize_database_url
from ags.infrastructure.persistence.repositories import (
    SqlAlchemyConversationRepository,
    SqlAlchemyKnowledgeRepository,
)
from ags.infrastructure.persistence.vector_retriever import SqlKnowledgeRetriever
from embed_security import embed_rate_limiter
from providers.base import AIProvider

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ORIGIN = "http://127.0.0.1:9000"


class SequencedProvider(AIProvider):
    def __init__(self):
        self.calls = []

    @property
    def name(self):
        return "sequenced"

    @property
    def model(self):
        return "sequenced-model"

    @property
    def is_configured(self):
        return True

    def generate(self, messages):
        self.calls.append(messages)
        return f"answer-{len(self.calls)}"


class FoundationHarness:
    def __init__(self, root: Path):
        self.tempdir = tempfile.TemporaryDirectory()
        db_path = Path(self.tempdir.name) / "foundation.db"
        self.settings = Settings(
            database_url=f"sqlite:///{db_path}",
            default_business_id="test-business",
            default_deployment_id="test-deployment",
            default_deployment_key="test-public-key",
            retrieval_limit=5,
        )
        self.database = Database(self.settings.database_url)
        create_schema(self.database)
        self.conversations = SqlAlchemyConversationRepository(self.database)
        self.knowledge = SqlAlchemyKnowledgeRepository(self.database)
        self.embedding = LocalHashEmbeddingProvider()
        self.ingestion = KnowledgeIngestionService(
            repository=self.knowledge,
            embedding_provider=self.embedding,
            loaders=[ManualTextLoader()],
        )
        seed_foundation(
            self.database,
            self.settings,
            self.ingestion,
            root / "seed" / "northstar_knowledge.txt",
        )
        self.retriever = SqlKnowledgeRetriever(self.database, self.knowledge, self.embedding)
        self.provider = SequencedProvider()
        self.orchestrator = ChatOrchestrator(
            conversation_repository=self.conversations,
            knowledge_retriever=self.retriever,
            agent_registry=AgentRegistry([WEBSITE_ASSISTANT]),
            ai_provider=self.provider,
            retrieval_limit=5,
        )

    def close(self):
        self.database.engine.dispose()
        self.tempdir.cleanup()

    


class ChunkFiveFoundationTests(unittest.TestCase):
    def test_database_url_normalization_uses_psycopg3(self):
        self.assertEqual(
            normalize_database_url("postgres://user:pass@host/db"),
            "postgresql+psycopg://user:pass@host/db",
        )

        self.assertEqual(
            normalize_database_url("postgresql://user:pass@host/db"),
            "postgresql+psycopg://user:pass@host/db",
        )

        self.assertEqual(
            normalize_database_url("sqlite:///./data/test.db"),
            "sqlite:///./data/test.db",
        )

    def test_server_owned_conversation_persists_and_rebuilds_history(self):
        harness = FoundationHarness(ROOT)
        try:
            first = harness.orchestrator.respond(
                deployment_key="test-public-key",
                origin=ALLOWED_ORIGIN,
                current_message="Which product is for dry skin?",
            )
            second = harness.orchestrator.respond(
                deployment_key="test-public-key",
                origin=ALLOWED_ORIGIN,
                conversation_id=first.conversation_id,
                current_message="How much is it?",
            )

            self.assertEqual(second.conversation_id, first.conversation_id)
            self.assertEqual(len(harness.provider.calls), 2)
            second_call = harness.provider.calls[-1]
            self.assertEqual(second_call[-1]["content"], "How much is it?")
            self.assertIn(
                {"role": "user", "content": "Which product is for dry skin?"},
                second_call,
            )
            self.assertIn(
                {"role": "assistant", "content": "answer-1"},
                second_call,
            )
            transcript = harness.conversations.get_conversation_with_messages(first.conversation_id)
            self.assertEqual([m["role"] for m in transcript["messages"]], ["user", "assistant", "user", "assistant"])
        finally:
            harness.close()

    def test_conversation_id_cannot_be_reused_from_a_different_origin(self):
        harness = FoundationHarness(ROOT)
        try:
            first = harness.orchestrator.respond(
                deployment_key="test-public-key",
                origin=ALLOWED_ORIGIN,
                current_message="Hello",
            )
            with self.assertRaises(ConversationNotFoundError):
                harness.orchestrator.respond(
                    deployment_key="test-public-key",
                    origin="https://different.example",
                    conversation_id=first.conversation_id,
                    current_message="Continue",
                )
        finally:
            harness.close()

    def test_manual_business_brain_ingestion_is_retrievable_through_port(self):
        harness = FoundationHarness(ROOT)
        try:
            source = harness.ingestion.ingest(
                business_id="test-business",
                source_type="manual",
                title="Launch notes",
                value="ZXQFALCON membership costs $73 and renews every twelve months.",
            )
            results = harness.retriever.retrieve("test-business", "What does ZXQFALCON cost?", limit=1)
            self.assertEqual(source["status"], "ready")
            self.assertGreaterEqual(source["chunk_count"], 1)
            self.assertEqual(len(results), 1)
            self.assertIn("$73", results[0].content)
            self.assertEqual(results[0].source_title, "Launch notes")
        finally:
            harness.close()

    def test_embed_runtime_uses_business_brain_not_demo_business_module(self):
        app_source = (ROOT / "app.py").read_text(encoding="utf-8")
        orchestrator_source = (ROOT / "ags" / "application" / "chat_orchestrator.py").read_text(encoding="utf-8")
        agent_source = (ROOT / "ags" / "agent_core" / "default_agent.py").read_text(encoding="utf-8")
        embed_source = (ROOT / "static" / "embed.js").read_text(encoding="utf-8")

        self.assertNotIn("demo_business", app_source)
        self.assertNotIn("DEMO_BUSINESS_KNOWLEDGE", app_source)
        self.assertIn("knowledge_retriever", orchestrator_source)
        self.assertNotIn("Cloud Cream", agent_source)
        self.assertNotIn("Cloud Cream", embed_source)
        self.assertTrue((ROOT / "seed" / "northstar_knowledge.txt").exists())

    def test_application_layer_has_no_gemini_postgres_or_render_transport_details(self):
        orchestrator_source = (ROOT / "ags" / "application" / "chat_orchestrator.py").read_text(encoding="utf-8")
        forbidden = [
            "generativelanguage.googleapis.com",
            "GEMINI_API_KEY",
            "psycopg",
            "pgvector",
            "onrender.com",
            "sqlalchemy",
        ]
        for term in forbidden:
            self.assertNotIn(term, orchestrator_source.lower())
        self.assertIn("AIProvider", orchestrator_source)
        self.assertIn("KnowledgeRetriever", orchestrator_source)
        self.assertIn("ConversationRepository", orchestrator_source)
        self.assertIn("AgentRegistry", orchestrator_source)

    def test_owner_dashboard_can_read_a_real_embed_transcript(self):
        provider = SequencedProvider()
        with patch.object(app_module, "current_provider", return_value=provider):
            embed_rate_limiter.reset()
            client = TestClient(app_module.app)
            first = client.post(
                "/embed-api/chat",
                headers={"Origin": ALLOWED_ORIGIN},
                json={"message": "Dashboard transcript test"},
            )
            self.assertEqual(first.status_code, 200)
            conversation_id = first.json()["conversation_id"]
            second = client.post(
                "/embed-api/chat",
                headers={"Origin": ALLOWED_ORIGIN},
                json={"conversation_id": conversation_id, "message": "Second turn"},
            )
            self.assertEqual(second.status_code, 200)

            detail = client.get(f"/owner-api/conversations/{conversation_id}")
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(len(detail.json()["messages"]), 4)
            self.assertEqual(detail.json()["messages"][0]["content"], "Dashboard transcript test")

    def test_public_embed_mode_keeps_owner_dashboard_and_owner_api_private(self):
        provider = SequencedProvider()
        with patch.object(app_module, "current_provider", return_value=provider), patch.dict(
            os.environ, {"PUBLIC_EMBED_ONLY": "true"}
        ):
            client = TestClient(app_module.app)
            self.assertEqual(client.get("/owner").status_code, 404)
            self.assertEqual(client.get("/owner-api/overview").status_code, 404)
            self.assertEqual(client.get("/owner-api/conversations").status_code, 404)
            self.assertEqual(client.get("/owner-api/knowledge").status_code, 404)

    def test_website_loader_rejects_private_targets_before_fetch(self):
        loader = WebsiteLoader(client_factory=lambda: self.fail("client should not be created"))
        with self.assertRaises(ValueError):
            loader.load("http://localhost:9000/private")
        with self.assertRaises(ValueError):
            loader.load("http://127.0.0.1/private")


    def test_website_loader_extracts_public_html_without_script_noise(self):
        class FakeClient:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def get(self, url, headers=None):
                return httpx.Response(
                    200,
                    headers={"content-type": "text/html; charset=utf-8"},
                    text="<html><head><title>Northstar FAQ</title><script>secret()</script></head><body><h1>Shipping</h1><p>Orders arrive in 2–4 business days.</p></body></html>",
                    request=httpx.Request("GET", url),
                )

        loader = WebsiteLoader(client_factory=lambda: FakeClient())
        with patch(
            "ags.business_brain.loaders.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("93.184.216.34", 443))],
        ):
            document = loader.load("https://example.com/faq")

        self.assertEqual(document.title, "Northstar FAQ")
        self.assertIn("Orders arrive in 2–4 business days.", document.text)
        self.assertNotIn("secret()", document.text)

    def test_owner_manual_knowledge_api_ingests_and_lists_source(self):
        provider = SequencedProvider()
        with patch.object(app_module, "current_provider", return_value=provider):
            client = TestClient(app_module.app)
            created = client.post(
                "/owner-api/knowledge/manual",
                json={
                    "title": "API knowledge test",
                    "content": "ORBITALNOTE support is available on Tuesdays.",
                },
            )
            self.assertEqual(created.status_code, 200)
            source_id = created.json()["id"]
            try:
                listing = client.get("/owner-api/knowledge")
                self.assertEqual(listing.status_code, 200)
                self.assertIn(source_id, [item["id"] for item in listing.json()["items"]])
            finally:
                client.delete(f"/owner-api/knowledge/{source_id}")

    def test_postgres_pgvector_is_an_infrastructure_adapter_not_app_dependency(self):
        bootstrap = (ROOT / "ags" / "infrastructure" / "persistence" / "bootstrap.py").read_text(encoding="utf-8")
        vector_adapter = (ROOT / "ags" / "infrastructure" / "persistence" / "vector_retriever.py").read_text(encoding="utf-8")
        migration = (ROOT / "alembic" / "versions" / "20260821_0001_chunk5_foundation.py").read_text(encoding="utf-8")
        self.assertIn("CREATE EXTENSION IF NOT EXISTS vector", bootstrap)
        self.assertIn("embedding_vector <=>", vector_adapter)
        self.assertIn("CREATE EXTENSION IF NOT EXISTS vector", migration)
        self.assertIn("hnsw", migration.lower())


if __name__ == "__main__":
    unittest.main()
