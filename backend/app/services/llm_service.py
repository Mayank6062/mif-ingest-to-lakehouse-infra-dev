"""
LLM Service — wraps Azure OpenAI via EPAM proxy.
Used for conversational text generation only.
All business logic (validation, derivation) is deterministic Python.
"""

from langsmith import traceable
from openai import AzureOpenAI
from app.config import get_settings

_client: AzureOpenAI | None = None


def get_llm_client() -> AzureOpenAI:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AzureOpenAI(
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
