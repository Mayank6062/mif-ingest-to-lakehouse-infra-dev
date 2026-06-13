PHASE 2.3 — FINAL RUNTIME VERIFICATION

Objective
- Verify at runtime whether repository validation blocks secondary Kafka validation.

Actions Performed
1. Inserted temporary debug prints into `backend/app/graph/nodes/check_kafka_topic.py` to trace execution (local, temporary; reverted after test).
2. Ran a single failing legacy Kafka test with full stdout: 
   `py -m pytest backend/tests/test_check_kafka_topic.py::TestRule2NoSchema::test_sends_approval_dialog -q -s -v`

Captured Evidence (relevant stdout excerpt)
- LOG 1: START REPOSITORY VALIDATION
- LOG 2: source_system=saptcc schema_grain=multi-2
- LOG 3: resolved_file_path=confluent_minerva_dev/topics_saptcc.tf
- LOG 4: repository_file_found=False
- Test outcome: node returned blocking message: "🚫 **Topic not found in repository.** ..."

Interpretation / Execution Path
- The node performs the repository-authoritative check first (GitHubService.validate_topic_in_repository).
- When the repository check indicates the topics file is absent (`topic_file_exists=False`), the node immediately returns a HARD BLOCK message and routes to STEP_COLLECT_TOPIC.
- Secondary Kafka checks (KafkaService.check_topic_exists and get_schema_count) are never executed in this failing case — the repository check short-circuited the flow.

Root Cause
- Repository-first architecture is implemented in `check_kafka_topic_node`: repository validation is explicitly prioritized and returns a blocking outcome when the topics file or schema grain is not present in the GitHub repository. This behavior matches the code in `backend/app/services/github_service.py` where `validate_topic_in_repository()` returns `topic_file_exists=False` when the file is not found on the configured base branch.

Conclusion
- Runtime verification confirms: Repository validation is authoritative and blocks Kafka/SR checks when the repository file or schema grain is absent. Secondary Kafka checks are informational only and do not run if the repository check fails.

Recommendation
- Classify legacy Kafka-first tests that expect Kafka/SR to be authoritative as obsolete; replace or update them to repository-first semantics. Continue running and classifying HCL security and SGR tests separately per the Phase 2.3 plan.

Notes
- Temporary debug edits were reverted immediately after the test run; no lasting code changes were committed.
- Full test log and terminal output are available in the test run history if further evidence is required.

Files inspected
- backend/app/graph/nodes/check_kafka_topic.py
- backend/app/services/github_service.py

Prepared by: GitHub Copilot (using GPT-5 mini)
Date: 2026-06-13
