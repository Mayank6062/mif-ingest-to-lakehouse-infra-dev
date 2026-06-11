from pydantic import SecretStr
from pydantic_settings import BaseSettings
from functools import lru_cache
import os

# Resolve .env relative to this file's directory (backend/) so the server
# finds it regardless of the working directory uvicorn is launched from.
_ENV_FILE = os.path.join(os.path.dirname(__file__), "..", ".env")


class Settings(BaseSettings):
    # Azure OpenAI via EPAM proxy
    azure_openai_api_key: SecretStr = SecretStr("")
    azure_openai_endpoint: str = "https://ai-proxy.lab.epam.com"
    azure_openai_deployment: str = "gpt-4.1-mini"
    azure_openai_api_version: str = "2024-02-01"

    # GitHub
    github_token: SecretStr = SecretStr("")
    github_repo_owner: str = ""
    github_repo_name: str = "mif-ingest-to-lakehouse-infra-dev"
    github_base_branch: str = "main"
    # Comma-separated GitHub usernames to assign as PR reviewers (optional)
    github_pr_reviewers: str = ""

    # App
    knowledge_base_path: str = "./knowledge_base"
    session_store_ttl_seconds: int = 3600
    redis_url: str = "redis://localhost:6379"
    # Set to False to use in-memory checkpointer (no Redis required).
    # Set to True to use AsyncShallowRedisSaver (STEP 20 Redis persistence).
    use_redis_checkpointer: bool = False

    # LangSmith observability (optional — disabled by default)
    langsmith_api_key: SecretStr = SecretStr("")
    langsmith_project: str = "glue-job-agent"
    langsmith_tracing_enabled: bool = False

    # Kafka + Schema Registry (used by check_kafka_topic node)
    enable_kafka_check: bool = True
    kafka_bootstrap_servers: str = "localhost:9092"
    schema_registry_url: str = "http://localhost:8081"
    kafka_admin_timeout_seconds: int = 10
    schema_registry_timeout_seconds: int = 5

    # Terraform execution controls
    enable_terraform_plan: bool = False
    enable_tfsec: bool = False

    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    class Config:
        env_file = _ENV_FILE
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
