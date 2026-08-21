# AI Growth System — Chunk 5: Platform Foundation

Chunk 5 converts the validated website chatbot slices into the first durable platform backbone while intentionally keeping product scope narrow.

## What Chunk 5 proves

- **Agent Core** is separated from client knowledge and conversation state.
- **Business Brain** can ingest manual knowledge and a public website, normalize/chunk/embed/store it, and retrieve relevant context.
- **Business Context** stores multiple server-owned visitor conversations and messages.
- A conversation belongs to an **agent deployment**, which belongs to a business.
- The external widget sends only a deployment key, optional conversation ID, and the new message. It no longer sends model history or business knowledge.
- The owner dashboard can view real visitor conversations and manage knowledge sources.
- PostgreSQL + pgvector is supported behind a replaceable retrieval adapter; SQLite remains the local/test fallback.
- Gemini remains isolated behind the existing `AIProvider` interface.
- Existing origin allowlisting, rate limiting, public-embed-only behavior, bounded history, and Chunk 4.1 guardrails remain covered by regression tests.

Read `ARCHITECTURE.md` before adding future features.

## Deliberately not implemented

Chunk 5 does **not** add:

- authentication/customer accounts;
- true multi-tenancy;
- multiple production AI employees;
- lead/CRM objects;
- conversion outcomes or scoring;
- analytics;
- usage/cost metering;
- a second LLM provider;
- additional channels;
- billing;
- production-grade distributed abuse controls.

The foundation is designed so these can be added later without collapsing the three core layers.

## Project structure

```text
ags/
  agent_core/          company-owned agent intelligence
  business_brain/      knowledge ingestion/retrieval domain
  business_context/    conversations/deployments domain
  application/         orchestration/use cases
  infrastructure/      database, embeddings, vector retrieval adapters

providers/             AIProvider + Gemini adapter
alembic/               schema migrations
seed/                   initial Northstar source used through ingestion
static/                 owner dashboard, local store, external widget
external-test-site/     separate website used for cross-origin validation
tests/                  retained regression suite + Chunk 5 foundation tests
```

## Local setup

PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:GEMINI_API_KEY="YOUR_KEY"
$env:AI_PROVIDER="gemini"
alembic upgrade head
uvicorn app:app --reload
```

Without `DATABASE_URL`, local development uses:

```text
sqlite:///./data/ags.db
```

Open the local owner dashboard:

```text
http://127.0.0.1:8000/owner
```

## External website test

In a second terminal:

```powershell
cd external-test-site
py -m http.server 9000
```

Open:

```text
http://127.0.0.1:9000
```

The installation snippet identifies the deployment but contains no business knowledge or provider credentials:

```html
<script
  data-ags-embed
  data-ags-deployment="northstar-website-default"
  src="http://127.0.0.1:8000/embed.js"
  defer></script>
```

The default local origin allowlist permits `http://127.0.0.1:9000` and `http://localhost:9000`.

## Server-owned conversation contract

First turn:

```json
{
  "deployment_key": "northstar-website-default",
  "message": "Which product is for dry skin?"
}
```

Response:

```json
{
  "conversation_id": "opaque-server-id",
  "answer": "..."
}
```

Later turn:

```json
{
  "deployment_key": "northstar-website-default",
  "conversation_id": "opaque-server-id",
  "message": "How much is it?"
}
```

The server loads the bounded recent transcript. Client-supplied inference history is no longer part of the real embed contract.

## Business Knowledge

The local owner dashboard supports:

1. manual text sources;
2. one public HTTP/HTTPS website URL per ingestion action.

Website ingestion rejects localhost/private-network targets and revalidates redirect destinations.

Knowledge is stored as:

```text
knowledge source
  -> normalized document
  -> chunks
  -> embeddings
  -> retrieval
```

Northstar's initial knowledge lives in `seed/northstar_knowledge.txt` and is seeded **through the same ingestion service** as customer knowledge. The embed runtime does not import a demo-knowledge constant.

## Embeddings and retrieval

The first embedding adapter is `LocalHashEmbeddingProvider`. It is deterministic, offline, and useful for proving the complete architecture and tests. It is intentionally replaceable and is not claimed to be the final semantic embedding model.

- SQLite: vectors are stored portably and ranked in-process.
- PostgreSQL: the infrastructure adapter creates/uses pgvector and performs cosine search with an HNSW index.

Agent/application code sees only `EmbeddingProvider` and `KnowledgeRetriever` contracts.

## Durable deployment database

Set `DATABASE_URL` to a PostgreSQL connection string from the provider you choose. The application is not tied to Render's database service.

The Render Blueprint leaves `DATABASE_URL` as a secret setting and starts with:

```text
alembic upgrade head && uvicorn app:app --host 0.0.0.0 --port $PORT
```

`PUBLIC_EMBED_ONLY=true` remains enabled in the public blueprint, so the owner dashboard stays private until real authentication is implemented.

## Automated validation

Run:

```powershell
python -m unittest discover -s tests -v
python -m compileall -q .
node --check static/embed.js
node --check static/app.js
node --check static/store.js
```

See `CHUNK5_VALIDATION.md` for the complete manual validation sequence.
