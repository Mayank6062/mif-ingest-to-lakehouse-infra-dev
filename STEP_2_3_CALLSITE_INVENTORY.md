# STEP 2.3 — GitHub Mutation Callsite Inventory
**Date:** 2026-06-12

---

## Summary

All GitHub mutations currently flow through **one entry point**:
- **`GitHubService.create_pr(state: dict)`** in [backend/app/services/github_service.py](backend/app/services/github_service.py#L308)

This is called by:
- **`create_pr_node(state)`** in [backend/app/graph/nodes/create_pr.py](backend/app/graph/nodes/create_pr.py#L15)

No other code paths directly call GitHub mutations.

---

## Complete Callsite Map

### Tier 1: User-Facing Triggering Node

**File:** [backend/app/graph/nodes/create_pr.py](backend/app/graph/nodes/create_pr.py)  
**Function:** `create_pr_node(state: GlueJobState) -> GlueJobState`  
**Lines:** 15–161

**Behavior:**
- Safety gate: checks `user_approved == True`
- Safety gate: checks `terraform_validation_status != "failed"`
- Creates branch name (or uses existing from state)
- Calls `GitHubService().create_pr(updated_state)` — line 94
- Handles success/failure and returns updated state with PR metadata

**Flow:**
```
create_pr_node
  ├─ Validates user_approved
  ├─ Validates terraform_validation_status
  ├─ Calls svc.create_pr(updated_state)      ← GitHub mutations occur here
  └─ Returns state with pr_url, branch_name, pr_number
```

---

### Tier 2: Service Layer (All GitHub Mutations)

**File:** [backend/app/services/github_service.py](backend/app/services/github_service.py)  
**Class:** `GitHubService`

#### Entry Point: `create_pr(state: dict) -> dict`
**Lines:** 308–410

**Key operations:**
1. Get GitHub repository object (authenticated)
2. Check GitHub for authoritative source-system existence
3. Get base branch SHA
4. **Create branch ref** — line 356: `repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base_sha)`
5. Commit files (either existing or new system)
6. **Create Pull Request** — line 375: `repo.create_pull(title=..., body=..., head=branch_name, base=...)`

**Output:** `{ pr_url, branch_name, pr_number, files_modified }`

#### Sub-operation 1: `_commit_existing_system(repo, branch_name, state, locals_path) -> list[str]`
**Lines:** 410–454

**Operations:**
- Read existing `locals.tf` from base branch
- Insert new job entry into `glue_jobs { }` block
- **Call `_create_or_update_file(...)`** to commit to PR branch — line 448

**Output:** `[ locals_path ]`

#### Sub-operation 2: `_commit_new_system(repo, branch_name, state) -> list[str]`
**Lines:** 455–492

**Operations:**
- **Call `_create_or_update_file(...)`** for `locals.tf` creation — line 477
- **Call `_create_or_update_file(...)`** for `glue.tf` creation — line 485

**Output:** `[ locals_path, glue_path ]`

#### File Mutation Helper: `_create_or_update_file(repo, path, content, message, branch) -> None`
**Lines:** 496–521

**Operations:**
- Check if file exists on branch
- **If exists: `repo.update_file(...)`** — line 508
- **If not exists: `repo.create_file(...)`** — line 518

**These are the lowest-level GitHub API calls for file mutations.**

---

## GitHub API Calls (Raw PyGithub Methods)

### Mutation Callsites (in execution order within `create_pr`):

1. **`repo.create_git_ref(ref=..., sha=...)`** (line 356 in create_pr)
   - **What:** Create a new branch
   - **When:** Once per PR
   - **Error handling:** Catches 422 (branch exists) and continues

2. **`repo.update_file(path=..., message=..., content=..., sha=..., branch=...)`** (line 508 in _create_or_update_file)
   - **What:** Update existing file with new content
   - **When:** Per file that exists in the repository
   - **Called by:** _commit_existing_system or _commit_new_system (if file pre-exists)

3. **`repo.create_file(path=..., message=..., content=..., branch=...)`** (line 518 in _create_or_update_file)
   - **What:** Create new file
   - **When:** Per file that does not yet exist in the repository
   - **Called by:** _commit_existing_system or _commit_new_system (if creating new)

4. **`repo.create_pull(title=..., body=..., head=..., base=...)`** (line 375 in create_pr)
   - **What:** Create Pull Request
   - **When:** Once per PR
   - **Must follow:** All file creations/updates must be complete

5. **`pr.add_to_labels(...)`** (line 383 in create_pr)
   - **What:** Add labels to PR (non-critical)
   - **When:** After PR creation
   - **Error handling:** Fail-gracefully (labels may not exist)

6. **`pr.create_review_request(reviewers=...)`** (line 393 in create_pr)
   - **What:** Assign reviewers to PR (non-critical)
   - **When:** After PR creation
   - **Error handling:** Fail-gracefully (reviewers may be invalid)

### Non-Mutation (Read-Only) Callsites:

- **`repo.get_branch(...)`** (line 349 in create_pr) — Get base branch SHA
- **`repo.get_contents(path, ref=branch)`** (line 509 in _get_file_content) — Check file existence
- **`self._gh.get_repo(...)`** (line 142) — Get repo object
- **`repo.get_source_system_repository_state(...)`** — Check if source system exists in repo

---

## Identified Mutation Sequence (Current Flow)

```
User clicks "Create PR"
    ↓
LangGraph routes to create_pr_node
    ↓
create_pr_node validates safety gates
    ↓
create_pr_node calls GitHubService().create_pr(state)
    ├─ [1] repo.create_git_ref(branch_name, base_sha)     ← BRANCH CREATED
    │
    ├─ IF source_exists:
    │   └─ _commit_existing_system()
    │       └─ [2] repo.update_file(locals.tf, content)   ← FILE UPDATED
    │
    ├─ IF NOT source_exists:
    │   └─ _commit_new_system()
    │       ├─ [3] repo.create_file(locals.tf, content)   ← FILE CREATED
    │       └─ [4] repo.create_file(glue.tf, content)     ← FILE CREATED
    │
    ├─ [5] repo.create_pull(title, body, branch_name)     ← PR CREATED
    ├─ [6] pr.add_to_labels(labels)                        ← LABELS ADDED (non-critical)
    └─ [7] pr.create_review_request(reviewers)             ← REVIEWERS ASSIGNED (non-critical)
    ↓
create_pr_node returns success
    ↓
LangGraph state updated with pr_url, pr_number, branch_name
```

---

## Problem: Current Flow Creates Multiple GitHub Mutations

**Issue:** The current flow performs **1 branch creation + 1-2 file mutations + 1 PR creation** in a sequence. Although this is **currently acceptable** (each PR is independent), the **Step 2.3 requirement is ONE COMMIT PER PR**, not per-file or per-job.

**Current behavior breakdown:**
- Branch is created
- Files are committed via individual `update_file` / `create_file` calls
- PR is created pointing to the branch

**This works but does not align with ONE COMMIT = ONE PR.**

---

## Target Refactoring (Step 2.3)

### New Single Mutation Method

**New method:** `GitHubService.create_single_commit_and_pr(...)`

**Signature:**
```python
def create_single_commit_and_pr(
    self,
    repo_name: str,
    target_branch: str,
    base_sha: str,
    tree_entries: List[Dict],      # { path, content, mode }
    branch_name: str,
    commit_message: str,
    pr_title: str,
    pr_body: str
) -> Dict:
    """
    Atomic operation: create one tree, one commit, update branch, create PR.
    Returns: { commit_sha, pr_url, pr_number }
    """
```

**Implementation sequence:**
```
1. For each file entry:
   └─ repo.create_git_blob(content)          ← CREATE BLOB
2. repo.create_git_tree(tree_entries)         ← CREATE TREE
3. repo.create_git_commit(message, tree, parent=base_sha)  ← CREATE SINGLE COMMIT
4. repo.update_ref(branch_name, commit_sha)   ← UPDATE BRANCH REF
5. repo.create_pull(title, body, branch_name) ← CREATE PR
```

**Key difference from current:**
- **Current:** Multiple `update_file` / `create_file` calls (each creates its own commit in GitHub history)
- **Target:** Single `create_git_commit` call with all files in one tree

---

## Files to Refactor

### Primary Changes

| File | Change | Lines |
|------|--------|-------|
| [backend/app/services/github_service.py](backend/app/services/github_service.py) | Add `create_single_commit_and_pr()`; refactor `create_pr()` to use it | New method |
| [backend/app/services/draft_workspace_service.py](backend/app/services/draft_workspace_service.py) | Add `collect_final_files(draft_id)` | New method |
| [backend/app/api/routes.py](backend/app/api/routes.py) | Add POST `/draft/create_pr` endpoint | New endpoint |
| [backend/app/api/processor.py](backend/app/api/processor.py) | Wire draft → PR creation logic | Updated |

### Secondary/Supporting

| File | Change | Lines |
|------|--------|-------|
| [backend/app/graph/state.py](backend/app/graph/state.py) | Add DraftStatus enum, draft fields | Extended |
| [backend/app/graph/nodes/create_pr.py](backend/app/graph/nodes/create_pr.py) | Route to API instead of direct GitHubService call (or vice versa) | Modified ~10 lines |

---

## Implementation Order (Tasks 2–5)

After **Task 1 (complete — this inventory)**, proceed:

1. **Task 2:** Identify every create/update file operation
   - **Result:** All in `_create_or_update_file` (lines 496–521)
   - **Action:** Will be replaced by blob creation in `create_single_commit_and_pr`

2. **Task 3:** Identify every commit creation operation
   - **Result:** Implicit in `update_file` / `create_file` (GitHub does auto-commit)
   - **Action:** Will be made explicit via `create_git_commit`

3. **Task 4:** Identify every branch update operation
   - **Result:** `create_git_ref` (line 356) and implicit branch tracking
   - **Action:** Will add explicit `update_ref` call in `create_single_commit_and_pr`

4. **Task 5:** Identify every PR creation operation
   - **Result:** `repo.create_pull(...)` (line 375 in `create_pr`)
   - **Action:** Will remain, but called after commit/branch are finalized

---

## Callsite Summary Table

| Operation | Current Method | Current Lines | New Method | Status |
|-----------|---|---|---|---|
| Validate user approval | `create_pr_node` | 18–30 | Same | Keep |
| Get base SHA | `create_pr` | 349 | Same | Keep |
| Create branch | `create_pr` | 356 | `create_single_commit_and_pr` | Refactor |
| Create file | `_create_or_update_file` | 518 | `create_single_commit_and_pr` (blob+tree) | Refactor |
| Update file | `_create_or_update_file` | 508 | `create_single_commit_and_pr` (blob+tree) | Refactor |
| Commit (implicit) | `update_file` / `create_file` | N/A | `create_single_commit_and_pr` (explicit) | Refactor |
| Create PR | `create_pr` | 375 | `create_single_commit_and_pr` | Refactor |

---

## Next Actions (Tasks 2–15)

- ✅ **Task 1:** Complete — Inventory created
- ⏳ **Task 2:** Identify every create/update file operation
  - Map all `_create_or_update_file` usage
- ⏳ **Task 3:** Identify every commit creation operation
  - Document implicit commits in PyGithub `update_file` / `create_file`
- ⏳ **Task 4:** Identify every branch update operation
  - Document `create_git_ref` and implicit branch tracking
- ⏳ **Task 5:** Identify every PR creation operation
  - Document `create_pull` call
- ⏳ **Task 6–15:** Refactor and test

