from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, HttpUrl

from ai_service import AIService, MAX_HISTORY_MESSAGES
from ags.agent_core.default_agent import WEBSITE_ASSISTANT
from ags.agent_core.registry import AgentRegistry
from ags.application.chat_orchestrator import ChatOrchestrator
from ags.application.dashboard_service import DashboardService
from ags.business_brain.ingestion import KnowledgeIngestionService
from ags.business_brain.loaders import ManualTextLoader, WebsiteLoader
from ags.business_context.ports import ConversationNotFoundError, DeploymentNotFoundError
from ags.config import get_settings
from ags.infrastructure.embeddings.local_hash import LocalHashEmbeddingProvider
from ags.infrastructure.persistence.bootstrap import create_schema, seed_foundation
from ags.infrastructure.persistence.database import Database
from ags.infrastructure.persistence.vector_retriever import SqlKnowledgeRetriever
from ags.infrastructure.persistence.repositories import (
    SqlAlchemyConversationRepository,
    SqlAlchemyKnowledgeRepository,
)
from embed_security import (
    allowed_embed_origins,
    embed_rate_limiter,
    public_embed_only,
    request_client_key,
    require_allowed_origin,
)
from providers import get_provider
from providers.base import (
    ProviderAPIError,
    ProviderConfigurationError,
    ProviderResponseError,
)

ROOT = Path(__file__).resolve().parent
settings = get_settings()
database = Database(settings.database_url)
conversation_repository = SqlAlchemyConversationRepository(database)
knowledge_repository = SqlAlchemyKnowledgeRepository(database)
embedding_provider = LocalHashEmbeddingProvider()
knowledge_retriever = SqlKnowledgeRetriever(database, knowledge_repository, embedding_provider)
agent_registry = AgentRegistry([WEBSITE_ASSISTANT])
ingestion_service = KnowledgeIngestionService(
    repository=knowledge_repository,
    embedding_provider=embedding_provider,
    loaders=[ManualTextLoader(), WebsiteLoader()],
)
dashboard_service = DashboardService(
    conversation_repository=conversation_repository,
    knowledge_repository=knowledge_repository,
    business_id=settings.default_business_id,
    deployment_id=settings.default_deployment_id,
)

# Chunk 5 carries an Alembic migration for durable deployments. create_all keeps
# local/test setup zero-friction and is idempotent against the same schema.
create_schema(database)
seed_foundation(database, settings, ingestion_service, ROOT / "seed" / "northstar_knowledge.txt")

app = FastAPI(title="AI Growth System — Chunk 5")
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")

# Cross-origin access remains scoped to the embed sub-application. Owner APIs
# stay same-origin/local until authentication earns a public owner surface.
embed_app = FastAPI(
    title="AI Growth System — Embed API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
embed_app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_embed_origins(),
    allow_credentials=False,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=600,
)
app.mount("/embed-api", embed_app)


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2_000)


class ChatRequest(BaseModel):
    business_knowledge: str = Field(min_length=1, max_length=20_000)
    message: str = Field(min_length=1, max_length=2_000)
    history: list[ConversationMessage] = Field(default_factory=list, max_length=MAX_HISTORY_MESSAGES)


class EmbedChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2_000)
    conversation_id: str | None = Field(default=None, max_length=64)
    deployment_key: str = Field(default=settings.default_deployment_key, min_length=1, max_length=120)


class ManualKnowledgeRequest(BaseModel):
    title: str = Field(default="Manual knowledge", min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=100_000)


class WebsiteKnowledgeRequest(BaseModel):
    url: HttpUrl
    title: str | None = Field(default=None, max_length=300)


def current_provider():
    try:
        return get_provider()
    except ProviderConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def generate_answer(*, business_knowledge: str, history: list[ConversationMessage], message: str) -> str:
    """Legacy local test path kept to protect already validated behavior."""
    provider = current_provider()
    service = AIService(provider)
    bounded_history = [
        {"role": item.role, "content": item.content.strip()}
        for item in history[-MAX_HISTORY_MESSAGES:]
    ]
    try:
        return service.answer(
            business_knowledge=business_knowledge,
            history=bounded_history,
            current_message=message,
        )
    except ProviderConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ProviderAPIError, ProviderResponseError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def make_chat_orchestrator() -> ChatOrchestrator:
    return ChatOrchestrator(
        conversation_repository=conversation_repository,
        knowledge_retriever=knowledge_retriever,
        agent_registry=agent_registry,
        ai_provider=current_provider(),
        retrieval_limit=settings.retrieval_limit,
    )


def require_owner_surface() -> None:
    if public_embed_only():
        raise HTTPException(status_code=404, detail="Not available in public embed mode.")


@app.get("/")
def index():
    if public_embed_only():
        return JSONResponse(
            {"ok": True, "service": "AI Growth System embed backend", "chunk": "5"}
        )
    return RedirectResponse(url="/owner", status_code=307)


@app.get("/owner")
def owner() -> FileResponse:
    require_owner_surface()
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/store")
def store() -> FileResponse:
    require_owner_surface()
    return FileResponse(ROOT / "static" / "store.html")


@app.get("/embed.js")
def embed_script() -> FileResponse:
    response = FileResponse(ROOT / "static" / "embed.js", media_type="application/javascript")
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/health")
def health() -> dict[str, Any]:
    provider = current_provider()
    return {
        "ok": True,
        "chunk": "5",
        "provider": provider.name,
        "api_key_configured": provider.is_configured,
        "model": provider.model,
        "max_history_messages": MAX_HISTORY_MESSAGES,
        "embedding_provider": embedding_provider.name,
        "database_backend": database.engine.dialect.name,
        "default_deployment_key": settings.default_deployment_key,
        "allowed_embed_origins": allowed_embed_origins(),
        "public_embed_only": public_embed_only(),
    }


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict[str, str]:
    # This endpoint is retained only for the frozen local owner/store regression
    # flow. The real embed runtime below no longer accepts client-owned history or
    # client-supplied business knowledge.
    require_owner_surface()
    answer = generate_answer(
        business_knowledge=req.business_knowledge,
        history=req.history,
        message=req.message,
    )
    return {"answer": answer}


@embed_app.post("/chat")
def embed_chat(req: EmbedChatRequest, request: Request) -> dict[str, str]:
    origin = require_allowed_origin(request)
    embed_rate_limiter.check(request_client_key(request, origin))
    try:
        result = make_chat_orchestrator().respond(
            deployment_key=req.deployment_key,
            origin=origin,
            conversation_id=req.conversation_id,
            current_message=req.message,
        )
    except DeploymentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Agent deployment was not found.") from exc
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Conversation was not found for this deployment/origin.") from exc
    except ProviderConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ProviderAPIError, ProviderResponseError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"conversation_id": result.conversation_id, "answer": result.answer}


@app.get("/owner-api/overview")
def owner_overview() -> dict:
    require_owner_surface()
    return dashboard_service.overview()


@app.get("/owner-api/conversations")
def owner_conversations() -> dict:
    require_owner_surface()
    return {"items": conversation_repository.list_conversations(settings.default_deployment_id, 100)}


@app.get("/owner-api/conversations/{conversation_id}")
def owner_conversation(conversation_id: str) -> dict:
    require_owner_surface()
    try:
        return conversation_repository.get_conversation_with_messages(conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found.") from exc


@app.get("/owner-api/knowledge")
def owner_knowledge() -> dict:
    require_owner_surface()
    return {"items": knowledge_repository.list_sources(settings.default_business_id)}


@app.post("/owner-api/knowledge/manual")
def owner_add_manual_knowledge(req: ManualKnowledgeRequest) -> dict:
    require_owner_surface()
    try:
        return ingestion_service.ingest(
            business_id=settings.default_business_id,
            source_type="manual",
            title=req.title,
            value=req.content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/owner-api/knowledge/website")
def owner_add_website_knowledge(req: WebsiteKnowledgeRequest) -> dict:
    require_owner_surface()
    try:
        return ingestion_service.ingest(
            business_id=settings.default_business_id,
            source_type="website",
            title=req.title,
            value=str(req.url),
        )
    except (ValueError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/owner-api/knowledge/{source_id}")
def owner_delete_knowledge(source_id: str) -> dict[str, bool]:
    require_owner_surface()
    try:
        knowledge_repository.delete_source(settings.default_business_id, source_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Knowledge source not found.") from exc
    return {"deleted": True}
