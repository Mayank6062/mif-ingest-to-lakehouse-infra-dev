# Phase 1 Implementation Plan: Backend Foundation

**Scope**: State Model V2, Draft Workspace, Snapshot Engine, Diff Engine, Session Persistence  
**Date**: 2026-06-12  
**Focus**: Backend only — NO UI changes, NO LangGraph changes, NO PR creation

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   LangGraph State (existing)                │
│              (GlueJobState + messages history)              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│           Session (V2) — NEW ROOT ENTITY                    │
│  • session_id (PK)                                          │
│  • user_email                                               │
│  • current_draft_id (FK → DraftWorkspace)                   │
│  • message_history[]                                        │
│  • status: {active, paused, closed, pr_created, archived}  │
│  • created_at, updated_at, last_activity_at                │
└─────────────────────────────────────────────────────────────┘
                            ↓
        ┌───────────────────────────────────────┐
        │      DraftWorkspace (V2) — NEW        │
        │  • draft_id (PK)                      │
        │  • session_id (FK)                    │
        │  • status: {open, validated, ready,   │
        │             merged, abandoned}        │
        │  • files[] (DraftFile entities)       │
        │  • snapshot_refs[] (SnapshotRef)      │
        │  • glue_jobs[] (job metadata)         │
        │  • validations[] (ValidationReport)   │
        │  • created_at, updated_at             │
        └───────────────────────────────────────┘
                    ↓         ↓          ↓
        ┌─────────────────────────────────┐
        │  DraftFile    Snapshot    Diff  │
        │  • file_id    • snapshot_id     │
        │  • path       • timestamp       │
        │  • content    • ref             │
        │  • mtime      • parent_ref      │
        │              • changes         │
        └─────────────────────────────────┘
```

---

## Files to Create

### 1. Models Layer (`backend/app/models/`)

| File | Purpose | Classes |
|------|---------|---------|
| `state_v2.py` | **NEW** State Model V2 | `Session`, `DraftWorkspace`, `DraftFile`, `ValidationReport`, `Snapshot` |
| `diff.py` | **NEW** Diff tracking | `FileDiff`, `DiffType`, `ChangeSet` |

### 2. Services Layer (`backend/app/services/`)

| File | Purpose | Classes |
|------|---------|---------|
| `draft_workspace_service.py` | **NEW** DraftWorkspace CRUD | `DraftWorkspaceService` |
| `snapshot_engine.py` | **NEW** Snapshot management | `SnapshotEngine`, `SnapshotManager` |
| `diff_engine.py` | **NEW** Diff tracking | `DiffEngine` |
| `session_persistence.py` | **NEW** Session hydration | `SessionPersistenceService` |

### 3. Repository Layer (`backend/app/repositories/`)

| File | Purpose | Classes |
|------|---------|---------|
| `draft_workspace_repository.py` | **NEW** Draft storage | `DraftWorkspaceRepository` |
| `snapshot_repository.py` | **NEW** Snapshot storage | `SnapshotRepository` |
| `session_repository.py` | **NEW** Session storage | `SessionRepository` |

### 4. Modified Files

| File | Changes |
|------|---------|
| `backend/app/models/session.py` | Add Session V2 fields (merge with existing SessionRegistry) |
| `backend/app/config.py` | Add storage backend config (db_url, storage_type) |
| `backend/app/main.py` | Initialize persistence layer on startup |
| `backend/requirements.txt` | Add: `sqlalchemy`, `alembic` if needed |

---

## Data Storage Strategy

**Database**: SQLite (dev) / PostgreSQL (prod)

### Tables

```sql
-- Sessions
CREATE TABLE sessions (
    session_id VARCHAR(64) PRIMARY KEY,
    user_email VARCHAR(255),
    current_draft_id VARCHAR(64),
    message_history JSONB,
    status VARCHAR(32),
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    last_activity_at TIMESTAMP
);

-- DraftWorkspaces
CREATE TABLE draft_workspaces (
    draft_id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) FOREIGN KEY REFERENCES sessions,
    status VARCHAR(32),
    files JSONB,
    glue_jobs JSONB,
    validation_reports JSONB,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Snapshots
CREATE TABLE snapshots (
    snapshot_id VARCHAR(64) PRIMARY KEY,
    draft_id VARCHAR(64) FOREIGN KEY REFERENCES draft_workspaces,
    timestamp TIMESTAMP,
    parent_snapshot_id VARCHAR(64),
    draft_state JSONB,
    created_at TIMESTAMP
);

-- Diffs
CREATE TABLE diffs (
    diff_id VARCHAR(64) PRIMARY KEY,
    from_snapshot_id VARCHAR(64) FOREIGN KEY REFERENCES snapshots,
    to_snapshot_id VARCHAR(64) FOREIGN KEY REFERENCES snapshots,
    changes JSONB,
    created_at TIMESTAMP
);
```

---

## Migration Strategy

### Phase 1A: Standalone (No DB yet)
- Create all model classes with in-memory storage
- Unit tests with mock data
- No database initialization required

### Phase 1B: Add SQLite Persistence (Optional)
- Implement SQLAlchemy models
- Add repository implementations
- Run Alembic migrations

### Phase 1C: Integrate with LangGraph (Future)
- Connect SessionPersistenceService to graph
- Load/restore state from DB on session resume
- Persist after each node execution

---

## Unit Tests

### Test Files

```
backend/tests/
├── models/
│   ├── test_state_v2.py
│   ├── test_draft_workspace.py
│   └── test_diff.py
├── services/
│   ├── test_draft_workspace_service.py
│   ├── test_snapshot_engine.py
│   ├── test_diff_engine.py
│   └── test_session_persistence.py
└── repositories/
    ├── test_draft_workspace_repository.py
    ├── test_snapshot_repository.py
    └── test_session_repository.py
```

### Test Coverage Goals
- ✅ Model creation and validation (100%)
- ✅ CRUD operations (create, read, update, delete)
- ✅ Snapshot creation and restore
- ✅ Diff tracking (additions, modifications, deletions)
- ✅ Session hydration (full state restore from DB)
- ✅ Conflict detection (two edits to same file)

---

## Implementation Order

**Week 1 (Day 1-2):**
1. ✅ Create state_v2.py with all TypedDicts
2. ✅ Create diff.py with DiffType enum and change tracking
3. ✅ Create draft_workspace_service.py (in-memory)
4. ✅ Create snapshot_engine.py with version management
5. ✅ Create diff_engine.py with change tracking
6. ✅ Create session_persistence.py (in-memory first)
7. ✅ Write unit tests (50+ test cases)

**Week 1 (Day 3):**
8. ⏭️ Add SQLAlchemy models
9. ⏭️ Add repository implementations
10. ⏭️ Wire into FastAPI app
11. ⏭️ Integration tests

---

## Success Criteria

- [ ] All 5 core services (Draft, Snapshot, Diff, Session, Persistence) working
- [ ] 50+ unit tests passing
- [ ] Full state V2 model validated
- [ ] Snapshot restore creates identical state
- [ ] Diff engine tracks all change types (add/mod/del)
- [ ] Session hydration works for complex workflows
- [ ] No breaking changes to existing LangGraph code
- [ ] Code 100% typed with mypy strict mode

---

## NOT Included (Out of Scope)

- ❌ UI implementation
- ❌ LangGraph routing changes
- ❌ PR creation
- ❌ Conflict resolution
- ❌ Topic validation
- ❌ Database migrations (Alembic setup)
- ❌ Kubernetes deployment
- ❌ Error recovery workflows

---

## File Dependencies

```
state_v2.py
    ├── No external deps (pure TypedDict)
    └── Used by all other services

diff.py
    ├── No external deps (pure enum + dataclass)
    └── Used by: diff_engine, snapshot_engine

draft_workspace_service.py
    ├── Depends on: state_v2, draft_workspace_repository
    └── Uses: snapshot_engine, diff_engine

snapshot_engine.py
    ├── Depends on: state_v2, diff.py, snapshot_repository
    └── Used by: draft_workspace_service

diff_engine.py
    ├── Depends on: diff.py, state_v2
    └── Used by: snapshot_engine, draft_workspace_service

session_persistence.py
    ├── Depends on: state_v2, draft_workspace_service, session_repository
    └── Used by: FastAPI app, LangGraph (future)

[Repository Layer]
draft_workspace_repository.py
snapshot_repository.py
session_repository.py
    └── Depend on: SQLAlchemy (added later)
```

---

## Next Steps

1. ✅ Create all model and service files
2. ✅ Implement core logic (no DB)
3. ✅ Write comprehensive unit tests
4. ✅ Verify all interactions work
5. ⏭️ Add SQLAlchemy integration (Phase 1B)
6. ⏭️ Wire to FastAPI endpoints (Phase 2)
7. ⏭️ Integrate with LangGraph (Phase 3)
