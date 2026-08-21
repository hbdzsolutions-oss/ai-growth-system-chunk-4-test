# AI Growth System — Architecture Contract

Chunk 5 establishes the first platform backbone. The rules in this document are architectural constraints for future chunks, not temporary implementation notes.

## Non-negotiable domain separation

### 1. Agent Core — how an AI employee acts

Company-owned, reusable intelligence:

- role and methodology;
- behavior and conversation policy;
- guardrails;
- playbooks and future action rules;
- evaluation criteria.

Agent Core **must not contain client business facts**. A future Sales Agent, Shopping Assistant, Receptionist, Support Agent, etc. should be registered as another `AgentDefinition`, not implemented as a new chat stack.

Current implementation: `ags/agent_core/`.

### 2. Business Brain — what the business knows

Client-controlled knowledge:

- source definitions;
- ingestion loaders;
- normalized documents;
- chunks/structured metadata;
- embeddings;
- retrieval.

Business Brain **must not own conversation state or agent methodology**.

Current implementation: `ags/business_brain/` plus infrastructure adapters under `ags/infrastructure/`.

### 3. Business Context — what happened

Durable operational context:

- agent deployments;
- conversations;
- messages;
- future leads;
- future customers;
- future appointments;
- future outcomes and interaction history.

Business Context **must not define agent methodology or become the business knowledge store**.

Current implementation: `ags/business_context/`.

## Dependency direction

```text
Channel / HTTP adapter
        |
        v
Application use case
        |
        +--> Agent Core interface/model
        +--> Business Brain ports
        +--> Business Context ports
        +--> AIProvider port
                  |
                  v
          Infrastructure adapters
```

The application layer may depend on abstractions. Infrastructure may implement those abstractions. Infrastructure-specific details must not flow upward into application/domain code.

Examples:

- `ChatOrchestrator` depends on `AIProvider`, not Gemini.
- `ChatOrchestrator` depends on `KnowledgeRetriever`, not pgvector.
- `ChatOrchestrator` depends on `ConversationRepository`, not SQLAlchemy/PostgreSQL.
- the website widget talks to an HTTP channel adapter, not directly to an LLM or database.

## Current platform runtime

```text
External website
  |
  | deployment_key + conversation_id? + message
  v
/embed-api/chat
  |
  +-- exact origin allowlist
  +-- minimum rate limit
  v
ChatOrchestrator
  |
  +--> AgentRegistry --> Website Assistant Agent Core
  |
  +--> ConversationRepository --> SQLAlchemy persistence
  |       |
  |       +--> businesses
  |       +--> agent_deployments
  |       +--> conversations
  |       +--> messages
  |
  +--> KnowledgeRetriever
  |       |
  |       +--> PostgreSQL: pgvector cosine search
  |       +--> SQLite: portable in-process cosine fallback
  |       |
  |       +--> knowledge_sources
  |       +--> knowledge_documents
  |       +--> knowledge_chunks
  |
  +--> AIProvider --> GeminiProvider
```

## Agent deployments are foundational

A conversation belongs to an **agent deployment**, and an agent deployment belongs to a business.

This is intentionally modeled now even though Chunk 5 ships only one deployment. It prevents future channels or agents from forcing a conversation-schema rewrite.

Future examples can fit the existing model:

```text
Business
  +-- Website Receptionist
  +-- Website Sales Agent
  +-- WhatsApp Sales Agent
```

Chunk 5 does **not** implement those additional agents or channels.

## Business Brain ingestion model

```text
Source
  -> Loader
  -> Normalized document
  -> Chunking
  -> EmbeddingProvider
  -> Knowledge chunks
  -> KnowledgeRetriever
  -> Agent prompt context
```

Current source loaders:

- manual text;
- one public website URL.

Future PDF/DOCX/catalog/spreadsheet loaders should implement the same loader boundary instead of modifying the chat runtime.

## Retrieval infrastructure

Chunk 5 deliberately separates three concerns:

- `EmbeddingProvider` — turns text into vectors;
- `KnowledgeRepository` — persists sources/documents/chunks;
- `KnowledgeRetriever` — returns relevant `KnowledgeItem` objects to the application.

The default embedding adapter is a deterministic local hash vectorizer. It makes the ingestion/retrieval pipeline fully testable without a second external AI dependency. It is a **foundation adapter, not the final semantic embedding model**. A stronger local or external embedding model can replace it behind `EmbeddingProvider`.

For PostgreSQL, the SQL retrieval adapter uses the `vector` extension and cosine distance. SQLite keeps a portable fallback for local development and tests.

## Persistence and migrations

- SQLAlchemy is the persistence implementation.
- Alembic owns schema migration history.
- `DATABASE_URL` selects the database.
- PostgreSQL is the intended durable deployment database.
- SQLite is the default local/test database.

Application/domain code must never depend on Render, PostgreSQL SQL syntax, SQLAlchemy sessions, or a database URL.

## Website channel contract

The real embed endpoint no longer accepts model history or business knowledge from the browser.

Browser sends:

```json
{
  "deployment_key": "northstar-website-default",
  "conversation_id": "optional opaque id",
  "message": "visitor message"
}
```

Server owns:

- conversation history used for inference;
- business/deployment resolution;
- knowledge retrieval;
- Agent Core selection;
- persisted transcript.

The browser may cache visible messages for UX, but that cache is not authoritative model context.

## Public owner-surface rule

Until authentication exists, `PUBLIC_EMBED_ONLY=true` keeps `/owner`, `/owner-api/*`, `/api/chat`, and `/store` unavailable on the public deployment. The guarded `/embed-api/chat` path remains available.

Chunk 6 may introduce real authenticated customer accounts; Chunk 5 does not fake authentication.

## Rules future work must preserve

1. Agent Core never owns business facts.
2. Business Brain never owns conversation state.
3. Business Context never defines agent methodology.
4. HTTP routes/controllers stay thin.
5. LLM-provider details stay in provider adapters.
6. Database-specific code stays in persistence adapters.
7. Retrieval-engine details stay behind `KnowledgeRetriever`.
8. New channels become adapters to application use cases.
9. Existing validated behavior remains regression-tested.
10. Add abstractions for real architectural boundaries; do not implement speculative product scope simply because it may exist later.
