import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings, Settings
from app.api.websocket import router as ws_router
from app.api.routes import router as api_router
from app.knowledge.loader import KnowledgeBaseLoader
from app.graph.builder import initialize_graph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.redis.ashallow import AsyncShallowRedisSaver

settings = get_settings()


def _validate_required_config(s: Settings) -> None:
    """
    Validate that all required configuration values are present.
    Raises RuntimeError with a clear message listing every missing variable.
    Never prints or logs secret values — only indicates presence/absence.
    """
    errors: list[str] = []

    if not s.azure_openai_api_key.get_secret_value():
        errors.append("AZURE_OPENAI_API_KEY is not set")
    if not s.azure_openai_endpoint:
        errors.append("AZURE_OPENAI_ENDPOINT is not set")
    if not s.github_token.get_secret_value():
        errors.append("GITHUB_TOKEN is not set")
    if not s.github_repo_owner:
        errors.append("GITHUB_REPO_OWNER is not set")
    if not s.github_repo_name:
        errors.append("GITHUB_REPO_NAME is not set")

    if errors:
        bullet_list = "\n".join(f"  - {e}" for e in errors)
        raise RuntimeError(
            f"Server startup aborted — missing required configuration:\n{bullet_list}\n\n"
            "Set the missing variables in backend/.env (copy from .env.example) "
            "or as environment variables, then restart the server."
        )


def _configure_audit_logger(log_dir: Path) -> None:
    """
    Configure the "audit" logger to write structured JSONL to log_dir/audit.jsonl.
    Rotates daily at midnight, retains 90 days of backups.
    Emits raw JSON lines only — no logging prefix.
    Guard prevents duplicate handler registration on repeated calls (e.g. tests).
    """
    audit = logging.getLogger("audit")
    if audit.handlers:
        return  # already configured — skip to prevent duplicate output
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = TimedRotatingFileHandler(
        log_dir / "audit.jsonl",
        when="midnight",
        backupCount=90,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    audit.setLevel(logging.INFO)
    audit.addHandler(handler)
    audit.propagate = False  # do not emit to root logger


def _configure_langsmith(s: Settings) -> None:
    """
    Configure LangSmith tracing environment variables at server startup.
    Sets LANGSMITH_TRACING_V2, LANGSMITH_API_KEY, and LANGSMITH_PROJECT only
    when tracing is explicitly enabled AND a non-empty API key is configured.
    Clears all LangSmith/LangChain tracing vars when disabled to prevent stale
    env state from a previous server run.
    Never prints or logs the API key value.
    """
    if s.langsmith_tracing_enabled and s.langsmith_api_key.get_secret_value():
        os.environ["LANGSMITH_TRACING_V2"] = "true"
        os.environ["LANGSMITH_API_KEY"] = s.langsmith_api_key.get_secret_value()
        os.environ["LANGSMITH_PROJECT"] = s.langsmith_project
        print("\u2705 LangSmith tracing enabled")
    else:
        for key in (
            "LANGSMITH_TRACING_V2", "LANGSMITH_API_KEY", "LANGSMITH_PROJECT",
            "LANGCHAIN_TRACING_V2", "LANGCHAIN_API_KEY", "LANGCHAIN_PROJECT",
        ):
            os.environ.pop(key, None)
        print("\u2139\ufe0f LangSmith tracing disabled")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    _configure_audit_logger(Path(__file__).parent.parent / "logs")
    _validate_required_config(settings)
    _configure_langsmith(settings)
    print("✅ OpenAI key configured")
    print("✅ GitHub token configured")
    loader = KnowledgeBaseLoader(settings.knowledge_base_path)
    loader.load_all()
    print("✅ Knowledge base loaded successfully")
    print(f"   Source systems: {len(loader.source_systems.get('known_source_systems', []))}")
    print(f"   Validation rules loaded: YES")
    print(f"   Terraform template loaded: YES")
    if settings.use_redis_checkpointer:
        # ── STEP 20: Redis persistence (production path) ──────────────────
        redis_ctx = AsyncShallowRedisSaver(
            redis_url=settings.redis_url,
            ttl={
                "default_ttl": settings.session_store_ttl_seconds / 60,
                "refresh_on_read": True,
            },
        )
        async with redis_ctx as checkpointer:
            initialize_graph(checkpointer)
            print(f"\u2705 Redis checkpointer initialized ({settings.redis_url})")
            
            # ── Initialize Redis-backed session registry (tokens persist) ──
            from app.models.session import RedisSessionRegistry, set_redis_registry
            import redis.asyncio as redis_asyncio
            redis_client = redis_asyncio.from_url(settings.redis_url)
            redis_registry = RedisSessionRegistry(
                redis_client=redis_client,
                ttl_seconds=settings.session_store_ttl_seconds
            )
            set_redis_registry(redis_registry)
            print(f"\u2705 Redis session registry initialized (tokens persist)")
            
            yield
            
            # Close Redis client on shutdown
            await redis_client.close()
        # AsyncShallowRedisSaver.__aexit__ closes the Redis connection on shutdown
    else:
        # ── Dev bypass: in-memory checkpointer (no Redis required) ────────
        # State is lost on server restart. Suitable for local development only.
        checkpointer = MemorySaver()
        initialize_graph(checkpointer)
        print("\u26a0\ufe0f  In-memory checkpointer active (USE_REDIS_CHECKPOINTER=false)")
        print("   Session state will NOT persist across server restarts.")
        print("   Session tokens will NOT persist across server restarts.")
        yield


app = FastAPI(
    title="MIF Glue Job Agent",
    description="AI-powered Glue Job creation agent for mif-ingest-to-lakehouse-infra-dev",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ws_router)
app.include_router(api_router, prefix="/api")


@app.get("/")
async def root():
    return {"status": "ok", "service": "MIF Glue Job Agent"}
