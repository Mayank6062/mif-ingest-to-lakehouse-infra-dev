"""
LLM Service — wraps Azure OpenAI via EPAM proxy.
Used for conversational text generation only.
All business logic (validation, derivation) is deterministic Python.
"""

from langsmith import traceable
from app.config import get_settings
from typing import Any

# Delay import of openai until actually creating a client to allow tests
# to import this module when openai is not installed.
_client: Any = None
AzureOpenAI = None


def get_llm_client() -> Any:
    global _client
    if _client is None:
        settings = get_settings()
        azure_cls = AzureOpenAI
        if azure_cls is None:
            try:
                from openai import AzureOpenAI as azure_cls
            except Exception:
                raise
        _client = azure_cls(
            api_key=settings.azure_openai_api_key.get_secret_value(),
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
        )
    return _client


@traceable(run_type="llm")
def chat_complete(messages: list[dict], system_prompt: str = "") -> str:
    """
    Send a chat completion request and return the assistant's reply.
    messages: list of {"role": "user"/"assistant", "content": "..."}
    """
    client = get_llm_client()
    settings = get_settings()

    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    response = client.chat.completions.create(
        model=settings.azure_openai_deployment,
        messages=full_messages,
        temperature=0.3,
        max_tokens=800,
    )
    return response.choices[0].message.content or ""
