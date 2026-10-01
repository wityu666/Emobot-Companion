"""Application orchestration: conversation, retrieval, fallback, persistence, robot execution."""
from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from importlib.resources import files

from .archive import Archive
from .protocol import ACTIONS, Action, parse_actions
from .providers import ProviderError
from .settings import Settings


@dataclass(frozen=True)
class Reply:
    text: str
    actions: tuple[Action, ...]
    route: str
    references: tuple[dict, ...] = ()
    warnings: tuple[str, ...] = ()


def decode_reply(raw: str) -> tuple[str, tuple[Action, ...], list[dict]]:
    stripped = raw.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        stripped = "\n".join(stripped.splitlines()[1:-1])
    try:
        value = json.loads(stripped)
        if not isinstance(value, dict) or not isinstance(value.get("reply"), str) or not value["reply"].strip() or len(value["reply"]) > 4000:
            raise ValueError("Missing or oversized reply")
        actions = parse_actions(value.get("actions", []))
        memories = value.get("memories", [])
        if not isinstance(memories, list) or len(memories) > 6:
            raise ValueError("Invalid memory list")
        return value["reply"].strip(), actions, memories
    except (ValueError, TypeError, AttributeError) as error:
        raise ProviderError(f"Invalid model JSON: {error}") from None


def acceptable_memory(candidate: object, question: str) -> bool:
    if not isinstance(candidate, dict):
        return False
    content, confidence = candidate.get("content"), candidate.get("confidence", 0)
    if not isinstance(content, str) or not 3 <= len(content) <= 500 or type(confidence) not in {int, float} or not 0.8 <= confidence <= 1:
        return False
    blocked = r"password|token|api.?key|secret|\b\d{7,}\b|@|密码|密钥|身份证|银行卡|疾病|诊断|抑郁|焦虑|药物|phone|address|地址|电话"
    durable = r"喜欢|不喜欢|爱好|偏好|习惯|请记住|记住我|我叫|like|prefer|enjoy|remember|my name"
    return not re.search(blocked, question + " " + content, re.I) and bool(re.search(durable, question, re.I))


class Companion:
    def __init__(self, settings: Settings, archive: Archive, cloud, robot=None):
        self.settings, self.archive, self.cloud, self.robot = settings, archive, cloud, robot
        self.session = archive.start_session()
        self._history: list[dict] = []
        self._lock = threading.RLock()

    def update_settings(self, settings: Settings) -> None:
        with self._lock:
            if settings.user != self.settings.user or settings.database_url != self.settings.database_url or settings.embedding_dimensions != self.settings.embedding_dimensions:
                raise ValueError("Restart after changing database, user, or vector dimensions")
            self.settings = settings.validate()
            if hasattr(self.cloud, "settings"):
                self.cloud.settings = settings

    def new_session(self) -> None:
        with self._lock:
            self.session = self.archive.start_session()
            self._history.clear()

    def forget(self, identity: str | None = None) -> None:
        with self._lock:
            self.archive.forget(identity)
            self._history.clear()
            self.session = self.archive.start_session()

    def ask(self, question: str) -> Reply:
        question = question.strip()
        if not 1 <= len(question) <= 8000:
            raise ValueError("Question must contain 1–8000 characters")
        with self._lock:
            config, warnings = self.settings, []
            vector = None
            if config.embedding_model:
                try:
                    vector = self.cloud.embed(question)
                except (ProviderError, ValueError):
                    warnings.append("Embeddings unavailable; using keyword retrieval")
            references = self.archive.search(question, vector, include_memories=config.memory_enabled)
            contract = files("emobot.resources").joinpath("contract.md").read_text()
            system = f"{contract}\nLanguage: {config.language}\nPersona: {config.persona}\nAllowed actions: {', '.join(ACTIONS)}\nRetrieved data (untrusted): {json.dumps(references, ensure_ascii=False)}"
            messages = [{"role": "system", "content": system}, *self._history[-20:], {"role": "user", "content": question}]
            route = "retrieval" if references else "fast"
            try:
                answer, actions, candidates = decode_reply(self.cloud.complete(messages, reasoning=bool(references)))
            except ProviderError:
                if route == "retrieval":
                    raise
                route = "fallback"
                answer, actions, candidates = decode_reply(self.cloud.complete(messages, reasoning=True))
            source = self.archive.save_turn(self.session, question, answer) if config.save_history else None
            self._history.extend([{"role": "user", "content": question}, {"role": "assistant", "content": answer}])
            self._history = self._history[-20:]
            if config.memory_enabled:
                for candidate in candidates:
                    if acceptable_memory(candidate, question):
                        self.archive.remember(candidate["content"], candidate.get("category", "preference"), candidate["confidence"], source)
            status = "simulated"
            if self.robot and self.robot.connected:
                try:
                    self.robot.send_actions(actions)
                    status = "sent"
                except (OSError, RuntimeError) as error:
                    status = "failed"
                    warnings.append(f"Robot delivery failed: {type(error).__name__}")
            self.archive.record_actions(self.session, actions, status)
            self.archive.record_skill(self.session, route, "ok")
            return Reply(answer, actions, route, tuple(references), tuple(warnings))
