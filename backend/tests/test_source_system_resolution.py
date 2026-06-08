from unittest.mock import patch


def test_knowledge_agent_uses_github_as_source_of_truth_when_kb_disagrees():
    from app.agents.knowledge_agent import KnowledgeAgent

    with patch("app.agents.knowledge_agent.GitHubService") as mock_service:
        mock_service.return_value.get_source_system_repository_state.return_value = {
            "source_system": "saptcc",
            "base_branch": "main",
            "locals_path": "saptcc/locals.tf",
            "github_exists": False,
        }

        result = KnowledgeAgent().check_source_system("saptcc")

    assert result["knowledge_base_source_system_exists"] is True
    assert result["github_source_system_exists"] is False
    assert result["source_system_exists"] is False
    assert result["source_system_pattern"] == "new"
    assert result["source_system_decision_source"] == "github"


def test_check_source_system_node_uses_github_state_for_ui_message():
    from app.graph.nodes.check_source_system import check_source_system_node

    with patch("app.agents.knowledge_agent.GitHubService") as mock_service:
        mock_service.return_value.get_source_system_repository_state.return_value = {
            "source_system": "saptcc",
            "base_branch": "main",
            "locals_path": "saptcc/locals.tf",
            "github_exists": False,
        }

        result = check_source_system_node({"source_system": "saptcc"})

    assert result["source_system_exists"] is False
    assert result["github_source_system_exists"] is False
    assert "does not exist in GitHub" in result["messages"][0]["content"]
    assert "saptcc/locals.tf" in result["messages"][0]["content"]


def test_confirm_derived_shows_new_source_system_actions():
    from app.graph.nodes.confirm_derived import confirm_derived_node

    result = confirm_derived_node({
        "topic": "dev.saptcc.multi-1.raw",
        "environment": "dev",
        "source_system": "saptcc",
        "schema_grain": "multi-1",
        "job_key": "kafka-to-iceberg-batch-saptcc-multi-1",
        "kafka_secret_name": "minerva-dev-corp-mif-saptcc-gluejob-sa-cc-api-creds",
        "source_system_exists": False,
        "source_system_locals_path": "saptcc/locals.tf",
    })

    rows = result["messages"][0]["widget"]["rows"]
    folder_row = next(row for row in rows if row["field"] == "Source System Folder")
    action_row = next(row for row in rows if row["field"] == "Action")

    assert folder_row["value"] == "⚠️ New source system"
    assert action_row["value"] == "Create `saptcc/locals.tf` and `saptcc/glue.tf`"


def test_new_source_files_and_checklists_do_not_reference_vela():
    from app.agents.knowledge_agent import KnowledgeAgent

    agent = KnowledgeAgent()

    files_to_modify = agent.get_files_to_modify("saptcc", False, "new")
    pr_checklist = agent.get_pr_checklist("saptcc", False, "kafka-to-iceberg-batch-saptcc-multi-1")
    new_source_checklist = agent.get_new_source_checklist("saptcc")

    assert ".vela.py" not in files_to_modify
    assert all(".vela.py" not in item for item in pr_checklist)
    assert all(".vela.py" not in item for item in new_source_checklist)