# STEP 2.3 — ONE PR = ONE COMMIT
## Final Implementation Design with Architecture Rules
**Date:** 2026-06-12  
**Status:** Ready for Implementation

---

## Architecture Rules (FINAL)

### 1. BRANCH MANAGEMENT RULE
- **Default branch name:** `draft/<draft_id>` (e.g., `draft/dft_8a91bc`)
- **User-editable:** Branch name can be modified during Review Draft Workspace phase
- **Fallback:** If user does not modify, use auto-generated default
- **Draft metadata fields:**
  - `branch_name`
  - `draft_base_sha`
  - `repo_head_sha`
  - `conflict_files`

### 2. DRAFT AUTHORITATIVE RULE
- **Single source of truth:** Draft Workspace only
- **Function signature change:** `collect_final_files(draft_id)` instead of `collect_final_files(session_id)`
- **PR creation constraint:** Must NEVER use:
  - Session state
  - LangGraph state
  - Cached file_edits in processor
  - Temporary processor memory
- **All data must come from:** Draft Workspace only

### 3. DRAFT STATUS LIFECYCLE
```
OPEN (editable)
  ↓ (user clicks Review)
REVIEW (can return to OPEN)
  ↓ (user clicks Create PR)
PR_CREATING (frozen, no edits)
  ↓ (success)
PR_CREATED (immutable, read-only)
  
Alternative:
ABANDONED (read-only)
```

**Rules:**
- Only `OPEN` can be edited
- `REVIEW` can return to `OPEN` with "Edit Draft" button
- `PR_CREATING` is locked—all edits blocked
- `PR_CREATED` is immutable
- `ABANDONED` is read-only

### 4. DRAFT FREEZE RULE
**When user clicks "Create Pull Request":**
1. **Immediately:** Set `status = PR_CREATING`
2. **Freeze Draft:** Prevent all mutations
3. **Block operations:**
   - File edits (add/remove/modify)
   - Glue job creation
   - "Add Another Glue Job" visibility set to False
   - Discard last change

**On outcome:**
- If PR creation succeeds: `status = PR_CREATED`
- If PR creation fails: `status = REVIEW` (allow user to retry or edit)

### 5. DUPLICATE PR PROTECTION
**Rule:** If `status == PR_CREATING`, reject any additional PR creation requests.

**Response:**
```json
{
  "error": "Pull Request creation already in progress.",
  "draft_id": "dft_xxxxx",
  "status": "PR_CREATING"
}
```

### 6. ONE PR = ONE COMMIT (Mandatory)
**Invariant:** Exactly one commit per PR regardless of:
- Number of files
- Number of glue jobs
- Number of source systems
- Number of edits
- Number of draft revisions

**Never:**
- Create per-file commits
- Create per-job commits
- Create intermediate commits

### 7. REVIEW SCREEN RULE
**Before PR creation, user must see:**

**Editable fields:**
- Branch Name (text input, default: `draft/<draft_id>`)
- Commit Message (textarea)
- PR Title (text input)
- PR Description (textarea)

**Generated (read-only):**
- Files Changed (count and list)
- Glue Jobs Added (count and list)
- Validation Summary (pass/fail/warnings)

**Diff Viewer:**
- Green highlighting for added lines/files
- Red highlighting for removed lines/files
- GitHub-style side-by-side or unified diff
- Show file paths, line numbers, context

### 8. CONFLICT PREPARATION RULE (for future)
**Store:**
- `draft_base_sha` (SHA of HEAD when draft created)
- `repo_head_sha` (current HEAD SHA when divergence detected)
- `conflict_files` (list of files with conflicts, empty if no divergence)

**Do NOT implement conflict resolution yet.**

**Future workflow must support:**
- Incoming Changes (base → current repo HEAD)
- Current Changes (base → draft)
- Both Changes (three-way diff)

---

## Current Flow Analysis

### Current Commit/PR Creation Callsites
**Files to inventory:**
- [backend/app/services/github_service.py](backend/app/services/github_service.py)
- [backend/app/services/draft_workspace_service.py](backend/app/services/draft_workspace_service.py)
- [backend/app/api/processor.py](backend/app/api/processor.py)
- [backend/app/api/routes.py](backend/app/api/routes.py)
- [backend/app/graph/nodes/create_pr.py](backend/app/graph/nodes/create_pr.py) (if exists)
- [backend/app/graph/nodes/generate_terraform.py](backend/app/graph/nodes/generate_terraform.py)
- [backend/app/agents/terraform_agent.py](backend/app/agents/terraform_agent.py)

**Likely patterns to find:**
- `create_file(path, content, ...)`
- `update_file(path, content, ...)`
- `create_commit(...)`
- `update_ref(branch, sha, ...)`
- `create_pull(...)`

---

## Target Flow

### Sequence: One Draft → One Commit → One PR

1. **User builds/edits draft in `DraftWorkspaceService`**
   - Status: `OPEN`
   - All edits applied via `add_file`, `add_glue_job`, etc.
   - Snapshots created automatically (backend-only)

2. **User opens Review Draft Workspace**
   - Status: `OPEN` → `REVIEW`
   - Fetch draft from `DraftWorkspaceService` using `draft_id`
   - Call `preview_commit(draft_id)` to compute diffs
   - Display:
     - Editable metadata (branch name, commit message, PR title/description)
     - Generated summary (files, glue jobs, validation)
     - Diff viewer (GitHub-style)

3. **User optionally edits metadata**
   - Branch Name (default: `draft/<draft_id>`)
   - Commit Message (default: generated)
   - PR Title (default: generated)
   - PR Description (default: generated)
   - Call `update_draft_meta(draft_id, { branch_name, commit_message, pr_title, pr_body })` to persist

4. **User clicks "Create Pull Request"**
   - **Immediately:** Set `status = PR_CREATING`, freeze draft
   - Block all edits
   - Call `/api/sessions/{session_id}/draft/create_pr` with branch_name, commit_message, pr_title, pr_body

5. **Backend: PR Creation Handler**
   - Validate `status == REVIEW` (or OPEN if skip preview)
   - Set `status = PR_CREATING` (double-check, atomic)
   - Fetch draft via `DraftWorkspaceService.get_draft(draft_id)`
   - Call `collect_final_files(draft_id)` → `List[{ path, content, mode }]`
   - Fetch current `repo_head_sha` via GitHub API
   - Call `GitHubService.create_single_commit_and_pr(...)` with:
     - `repo_name`, `target_branch`, `base_sha`, `tree_entries`
     - `branch_name`, `commit_message`, `pr_title`, `pr_body`
   - On success:
     - Set `status = PR_CREATED`
     - Store PR metadata in draft (`pr_url`, `pr_number`, `commit_sha`)
     - Return PR URL to UI
   - On failure:
     - Set `status = REVIEW`
     - Return error details
     - Allow user to retry or edit draft and try again

6. **GitHub API sequence (inside `create_single_commit_and_pr`)**
   - For each file in `tree_entries`:
     - Create blob with content
   - Create tree with all blobs
   - Create commit with parent = `base_sha`
   - Update/create branch ref → new commit SHA
   - Create PR referencing branch
   - **Return:** `{ commit_sha, pr_url, pr_number }`

7. **Draft remains editable in `OPEN` state**
   - User can create multiple drafts per session
   - Each draft is independent
   - Only when PR created does draft become read-only

---

## Data Model Changes

### Draft Workspace State Extension
```python
class Draft:
    draft_id: str                      # Auto-generated: dft_<random>
    session_id: str                    # Foreign key to session
    status: DraftStatus                # OPEN, REVIEW, PR_CREATING, PR_CREATED, ABANDONED
    
    # Metadata
    branch_name: str                   # Default: draft/<draft_id>, user-editable
    draft_base_sha: str                # SHA when draft created
    repo_head_sha: Optional[str]       # Current HEAD SHA (set at review time)
    conflict_files: List[str]          # Files with conflicts (if diverged)
    
    # Review Screen Fields
    user_commit_message: str           # User-provided commit message
    user_pr_title: str                 # User-provided PR title
    user_pr_description: str           # User-provided PR description
    
    # File Edits (authoritative source)
    files: Dict[str, FileEdit]        # { path: FileEdit }
    
    # Snapshots (backend-only)
    snapshots: List[Snapshot]         # Change history for undo
    
    # PR Metadata (populated after creation)
    pr_url: Optional[str]             # GitHub PR URL
    pr_number: Optional[int]          # GitHub PR number
    commit_sha: Optional[str]         # Commit SHA of single commit
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
```

### GlueJobState Extensions
```python
class GlueJobState:
    # ... existing fields ...
    
    # Draft Workspace Integration
    draft_id: str                      # Current draft ID for this session
    draft_status: DraftStatus          # OPEN, REVIEW, PR_CREATING, PR_CREATED
    draft_frozen: bool                 # True if PR creation in progress
    draft_base_sha: str                # Stored for divergence detection
    
    # UI Visibility Rules (derived from status)
    can_edit_draft: bool               # True if status == OPEN
    can_add_glue_job: bool             # True if status == OPEN
    can_discard_change: bool           # True if status == OPEN
    can_create_pr: bool                # True if status == REVIEW
    show_pr_creating_spinner: bool     # True if status == PR_CREATING
```

---

## API Endpoints

### New/Modified Endpoints

#### GET `/api/sessions/{session_id}/draft`
**Purpose:** Fetch draft summary for UI

**Response:**
```json
{
  "draft_id": "dft_8a91bc",
  "status": "REVIEW",
  "branch_name": "draft/dft_8a91bc",
  "files_changed": 5,
  "glue_jobs_added": 2,
  "file_edits": [
    { "path": "terraform/glue_jobs.tf", "operation": "add", "size": 1024 }
  ],
  "user_commit_message": "",
  "user_pr_title": "",
  "user_pr_description": "",
  "can_edit_draft": false,
  "can_create_pr": true,
  "created_at": "2026-06-12T10:30:00Z"
}
```

#### POST `/api/sessions/{session_id}/draft/preview_commit`
**Purpose:** Generate diff/patch without creating commit

**Request:**
```json
{
  "draft_id": "dft_8a91bc"
}
```

**Response:**
```json
{
  "base_sha": "abc123",
  "repo_head_sha": "abc123",
  "diverged": false,
  "files_changed": 5,
  "files": [
    {
      "path": "terraform/glue_jobs.tf",
      "status": "added",
      "additions": 50,
      "deletions": 0,
      "patch": "@@ -0,0 +1,50 @@\n..."
    }
  ],
  "commit_message_suggestion": "Add 2 Glue jobs for sources...",
  "pr_title_suggestion": "Add Glue Job Configuration",
  "pr_body_suggestion": "- Added glue_job_1\n- Added glue_job_2"
}
```

#### POST `/api/sessions/{session_id}/draft/update_meta`
**Purpose:** Persist user-editable metadata before PR creation

**Request:**
```json
{
  "draft_id": "dft_8a91bc",
  "branch_name": "my-custom-branch",
  "user_commit_message": "Custom commit message",
  "user_pr_title": "Custom PR Title",
  "user_pr_description": "Custom description"
}
```

**Response:**
```json
{
  "success": true,
  "draft_id": "dft_8a91bc"
}
```

#### POST `/api/sessions/{session_id}/draft/create_pr`
**Purpose:** Create single commit and open PR

**Request:**
```json
{
  "draft_id": "dft_8a91bc"
}
```

**Response on success:**
```json
{
  "success": true,
  "pr_url": "https://github.com/owner/repo/pull/123",
  "pr_number": 123,
  "commit_sha": "def456",
  "branch_name": "my-custom-branch"
}
```

**Response on failure (divergence):**
```json
{
  "success": false,
  "error": "Branch diverged",
  "draft_base_sha": "abc123",
  "repo_head_sha": "xyz789",
  "conflict_files": []
}
```

**Response on duplicate PR creation:**
```json
{
  "success": false,
  "error": "Pull Request creation already in progress.",
  "draft_id": "dft_8a91bc",
  "status": "PR_CREATING"
}
```

#### POST `/api/sessions/{session_id}/draft/discard`
**Purpose:** Mark draft as ABANDONED (read-only after that)

**Request:**
```json
{
  "draft_id": "dft_8a91bc"
}
```

**Response:**
```json
{
  "success": true,
  "draft_id": "dft_8a91bc",
  "status": "ABANDONED"
}
```

---

## Service Layer Changes

### DraftWorkspaceService Extensions

```python
class DraftWorkspaceService:
    # ... existing methods ...
    
    def collect_final_files(self, draft_id: str) -> List[Dict]:
        """
        Collect all files from draft as final source of truth for PR.
        
        Returns: List[{ path, content, mode }] ready for GitHub API
        
        Raises: DraftNotFoundError if draft doesn't exist
        """
        
    def get_draft(self, draft_id: str) -> Draft:
        """Fetch draft object (including metadata, files, snapshots)"""
        
    def update_draft_meta(self, draft_id: str, metadata: Dict) -> Draft:
        """Update user-editable fields: branch_name, commit_message, pr_title, pr_body"""
        
    def set_draft_status(self, draft_id: str, status: DraftStatus) -> Draft:
        """Atomic status transition with validation"""
        
    def mark_draft_pr_created(self, draft_id: str, pr_metadata: Dict) -> Draft:
        """Mark draft as PR_CREATED and store PR metadata"""
        
    def preview_diff(self, draft_id: str) -> Dict:
        """Compute diff between base_sha and draft tree_entries (no commit)"""
```

### GitHubService Extensions

```python
class GitHubService:
    # ... existing methods ...
    
    def create_single_commit_and_pr(
        self,
        repo_name: str,
        target_branch: str,
        base_sha: str,
        tree_entries: List[Dict],  # { path, content, mode }
        branch_name: str,
        commit_message: str,
        pr_title: str,
        pr_body: str
    ) -> Dict:
        """
        Atomic operation: create one commit, update branch, create PR.
        
        Returns: { commit_sha, pr_url, pr_number }
        
        Raises: GitHubAPIError if any step fails
        """
        
    def preview_tree_diff(
        self,
        repo_name: str,
        base_sha: str,
        tree_entries: List[Dict]
    ) -> Dict:
        """Compute diff without creating commit"""
        
    def get_current_head_sha(self, repo_name: str, branch: str) -> str:
        """Fetch current HEAD SHA for divergence detection"""
```

---

## Implementation Checklist (15 Tasks)

### Phase 1: Analysis & Inventory (Tasks 1-5)
- [ ] **Task 1:** Inventory all GitHub mutation callsites
- [ ] **Task 2:** Identify every create/update file operation
- [ ] **Task 3:** Identify every commit creation operation
- [ ] **Task 4:** Identify every branch update operation
- [ ] **Task 5:** Identify every PR creation operation

### Phase 2: Core Implementation (Tasks 6-11)
- [ ] **Task 6:** Refactor GitHub mutations through single path (`create_single_commit_and_pr`)
- [ ] **Task 7:** Implement `collect_final_files(draft_id)`
- [ ] **Task 8:** Implement `create_single_commit_and_pr()`
- [ ] **Task 9:** Implement Draft Freeze logic (status transitions)
- [ ] **Task 10:** Implement Duplicate PR Protection (check status before creating)
- [ ] **Task 11:** Implement Review metadata persistence (update_draft_meta endpoint)

### Phase 3: Testing & Validation (Tasks 12-15)
- [ ] **Task 12:** Add unit tests (mock GitHub, test state transitions, metadata persistence)
- [ ] **Task 13:** Add integration tests (end-to-end draft → PR, divergence scenarios)
- [ ] **Task 14:** Run complete test suite (ensure no regressions)
- [ ] **Task 15:** Produce implementation report (summary of changes, test results)

---

## Files to Modify (Summary)

### Core Services
- [backend/app/services/draft_workspace_service.py](backend/app/services/draft_workspace_service.py)
  - Add `collect_final_files(draft_id)`
  - Add `update_draft_meta`, `set_draft_status`, `mark_draft_pr_created`
  - Add `preview_diff`
  
- [backend/app/services/github_service.py](backend/app/services/github_service.py)
  - Add `create_single_commit_and_pr()`
  - Add `preview_tree_diff()`
  - Add `get_current_head_sha()`
  - Refactor any existing commit/PR logic to use new method

### API & Routing
- [backend/app/api/processor.py](backend/app/api/processor.py)
  - Wire draft metadata persistence
  - Wire PR creation logic
  
- [backend/app/api/routes.py](backend/app/api/routes.py)
  - Add/modify endpoints: preview_commit, update_meta, create_pr, discard

### State & Models
- [backend/app/graph/state.py](backend/app/graph/state.py)
  - Add DraftStatus enum
  - Add draft-related fields to GlueJobState
  
- [backend/app/models/session.py](backend/app/models/session.py) or similar
  - Extend Draft model with full metadata

### Tests (New Files)
- `backend/tests/test_draft_status_lifecycle.py` — status transitions
- `backend/tests/test_draft_freeze.py` — freeze/lock behavior
- `backend/tests/test_github_single_commit_and_pr.py` — single commit creation
- `backend/tests/test_draft_pr_creation_e2e.py` — end-to-end flows
- `backend/tests/test_duplicate_pr_protection.py` — concurrent PR protection

---

## Backward Compatibility
- Existing nodes that emit `file_edits` continue to work unchanged
- `ENABLE_DRAFT_WORKSPACE` feature flag gates all new behavior
- If flag is False, existing per-file commit behavior retained
- No breaking changes to session/state contract (only extensions)

---

## Error Handling

### Divergence Detection
- Compare `draft_base_sha` to current `repo_head_sha`
- If mismatch: return 409 with divergence metadata
- Store `conflict_files` for future conflict-resolution workflow
- Do NOT attempt auto-merge; require user decision

### Duplicate PR Protection
- Check draft status before entering `create_pr` handler
- If already `PR_CREATING`, reject immediately with clear message
- Return 409 or 429 status code

### GitHub API Failures
- If `create_blob` fails: return error, no cleanup needed
- If `create_tree` fails: return error, no cleanup needed
- If `create_commit` fails: return error, orphan blobs OK (cleanup via GC)
- If `update_ref` fails after commit: return error with partial-operation details
- If `create_pull` fails: commit + ref already updated; return error; allow manual PR creation

---

## Next Steps
1. Start Task 1: Inventory GitHub mutation callsites
2. Complete Phase 1 (analysis)
3. Proceed to Phase 2 (implementation)
4. Conclude with Phase 3 (testing)

