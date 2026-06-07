# MIF Glue Job Agent

A production-ready AI platform for automating AWS Glue job creation in `mif-ingest-to-lakehouse-infra-dev`.

## Architecture

```
FastAPI (WebSocket) + LangGraph (state machine) + Next.js (chat UI)
```

### Workflow (12 steps)

```
1. Enter Kafka topic            → dev.saptcc.multi-1.raw
2. Auto-derive values           → source_system, schema_grain, job_key, secret
3. Check source system          → exists? pattern?
4. Confirm derived values       → user approves
5. Sink configuration form      → iceberg_database, warehouse, ARN (checkpoint is auto-derived)
6. Worker configuration form    → worker_type, count, ent_func, subgroup
7. Run all validations          → 40+ rules from knowledge_base
8. Show complete summary        → all fields in one table
9. Generate Terraform HCL       → exact block for locals.tf
10. Terraform preview           → syntax-highlighted code + file list
11. User approval               → REQUIRED before any PR creation
12. Create GitHub PR            → branch + commit + PR opened
```

## Quick Start

### Prerequisites

- Python 3.11+ ✅ (Python 3.13 detected on this machine)
- Node.js 18+ — install from https://nodejs.org/ (not yet installed — needed for frontend only)
- Azure OpenAI API key (EPAM proxy at `https://ai-proxy.lab.epam.com`)
- GitHub Personal Access Token (with `repo` scope)

> **Backend works without Node.js.** You can run and test the full workflow via  
> the API at http://localhost:8000/docs. The frontend (chat UI) requires Node.js.

### 1. Backend setup

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Copy and fill in your credentials
Copy-Item .env.example .env
notepad .env
```

Fill in `.env`:
```
AZURE_OPENAI_API_KEY=your_key_here
GITHUB_TOKEN=your_github_pat_here
GITHUB_REPO_OWNER=your_org_name
```

Start backend:
```powershell
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs

### 2. Frontend setup

```powershell
cd frontend
npm install
npm run dev
```

Open: http://localhost:3000

### 3. One-command start (both services)

```powershell
cd poc
.\start.ps1
```

## Project Structure

```
poc/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app + CORS + startup
│   │   ├── config.py            # Settings from .env
│   │   ├── api/
│   │   │   ├── websocket.py     # WebSocket /ws/{session_id}
│   │   │   ├── routes.py        # REST /api/sessions, /api/health
│   │   │   └── processor.py     # State machine message processor
│   │   ├── graph/
│   │   │   ├── state.py         # GlueJobState TypedDict + step constants
│   │   │   ├── builder.py       # LangGraph StateGraph construction
│   │   │   └── nodes/           # 12 node files (one per workflow step)
│   │   ├── agents/
│   │   │   ├── knowledge_agent.py   # Value derivation + source system check
│   │   │   ├── validation_agent.py  # 40+ rule validation
│   │   │   ├── terraform_agent.py   # HCL generation from template
│   │   │   └── pr_agent.py          # (used by create_pr node via github_service)
│   │   ├── services/
│   │   │   ├── llm_service.py       # Azure OpenAI client (EPAM proxy)
│   │   │   └── github_service.py    # PyGithub PR creation
│   │   ├── knowledge/
│   │   │   └── loader.py            # Loads all 6 knowledge_base files
│   │   └── models/
│   │       ├── chat.py              # Pydantic message models
│   │       └── session.py           # In-memory session store
│   ├── knowledge_base/          # Copied from ../knowledge_base/
│   └── requirements.txt
│
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── layout.tsx
│       │   ├── page.tsx         # Main chat page
│       │   └── globals.css
│       ├── components/
│       │   ├── chat/            # ChatContainer, ChatMessage, ChatInput, TypingIndicator
│       │   ├── widgets/         # ChipSelector, SinkConfigForm, WorkerConfigForm,
│       │   │                    # TerraformPreview, ApprovalCard, PRSuccessCard,
│       │   │                    # ValidationBadge, SummaryTable, TextInputWidget, StepBadge
│       │   └── layout/          # AppHeader
│       ├── hooks/
│       │   ├── useWebSocket.ts  # WebSocket with auto-reconnect
│       │   └── useChat.ts       # Chat state manager
│       ├── types/index.ts       # TypeScript types (mirrors Python Pydantic models)
│       └── lib/
│           ├── utils.ts
│           └── constants.ts
│
├── knowledge_base/              # SOURCE OF TRUTH (read-only)
│   ├── validation_rules.json    # 40+ business rules
│   ├── terraform_template.json  # Exact HCL template + derivation logic
│   ├── source_systems.json      # 20+ known source systems
│   ├── agent_system_prompt.md
│   ├── decision_trees.md
│   └── README.md
│
└── project_information/         # Original extracted repo intelligence (read-only)
```

## WebSocket Protocol

**Incoming (frontend → backend):**
```json
{ "type": "user_message", "content": "dev.saptcc.multi-1.raw" }
{ "type": "user_message", "content": "Sink config submitted", "widget_value": { "iceberg_database": "...", ... } }
{ "type": "approval", "content": "yes" }
```

**Outgoing (backend → frontend):**
```json
{ "type": "typing" }
{ "type": "stop_typing" }
{ "type": "assistant_message", "content": "...", "step": {...}, "widget": {...} }
{ "type": "terraform_preview", "terraform_hcl": "...", "files_to_modify": [...] }
{ "type": "approval_request", "widget": { "type": "approval" } }
{ "type": "pr_created", "pr_url": "...", "branch_name": "..." }
{ "type": "error", "content": "..." }
```

## Key Design Decisions

1. **No auto-merge** — PR creation requires explicit user `approved=true`. The guard is in `create_pr_node` and `_handle_approval`.
2. **Deterministic validation** — All 40+ rules are pure Python. No LLM for validation.
3. **Knowledge base as truth** — All rules, templates, defaults loaded from `knowledge_base/*.json` at startup.
4. **Session persistence** — In-memory store (replace with Redis for production).
5. **Auto-reconnect** — Frontend WebSocket retries with exponential backoff (max 5 attempts).
6. **EPAM proxy** — Uses `AzureOpenAI` client with `base_url=https://ai-proxy.lab.epam.com`, model `gpt-4.1-mini`.

## Resetting a session

Type `restart` in the chat at any time to start over.

Or call `DELETE /api/sessions/{session_id}`.
