"""Explicit, private configuration; no import-time network or device activity."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from urllib.parse import urlparse


def state_directory() -> Path:
    root = Path(os.environ.get("EMOBOT_HOME", Path.home() / ".local" / "share" / "emobot-companion"))
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


@dataclass(frozen=True)
class Settings:
    api_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    api_key: str = ""
    fast_model: str = "qwen3.6-flash"
    reasoning_model: str = "deepseek-v4-flash"
    language: str = "zh"
    theme: str = "system"
    database_url: str = ""
    user: str = "local_user"
    memory_enabled: bool = True
    save_history: bool = True
    voice: str = "onyx"
    voice_enabled: bool = False
    asr_model: str = "whisper-1"
    tts_model: str = "tts-1"
    embedding_url: str = ""
    embedding_key: str = ""
    embedding_model: str = ""
    embedding_dimensions: int = 1024
    volcano_app_id: str = ""
    volcano_token: str = ""
    volcano_cluster: str = "volcano_tts"
    volcano_voice: str = "BV001_streaming"
    speech_provider: str = "openai"
    persona: str = "Be warm, concise, playful, and curious. 尊重用户，先倾听，再提供具体帮助。"

    def validate(self) -> Settings:
        if self.language not in {"zh", "en"} or self.theme not in {"system", "light", "dark"}:
            raise ValueError("Unsupported language or theme")
        if self.speech_provider not in {"openai", "volcano"}:
            raise ValueError("Unsupported speech provider")
        if not 1 <= self.embedding_dimensions <= 8192 or not self.user.strip():
            raise ValueError("Invalid embedding dimensions or user")
        for value in (self.api_url, self.embedding_url):
            if value:
                parsed = urlparse(value)
                if parsed.scheme != "https" and not (
                    parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
                ):
                    raise ValueError("API endpoints require HTTPS (localhost may use HTTP)")
                if (
                    not parsed.hostname
                    or parsed.username
                    or parsed.password
                    or parsed.query
                    or parsed.fragment
                ):
                    raise ValueError("Use an API base URL without credentials, query, or fragment")
        return self

    @classmethod
    def load(cls, path: Path | None = None) -> Settings:
        target = path or state_directory() / "settings.json"
        data = json.loads(target.read_text()) if target.exists() else {}
        if not isinstance(data, dict):
            raise ValueError("Configuration must be a JSON object")
        known = {f.name for f in fields(cls)}
        data = {k: v for k, v in data.items() if k in known}
        for name in known:
            value = os.environ.get("EMOBOT_" + name.upper())
            if value is not None:
                if name in {"memory_enabled", "save_history", "voice_enabled"}:
                    value = value.lower() in {"1", "true", "yes"}
                elif name == "embedding_dimensions":
                    value = int(value)
                data[name] = value
        return cls(**data).validate()

    def save(self, path: Path | None = None) -> None:
        self.validate()
        target = path or state_directory() / "settings.json"
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = target.with_suffix(".tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump(asdict(self), stream, ensure_ascii=False, indent=2)
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
