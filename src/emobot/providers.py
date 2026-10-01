"""OpenAI-compatible REST, with bounded I/O and provider-independent response validation."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import httpx

from .settings import Settings


class ProviderError(RuntimeError):
    pass


class Cloud:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.http = httpx.Client(timeout=httpx.Timeout(30, connect=8), follow_redirects=False)

    def close(self) -> None:
        self.http.close()

    def _request(
        self,
        path: str,
        *,
        body: dict | None = None,
        url: str | None = None,
        key: str | None = None,
        auth_prefix: str = "Bearer ",
        **kwargs,
    ) -> httpx.Response:
        credential = self.settings.api_key if key is None else key
        if not credential:
            raise ProviderError("Configure an API key before using cloud services")
        endpoint = (url or self.settings.api_url).rstrip("/") + path
        try:
            with self.http.stream(
                "POST", endpoint, headers={"Authorization": auth_prefix + credential}, json=body, **kwargs
            ) as response:
                response.raise_for_status()
                data = bytearray()
                for part in response.iter_bytes():
                    data.extend(part)
                    if len(data) > 12_000_000:
                        raise ProviderError("Provider response exceeds 12 MB")
                return httpx.Response(response.status_code, headers=response.headers, content=bytes(data))
        except httpx.HTTPStatusError as error:
            raise ProviderError(f"Provider HTTP {error.response.status_code}") from None
        except httpx.HTTPError:
            raise ProviderError("Provider connection failed or timed out") from None

    def complete(self, messages: list[dict], *, reasoning: bool = False) -> str:
        model = self.settings.reasoning_model if reasoning else self.settings.fast_model
        response = self._request(
            "/chat/completions",
            body={
                "model": model,
                "messages": messages,
                "temperature": 0.4 if reasoning else 0.6,
                "max_tokens": 1200,
                "stream": False,
            },
        )
        try:
            value = response.json()["choices"][0]["message"]["content"]
            if not isinstance(value, str) or not value.strip():
                raise ValueError
            return value
        except (ValueError, KeyError, TypeError, IndexError):
            raise ProviderError("Provider returned an invalid chat response") from None

    def embed(self, content: str) -> list[float]:
        config = self.settings
        if not config.embedding_model:
            raise ProviderError("Configure an embedding model first")
        response = self._request(
            "/embeddings",
            url=config.embedding_url or config.api_url,
            key=config.embedding_key or config.api_key,
            body={
                "model": config.embedding_model,
                "input": content,
                "dimensions": config.embedding_dimensions,
            },
        )
        try:
            vector = response.json()["data"][0]["embedding"]
            if not isinstance(vector, list) or any(type(v) not in {int, float} for v in vector):
                raise ValueError
            return [float(v) for v in vector]
        except (ValueError, KeyError, TypeError, IndexError):
            raise ProviderError("Provider returned invalid embeddings") from None

    def transcribe(self, path: Path) -> str:
        with path.open("rb") as stream:
            response = self._request(
                "/audio/transcriptions",
                files={"file": (path.name, stream, "audio/wav")},
                data={"model": self.settings.asr_model},
            )
        try:
            result = response.json()["text"]
            if not isinstance(result, str) or not result.strip():
                raise ValueError
            return result.strip()
        except (ValueError, KeyError, TypeError):
            raise ProviderError("Provider returned invalid transcription") from None

    def synthesize(self, content: str) -> bytes:
        if self.settings.speech_provider == "volcano":
            return self._volcano(content)
        return self._request(
            "/audio/speech",
            body={
                "model": self.settings.tts_model,
                "input": content,
                "voice": self.settings.voice,
                "response_format": "mp3",
            },
        ).content

    def _volcano(self, content: str) -> bytes:
        from .archive import uid

        config = self.settings
        body = {
            "app": {
                "appid": config.volcano_app_id,
                "token": config.volcano_token,
                "cluster": config.volcano_cluster,
            },
            "user": {"uid": config.user},
            "audio": {"voice_type": config.volcano_voice, "encoding": "mp3"},
            "request": {"reqid": uid(), "text": content, "operation": "query"},
        }
        response = self._request(
            "/api/v1/tts",
            url="https://openspeech.bytedance.com",
            key=config.volcano_token,
            body=body,
            auth_prefix="Bearer; ",
        )
        try:
            data = response.json()
            if data.get("code") != 3000:
                raise ValueError
            return base64.b64decode(data["data"], validate=True)
        except (ValueError, KeyError, TypeError):
            raise ProviderError("Volcano TTS rejected the synthesis request") from None


class DemoCloud:
    """Explicit deterministic demo. Never used as a silent cloud fallback."""

    def close(self) -> None:
        pass

    def embed(self, content: str) -> list[float]:
        raise ProviderError("Demo mode has no cloud embeddings; use keyword retrieval")

    def complete(self, messages: list[dict], *, reasoning: bool = False) -> str:
        english = "Language: en" in messages[0]["content"]
        question = messages[-1]["content"]
        answer = (
            f"Demo: I heard you say '{question[:100]}'. What would help you today?"
            if english
            else f"演示模式：我听到你说“{question[:100]}”。今天有什么想一起聊聊的？"
        )
        return json.dumps(
            {
                "reply": answer,
                "actions": [
                    {"action": "eye_happy", "duration": 700},
                    {"action": "head_nod", "duration": 800},
                ],
                "memories": [],
            },
            ensure_ascii=False,
        )
