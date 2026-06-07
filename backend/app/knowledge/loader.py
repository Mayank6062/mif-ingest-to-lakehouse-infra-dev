"""
Knowledge Base Loader — loads all files from knowledge_base/ as the single source of truth.
Files loaded:
  - validation_rules.json
  - terraform_template.json
  - source_systems.json
  - agent_system_prompt.md
  - decision_trees.md
  - README.md
"""

import json
import os
from functools import lru_cache
from typing import Any


class KnowledgeBaseLoader:
    _instance: "KnowledgeBaseLoader | None" = None

    def __init__(self, base_path: str):
        self.base_path = base_path
        self._validation_rules: dict = {}
        self._terraform_template: dict = {}
        self._source_systems: dict = {}
        self._system_prompt: str = ""
        self._decision_trees: str = ""
        self._loaded = False

    def load_all(self) -> None:
        """Load all knowledge base files into memory."""
        self._validation_rules = self._load_json("validation_rules.json")
        self._terraform_template = self._load_json("terraform_template.json")
        self._source_systems = self._load_json("source_systems.json")
        self._system_prompt = self._load_text("agent_system_prompt.md")
        self._decision_trees = self._load_text("decision_trees.md")
        self._loaded = True

    def _load_json(self, filename: str) -> dict:
        path = os.path.join(self.base_path, filename)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_text(self, filename: str) -> str:
        path = os.path.join(self.base_path, filename)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def _ensure_loaded(self):
        if not self._loaded:
            self.load_all()

    # ─── Validation Rules ───────────────────────────────────────────────────

    @property
    def validation_rules(self) -> dict:
        self._ensure_loaded()
        return self._validation_rules

    @property
    def topic_rules(self) -> list:
        return self.validation_rules.get("rules", {}).get("topic_naming", [])

    @property
    def worker_rules(self) -> list:
        return self.validation_rules.get("rules", {}).get("worker_config", [])

    @property
    def enterprise_rules(self) -> list:
        return self.validation_rules.get("rules", {}).get("enterprise_func", [])

    @property
    def sink_database_rules(self) -> list:
        return self.validation_rules.get("rules", {}).get("sink_database", [])

    @property
    def s3_warehouse_rules(self) -> list:
        return self.validation_rules.get("rules", {}).get("s3_warehouse", [])

    @property
    def all_rules_flat(self) -> list:
        """All rules across all categories as a flat list."""
        rules = []
        for category, rule_list in self.validation_rules.get("rules", {}).items():
            for rule in rule_list:
                rule["_category"] = category
                rules.append(rule)
        return rules

    # ─── Terraform Template ─────────────────────────────────────────────────

    @property
    def terraform_template(self) -> dict:
        self._ensure_loaded()
        return self._terraform_template

    @property
    def terraform_hcl_template(self) -> str:
        return self.terraform_template.get("output_template_hcl", "")

    @property
    def field_derivation_logic(self) -> dict:
        return self.terraform_template.get("field_derivation_logic", {})

    @property
    def terraform_fields(self) -> dict:
        return (
            self.terraform_template
            .get("terraform_entry_template", {})
            .get("fields", {})
        )

    # ─── Source Systems ──────────────────────────────────────────────────────

    @property
    def source_systems(self) -> dict:
        self._ensure_loaded()
        return self._source_systems

    @property
    def known_source_system_folders(self) -> list[str]:
        """List of all known source system folder names."""
        return [
            s["folder"]
            for s in self.source_systems.get("known_source_systems", [])
        ]

    def get_source_system_info(self, folder_name: str) -> dict | None:
        """Get metadata for a specific source system by folder name."""
        for s in self.source_systems.get("known_source_systems", []):
            if s["folder"] == folder_name:
                return s
        return None

    def source_system_exists(self, folder_name: str) -> bool:
        return folder_name in self.known_source_system_folders

    def get_pattern_type(self, folder_name: str) -> str:
        """Returns 'local_module', 'external_module', or 'new'."""
        info = self.get_source_system_info(folder_name)
        if info:
            return info.get("pattern_type", "local_module")
        return "new"

    # ─── Allowed Values (for UI dropdowns) ──────────────────────────────────

    @property
    def allowed_worker_types(self) -> list[str]:
        for rule in self.worker_rules:
            if rule.get("rule_id") == "WR-001":
                return rule.get("allowed_values", ["G.025X", "G.1X", "G.2X", "G.4X"])
        return ["G.025X", "G.1X", "G.2X", "G.4X"]

    @property
    def allowed_enterprise_funcs(self) -> list[str]:
        for rule in self.enterprise_rules:
            if rule.get("rule_id") == "ER-001":
                return rule.get("allowed_values", ["AGTR", "CORP", "FOOD", "SPEC"])
        return ["AGTR", "CORP", "FOOD", "SPEC"]

    @property
    def allowed_job_types(self) -> list[str]:
        rules = self.validation_rules.get("rules", {}).get("job_type", [])
        for rule in rules:
            if rule.get("rule_id") == "JOBT-001":
                return rule.get("allowed_values", ["unified", "unified_batch"])
        return ["unified", "unified_batch", "kafka_to_iceberg", "kafka_to_iceberg_batch"]

    @property
    def allowed_environments(self) -> list[str]:
        for rule in self.topic_rules:
            if rule.get("rule_id") == "TR-004":
                return rule.get("allowed_values", ["dev", "snd", "prod"])
        return ["dev", "snd", "prod"]

    @property
    def allowed_subgroups(self) -> list[str]:
        rules = self.validation_rules.get("rules", {}).get("subgroup", [])
        for rule in rules:
            if rule.get("rule_id") == "SGR-001":
                return rule.get("allowed_values", ["apac", "na", "latam"])
        return ["apac", "na", "latam"]

    @property
    def allowed_scheduling_modes(self) -> list[str]:
        rules = self.validation_rules.get("rules", {}).get("job_type", [])
        for rule in rules:
            if rule.get("rule_id") == "JOBT-002":
                return rule.get("allowed_values", ["manual", "scheduled"])
        return ["manual", "scheduled"]

    @property
    def topic_regex(self) -> str:
        for rule in self.topic_rules:
            if rule.get("rule_id") == "TR-001":
                return rule.get("regex", r"^(dev|snd|prod)\.[a-z][a-z0-9-]*\.[a-z][a-z0-9-]*\.raw$")
        return r"^(dev|snd|prod)\.[a-z][a-z0-9-]*\.[a-z][a-z0-9-]*\.raw$"

    # ─── Defaults ────────────────────────────────────────────────────────────

    @property
    def defaults(self) -> dict:
        fields = self.terraform_fields
        return {
            "worker_type": fields.get("worker_type", {}).get("default", "G.1X"),
            "number_of_workers": fields.get("number_of_workers", {}).get("default", 2),
            "job_type": fields.get("job_type", {}).get("default", "unified"),
            "job_version": fields.get("job_version", {}).get("default", "0.3.0"),
            "glue_version": fields.get("glue_version", {}).get("default", "5.0"),
            "ent_func": "AGTR",
            "subgroup": "APAC",
            "scheduling_mode": "manual",
        }

    # ─── System prompt ───────────────────────────────────────────────────────

    @property
    def system_prompt(self) -> str:
        self._ensure_loaded()
        return self._system_prompt


@lru_cache()
def get_knowledge_base(base_path: str = None) -> KnowledgeBaseLoader:
    from app.config import get_settings
    settings = get_settings()
    path = base_path or settings.knowledge_base_path
    loader = KnowledgeBaseLoader(path)
    loader.load_all()
    return loader
