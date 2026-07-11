from dataclasses import dataclass
import json
import time

import httpx

from app.core.config import get_settings

MISTRAL_CHAT_URL = "https://api.mistral.ai/v1/chat/completions"


@dataclass
class MistralJsonResult:
    data: dict
    model_name: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int


def parse_json_object(content: str) -> dict:
    normalized = content.strip()
    if normalized.startswith("```"):
        first_newline = normalized.find("\n")
        normalized = normalized[first_newline + 1 :] if first_newline >= 0 else normalized[3:]
        if normalized.endswith("```"):
            normalized = normalized[:-3].rstrip()

    try:
        value = json.loads(normalized)
    except json.JSONDecodeError:
        start = normalized.find("{")
        end = normalized.rfind("}")
        if start < 0 or end <= start:
            raise
        value = json.loads(normalized[start : end + 1])

    if not isinstance(value, dict):
        raise ValueError("Mistral response must be a JSON object")
    return value


class MistralClient:
    def __init__(self, model_name: str | None = None) -> None:
        self.settings = get_settings()
        self.model_name = model_name or self.settings.mistral_model

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.mistral_api_key.strip())

    async def complete_json(self, messages: list[dict[str, str]], purpose: str) -> MistralJsonResult:
        if not self.is_configured:
            raise RuntimeError("MISTRAL_API_KEY is not configured")
        started = time.perf_counter()
        headers = {
            "authorization": f"Bearer {self.settings.mistral_api_key}",
            "content-type": "application/json",
        }
        last_error: Exception | None = None
        configured_attempts = max(1, self.settings.mistral_max_retries)
        if purpose.endswith("_revision"):
            attempts = min(2, configured_attempts)
        elif purpose.endswith("_generation"):
            attempts = min(2, configured_attempts)
        else:
            attempts = configured_attempts
        configured_timeout = float(self.settings.mistral_request_timeout_seconds)
        request_timeout = configured_timeout if purpose == "factual_notes" else max(180.0, configured_timeout)
        async with httpx.AsyncClient(timeout=request_timeout) as client:
            for attempt in range(attempts):
                request_messages = messages
                if attempt > 0:
                    retry_instruction = (
                        "The previous revision was too short or still failed a quality check. Rewrite the complete article, "
                        "meet the requested article length, paraphrase every source sentence, and return one valid JSON object."
                        if purpose.endswith("_revision")
                        else "The previous response was invalid or truncated. Return one compact JSON object only. "
                        "Keep every array concise, omit repetition, and close all JSON strings, arrays, and objects."
                    )
                    request_messages = [
                        *messages,
                        {
                            "role": "user",
                            "content": retry_instruction,
                        },
                    ]
                payload = {
                    "model": self.model_name,
                    "messages": request_messages,
                    "temperature": 0.1,
                    "max_tokens": 3600 if purpose == "factual_notes" else 5000,
                    "response_format": {"type": "json_object"},
                }
                try:
                    response = await client.post(MISTRAL_CHAT_URL, headers=headers, json=payload)
                    response.raise_for_status()
                    body = response.json()
                    choice = body["choices"][0]
                    if choice.get("finish_reason") == "length":
                        raise RuntimeError("Mistral response exceeded the output token limit")
                    content = choice["message"]["content"]
                    usage = body.get("usage") or {}
                    return MistralJsonResult(
                        data=parse_json_object(content),
                        model_name=body.get("model") or self.model_name,
                        input_tokens=usage.get("prompt_tokens"),
                        output_tokens=usage.get("completion_tokens"),
                        latency_ms=int((time.perf_counter() - started) * 1000),
                    )
                except Exception as exc:
                    message = str(exc).strip() or type(exc).__name__
                    last_error = RuntimeError(message)
        raise RuntimeError(f"Mistral {purpose} failed: {last_error}")
