# Chunk 5 Validation Record

## Automated gates

The packaged build must pass all retained regression tests plus Chunk 5 foundation tests.

```text
python -m unittest discover -s tests -v
```

Expected at packaging time:

```text
40 tests
OK
```

Additional static gates:

```text
python -m compileall -q .
node --check static/embed.js
node --check static/app.js
node --check static/store.js
```

Migration-from-empty gate:

```text
DATABASE_URL=<empty sqlite test database> alembic upgrade head
```

The resulting schema must contain:

- businesses;
- agent_deployments;
- conversations;
- messages;
- knowledge_sources;
- knowledge_documents;
- knowledge_chunks;
- alembic_version.

## Local manual validation

### 1. Start backend

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:GEMINI_API_KEY="YOUR_KEY"
alembic upgrade head
uvicorn app:app --reload
```

Open `http://127.0.0.1:8000/owner`.

Expected:

- Overview shows one active Website Assistant.
- Business Knowledge contains the seeded Northstar source.
- Conversations is initially empty on a clean DB.

### 2. Start external website

```powershell
cd external-test-site
py -m http.server 9000
```

Open `http://127.0.0.1:9000`.

Ask:

```text
Which product is for dry skin?
```

Expected: answer is grounded in Northstar knowledge (Cloud Cream).

Then ask:

```text
How much is it?
```

Expected: the answer uses server-loaded conversation history. The browser does not send history in the request body.

### 3. Confirm persistence and multiple conversations

- Refresh the external page: visible history should return from browser cache.
- Continue the conversation: the same server conversation ID is used.
- Click `New chat`: a fresh conversation starts; the old transcript remains in the database.
- Send a message in the new chat.
- Open Owner -> Conversations.

Expected: both conversations are listed separately and each transcript can be opened.

### 4. Confirm Business Brain manual ingestion

Owner -> Business Knowledge -> Add Manual Source.

Add a unique fact, for example:

```text
VIP consultation costs $91.
```

Ask the external widget about the VIP consultation.

Expected: the new fact can be retrieved without editing Python source or restarting the app.

### 5. Confirm website ingestion

In Owner -> Business Knowledge, add a public website URL that contains a unique test fact.

Expected:

- source status becomes ready;
- source appears in the inventory with chunk count;
- asking about the unique fact can retrieve it.

Security check:

- `http://localhost/...` must be rejected;
- `http://127.0.0.1/...` must be rejected.

### 6. Confirm unsupported fact behavior

Ask a business fact absent from all active knowledge sources.

Expected exact response:

```text
I don't have that information yet.
```

### 7. Confirm guardrail behavior

Ask:

```text
Is this a scam?
```

Expected: natural acknowledgment and an invitation to identify the concern, without claiming the business is legitimate/safe/trustworthy unless supplied knowledge supports that claim.

### 8. Confirm origin boundary

Use an origin not present in `ALLOWED_EMBED_ORIGINS`.

Expected: embed API rejects the request.

### 9. Confirm public owner isolation

Set:

```text
PUBLIC_EMBED_ONLY=true
```

Expected:

- `/embed.js` available;
- `/embed-api/chat` available for allowed origins;
- `/owner` returns 404;
- `/owner-api/*` returns 404;
- `/api/chat` returns 404;
- `/store` returns 404.

## PostgreSQL / pgvector validation

For a durable deployment, point `DATABASE_URL` at a PostgreSQL database and run:

```text
alembic upgrade head
```

Expected:

- `vector` extension exists;
- `knowledge_chunks.embedding_vector` is `vector(256)`;
- HNSW cosine index exists;
- ingestion populates both portable embedding JSON and the pgvector column;
- retrieval uses pgvector cosine search through `SqlKnowledgeRetriever`.

## Chunk 5 freeze criteria

Freeze Chunk 5 only when:

1. all automated gates pass;
2. local external-site conversation flow passes;
3. multiple conversations appear in Owner dashboard;
4. manual knowledge ingestion affects answers;
5. website ingestion affects answers;
6. exact unknown-information behavior still passes;
7. origin and rate-limit controls still pass;
8. public owner surfaces remain disabled without authentication;
9. PostgreSQL migration is validated before treating hosted persistence as durable.
