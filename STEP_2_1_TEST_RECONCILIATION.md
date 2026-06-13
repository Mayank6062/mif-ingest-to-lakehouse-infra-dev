# STEP 2.1 — Test Reconciliation (Repository-First Topic Validation)
Date: 2026-06-12

Purpose
-------
Reconcile the Kafka-related failing tests observed after implementing repository-first topic validation (Step 2.1). For each failing test below I record the original test assumption, the current architecture behavior, and recommendations about obsolescence/retirement and replacement coverage.

Notes
-----
- I did not change any production code or tests — this is analysis only.
- The repository-based replacement tests live in `backend/tests/test_repository_topic_validation.py`.

Failing tests (Kafka-related)
--------------------------------

- Test: `backend/tests/test_check_kafka_topic.py::TestRule1TopicMissing::test_sets_kafka_topic_missing_flag`
  - Original Assumption: Missing topic in Kafka broker should set a missing flag (Kafka-authoritative).
  - Current Architecture Behavior: Repository absence blocks earlier; node sets `kafka_topic_missing`/routing based on repo check instead of broker probe.
  - Category: 1 (old Kafka-authoritative behavior)
  - Obsolete: Yes
  - Retire: Yes — replace with repository-first assertions
  - Replacement exists: Yes — `TestRule1RepoFileNotFound.test_kafka_topic_missing_flag_set` in `test_repository_topic_validation.py`.

- Test: `...::TestRule1TopicMissing::test_broker_error_message_included`
  - Original Assumption: Broker connection errors are surfaced and included in the blocking message.
  - Current Behavior: Broker errors are informational only when repo approves; if repo file missing, repository message replaces broker message.
  - Category: 1
  - Obsolete: Yes
  - Retire: Yes
  - Replacement exists: Yes — see `TestRule3RepoApproved.test_kafka_broker_warning_in_message` (repo-approved + kafka warnings informational).

- Test: `...::TestRule2NoSchema::test_sends_approval_dialog`
  - Original Assumption: Missing schema (Schema Registry) should produce an approval dialog (SR-authoritative path).
  - Current Behavior: Missing schema in repository blocks with repository message; Schema Registry is secondary/informational.
  - Category: 2 (old Schema Registry behavior)
  - Obsolete: Yes
  - Retire: Yes
  - Replacement exists: Yes — repository-level blocking tests cover the grain-missing scenario: `TestRule2SchemaGrainNotFound.*`.

- Test: `...::TestRule2NoSchema::test_current_step_is_check_kafka_topic`
  - Original Assumption: Workflow stays at `check_kafka_topic` when schema missing (broker/SR-driven flow).
  - Current Behavior: Workflow routes to `collect_topic` when repo file/grain missing (repository-first block).
  - Category: 3 (behavior explicitly removed by Architecture Freeze Rule 2)
  - Obsolete: Yes
  - Retire: Yes
  - Replacement exists: Yes — `TestRule2SchemaGrainNotFound.test_routes_to_collect_topic`.

- Test: `...::TestRule2NoSchema::test_sets_schema_check_needs_approval`
  - Original Assumption: Missing schema triggers `schema_check_needs_approval == True`.
  - Current Behavior: No approval emitted once repository check fails; approval flag remains False.
  - Category: 2
  - Obsolete: Yes
  - Retire: Yes
  - Replacement exists: Yes — repository tests assert `not approval_request` when repo blocks.

- Tests: `...::TestRule3SRUnavailable::test_sends_approval_dialog_for_all_sr_errors[...]` (parametrized cases)
  - Original Assumption: Various Schema Registry errors should cause approval dialogs / approval_request emissions.
  - Current Behavior: SR errors are informational if repository approves; if repository missing the file, repo message blocks and SR text is not used to trigger approval.
  - Category: 2
  - Obsolete: Yes
  - Retire: Yes
  - Replacement exists: Yes — `TestRule3RepoApproved.test_auto_advance_even_when_kafka_down` and `test_kafka_broker_warning_in_message` demonstrate informational handling of SR/broker errors under repo-approved flow.

- Test: `...::TestRule3SRUnavailable::test_sets_sr_unavailable_in_state`
  - Original Assumption: `schema_registry_available` should be False when SR unreachable and used to alter flow.
  - Current Behavior: SR availability still recorded only when repo approves; missing repo results in repo-block and SR flags are not authoritative.
  - Category: 2
  - Obsolete: Yes
  - Retire: Yes
  - Replacement exists: Partial — `TestRule3RepoApproved` covers SR fields when repo-approved; unit-level SR-unavailable handling is covered there.

- Test: `...::TestRule3SRUnavailable::test_error_text_in_message`
  - Original Assumption: Error text from SR should appear in the approval dialog message.
  - Current Behavior: When repo missing, repository-first message supersedes SR text; when repo present SR text is informational and included per `TestRule3RepoApproved.test_kafka_broker_warning_in_message`.
  - Category: 2
  - Obsolete: Yes
  - Retire: Yes
  - Replacement exists: Yes — see `TestRule3RepoApproved` variants.

- Tests: `...::TestRule4SchemaFound::test_auto_advance_for_any_positive_count[...]` (parametrized counts)
  - Original Assumption: Schema count from SR drives auto-advance or blocking behavior (SR-authoritative influence).
  - Current Behavior: With repository approval auto_advance is True regardless of broker/SR availability; SR counts are recorded but informational.
  - Category: 2
  - Obsolete: Yes
  - Retire: Yes
  - Replacement exists: Yes — `TestRule3RepoApproved.test_auto_advance_when_kafka_healthy` and related tests assert auto-advance under repo approval.

- Test: `...::TestRule4SchemaFound::test_sets_schema_exists_true`
  - Original Assumption: Schema existence (SR) should drive `schema_exists` True and possibly advance flow.
  - Current Behavior: `schema_exists` is populated only as informational after repo approval; repo approval is decisive.
  - Category: 2
  - Obsolete: Yes
  - Retire: Yes
  - Replacement exists: Yes — `TestRule3RepoApproved.test_kafka_fields_populated_when_broker_healthy`.

- Test: `...::TestRule4SchemaFound::test_current_step_is_check_kafka_topic`
  - Original Assumption: Current step remains `check_kafka_topic` when SR/schema present.
  - Current Behavior: Repo-approved flow keeps `current_step==check_kafka_topic`; repo-missing flows route to `collect_topic` — failing case indicates test was run against repo-missing simulation.
  - Category: 1/3 (depends on fixture) — effectively removed when repo is authoritative.
  - Obsolete: Yes
  - Retire: Yes
  - Replacement exists: Yes — covered by `TestRule3RepoApproved.test_current_step_stays_at_check_kafka_topic` when repo approves.

- Test: `...::TestRule4SchemaFound::test_schema_count_in_message_content`
  - Original Assumption: Message content should contain the SR schema count value (used for user info/approval decision).
  - Current Behavior: When repo missing, message is repository-block text; when repo present SR count appears informationally in approval/confirmation messages.
  - Category: 2
  - Obsolete: Yes
  - Retire: Yes
  - Replacement exists: Yes — `TestRule3RepoApproved.*` assert schema count visibility when appropriate.

- Test: `...::TestRule4SchemaFound::test_waiting_for_user_is_false`
  - Original Assumption: Workflow should not be waiting for user when SR/schema found (auto-advance behavior under old flow).
  - Current Behavior: Under repo-missing scenarios the workflow remains waiting for user (collect_topic); under repo-approved auto-advance is enforced.
  - Category: 2
  - Obsolete: Yes
  - Retire: Yes
  - Replacement exists: Yes — `TestRule3RepoApproved` auto-advance assertions.

- Test: `backend/tests/test_kafka_integration_flow.py::TestKafkaIntegrationFlow::test_step_chain_derive_to_kafka_to_source`
  - Original Assumption: End-to-end chain includes Kafka-driven check step (old flow expected `check_kafka_topic` or `derive_values`).
  - Current Behavior: Repository-first flow may route to `collect_topic` on repo-missing cases; integration expectations must be updated to account for repository-first block and new message shapes.
  - Category: 1 (Kafka-authoritative integration assumption)
  - Obsolete: Yes
  - Retire: Yes (integration-level test should be replaced with a repository-first integration test)
  - Replacement exists: No (unit-level repository tests exist; an updated integration test is not present yet).

- Tests: `backend/tests/test_kafka_integration_flow.py::{test_rule4_auto_advance_processor_behavior,test_rule2_rejection_restart_behavior,test_rule3_approval_continue_behavior}`
  - Original Assumption: Processor mapping and message widget payloads match the old Kafka-first node behavior (string widget_value vs dict); also auto-advance/rejection flows driven by SR/Kafka.
  - Current Behavior: Node now emits repository-first messages and widget shapes changed; `processor._map_user_input_to_state()` hit an attribute error because tests pass dicts instead of strings (integration-level mismatch).
  - Category: 1 (old Kafka-authoritative + message shape coupling)
  - Obsolete: Yes
  - Retire: Yes (or update to new message/widget contract)
  - Replacement exists: No — integration tests need updates to exercise repository-first flows and the new widget/message shapes.


Repository Topic Validation Coverage
-----------------------------------

Do the new repository-validation tests (`backend/tests/test_repository_topic_validation.py`) completely cover the requested scenarios?

- `topics_<source>.tf` missing: Covered (TestRule1RepoFileNotFound.*, including `test_routes_to_collect_topic`, `test_kafka_topic_missing_flag_set`).
- `schema_grain` missing: Covered (TestRule2SchemaGrainNotFound.*).
- `schema_grain` present: Covered (TestRule3RepoApproved.* — includes population of kafka fields and confirmation message assertions).
- GitHub exception: Covered (TestGitHubServiceFailure.* — exception -> collect_topic, kafka_topic_missing flag, no auto_advance).
- Malformed topic: Covered (TestMalformedTopics.* parametrize for short topics and message content).
- Existing source system vs new source system: Covered (TestRule1RepoFileNotFound.test_different_source_systems and TestValidateTopicInRepository.test_topic_file_path_is_correct).

Coverage summary: The repository-validation unit tests comprehensively cover the repository-first outcomes requested by Step 2.1 for unit-level behavior. They assert the blocking paths (repo missing, grain missing), the repo-approved path (informational Kafka/SR checks + auto-advance), GitHub errors, malformed topics, and multiple source systems.

Recommendations
---------------
- Retire or update the legacy `backend/tests/test_check_kafka_topic.py` suite: it asserts Kafka/SR-authoritative semantics that are incompatible with Architecture Freeze Rule 2. Replace its intent with repository-first equivalents (many already exist in `test_repository_topic_validation.py`).
- Update integration tests in `backend/tests/test_kafka_integration_flow.py` to exercise repository-first flows and the new message/widget payload shapes (these are integration-level and not covered by the new unit tests).
- Keep `test_repository_topic_validation.py` as the canonical unit test suite for Step 2.1. Expand integration tests to confirm end-to-end behavior (LangGraph processor + frontend widget mapping) under repository-first semantics.

End of reconciliation.
