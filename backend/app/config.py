from pydantic import SecretStr
from pydantic_settings import BaseSettings
from functools import lru_cache
import os


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

    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
