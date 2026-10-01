"""One transactional archive for local SQLite or PostgreSQL with pgvector."""
from __future__ import annotations

import hashlib
import math
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    JSON,
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    delete,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.pool import StaticPool

from .settings import Settings, state_directory


def uid() -> str:
    return uuid.uuid4().hex


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def terms(value: str) -> set[str]:
    result = set(re.findall(r"[a-z0-9_]{2,}", value.lower()))
    for run in re.findall(r"[\u4e00-\u9fff]+", value):
        result.update(run[i:i + 2] for i in range(max(1, len(run) - 1)))
    return result


def cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    denominator = math.sqrt(sum(x*x for x in left) * sum(x*x for x in right))
    return sum(a*b for a, b in zip(left, right)) / denominator if denominator else 0.0


class Archive:
    def __init__(self, settings: Settings, url: str | None = None):
        self.user = settings.user
        self.dimensions = settings.embedding_dimensions
        address = url or settings.database_url or f"sqlite:///{state_directory() / 'companion.db'}"
        options = {"connect_args": {"check_same_thread": False}} if address.startswith("sqlite") else {}
        if address in {"sqlite://", "sqlite:///:memory:"}:
            options["poolclass"] = StaticPool
        self.engine = create_engine(address, **options)
        vector_type = JSON()
        if self.engine.dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector
            vector_type = vector_type.with_variant(Vector(self.dimensions), "postgresql")
            with self.engine.begin() as connection:
                connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        meta = MetaData()
        self.users = Table("users", meta, Column("id", String, primary_key=True), Column("created", String))
        self.devices = Table("devices", meta, Column("id", String, primary_key=True), Column("user_id", String), Column("transport", String), Column("last_seen", String))
        self.sessions = Table("sessions", meta, Column("id", String, primary_key=True), Column("user_id", String, index=True), Column("created", String))
        self.messages = Table("messages", meta, Column("id", String, primary_key=True), Column("user_id", String, index=True), Column("session_id", String, index=True), Column("role", String), Column("content", Text), Column("created", String))
        self.memories = Table("memories", meta, Column("id", String, primary_key=True), Column("user_id", String, index=True), Column("content", Text), Column("category", String), Column("confidence", Float), Column("vector", vector_type), Column("source_id", String), Column("created", String))
        self.documents = Table("knowledge_documents", meta, Column("id", String, primary_key=True), Column("user_id", String, index=True), Column("source", Text), Column("digest", String), Column("created", String))
        self.chunks = Table("knowledge_chunks", meta, Column("id", String, primary_key=True), Column("user_id", String, index=True), Column("document_id", String, index=True), Column("content", Text), Column("heading", Text), Column("position", Integer), Column("vector", vector_type))
        self.skills = Table("skill_invocations", meta, Column("id", String, primary_key=True), Column("user_id", String, index=True), Column("session_id", String), Column("kind", String), Column("status", String), Column("created", String))
        self.actions = Table("action_logs", meta, Column("id", String, primary_key=True), Column("user_id", String, index=True), Column("session_id", String), Column("name", String), Column("duration", Integer), Column("status", String), Column("created", String))
        meta.create_all(self.engine)
        with self.engine.begin() as connection:
            if not connection.execute(select(self.users.c.id).where(self.users.c.id == self.user)).first():
                connection.execute(insert(self.users).values(id=self.user, created=now()))

    def close(self) -> None:
        self.engine.dispose()

    def start_session(self) -> str:
        identity = uid()
        with self.engine.begin() as connection:
            connection.execute(insert(self.sessions).values(id=identity, user_id=self.user, created=now()))
        return identity

    def history(self, session: str, limit: int = 20) -> list[dict]:
        with self.engine.connect() as connection:
            rows = connection.execute(select(self.messages).where(self.messages.c.user_id == self.user, self.messages.c.session_id == session).order_by(self.messages.c.created.desc()).limit(limit)).mappings().all()
        return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

    def save_turn(self, session: str, question: str, answer: str) -> str:
        source = uid()
        with self.engine.begin() as connection:
            for identity, role, content in ((source, "user", question), (uid(), "assistant", answer)):
                connection.execute(insert(self.messages).values(id=identity, user_id=self.user, session_id=session, role=role, content=content, created=now()))
        return source

    def list_memories(self) -> list[dict]:
        with self.engine.connect() as connection:
            return [dict(row) for row in connection.execute(select(self.memories).where(self.memories.c.user_id == self.user).order_by(self.memories.c.created.desc())).mappings()]

    def remember(self, content: str, category: str = "preference", confidence: float = 1.0, source: str | None = None) -> str:
        content = content.strip()
        if not 1 <= len(content) <= 500 or not 0 <= confidence <= 1:
            raise ValueError("Memory requires 1–500 characters and confidence 0–1")
        with self.engine.begin() as connection:
            existing = connection.execute(select(self.memories.c.id).where(self.memories.c.user_id == self.user, self.memories.c.content == content)).scalar()
            if existing:
                return existing
            identity = uid()
            connection.execute(insert(self.memories).values(id=identity, user_id=self.user, content=content, category=category, confidence=confidence, source_id=source, created=now()))
        return identity

    def edit_memory(self, identity: str, content: str) -> None:
        if not 1 <= len(content.strip()) <= 500:
            raise ValueError("Memory requires 1–500 characters")
        with self.engine.begin() as connection:
            changed = connection.execute(update(self.memories).where(self.memories.c.id == identity, self.memories.c.user_id == self.user).values(content=content.strip(), vector=None, source_id=None))
            if changed.rowcount != 1:
                raise KeyError("Memory does not exist for this user")

    def forget(self, identity: str | None = None) -> None:
        """Hard-delete memory and its source turn; all means all personal history as well."""
        with self.engine.begin() as connection:
            condition = self.memories.c.user_id == self.user
            if identity:
                condition &= self.memories.c.id == identity
                row = connection.execute(select(self.memories.c.source_id).where(condition)).first()
                if row and row[0]:
                    connection.execute(delete(self.messages).where(self.messages.c.id == row[0], self.messages.c.user_id == self.user))
            else:
                for table in (self.messages, self.sessions, self.actions, self.skills):
                    connection.execute(delete(table).where(table.c.user_id == self.user))
            connection.execute(delete(self.memories).where(condition))

    def import_markdown(self, paths: list[Path]) -> int:
        imported = 0
        for path in paths:
            content = path.read_text(encoding="utf-8")
            if len(content) > 2_000_000:
                raise ValueError("Document exceeds 2 MB text limit")
            source, digest = str(path.resolve()), hashlib.sha256(content.encode()).hexdigest()
            chunks, heading = [], path.stem
            for section in re.split(r"(?m)(?=^#{1,6} )", content):
                lines = section.splitlines()
                if lines and lines[0].startswith("#"):
                    heading = lines[0].lstrip("# ")
                for offset in range(0, len(section), 900):
                    part = section[offset:offset+900].strip()
                    if part:
                        chunks.append((heading, part))
            with self.engine.begin() as connection:
                prior = connection.execute(select(self.documents).where(self.documents.c.user_id == self.user, self.documents.c.source == source)).mappings().first()
                if prior and prior["digest"] == digest:
                    continue
                if prior:
                    connection.execute(delete(self.chunks).where(self.chunks.c.document_id == prior["id"], self.chunks.c.user_id == self.user))
                    connection.execute(delete(self.documents).where(self.documents.c.id == prior["id"], self.documents.c.user_id == self.user))
                identity = uid()
                connection.execute(insert(self.documents).values(id=identity, user_id=self.user, source=source, digest=digest, created=now()))
                for index, (title, part) in enumerate(chunks):
                    connection.execute(insert(self.chunks).values(id=uid(), user_id=self.user, document_id=identity, heading=title, content=part, position=index))
            imported += 1
        return imported

    def index(self, embedder, limit: int = 100) -> int:
        count = 0
        for table in (self.memories, self.chunks):
            with self.engine.connect() as connection:
                rows = connection.execute(select(table).where(table.c.user_id == self.user, table.c.vector.is_(None)).limit(max(0, limit-count))).mappings().all()
            for row in rows:
                vector = embedder.embed(row["content"])
                if len(vector) != self.dimensions or any(not math.isfinite(v) for v in vector):
                    raise ValueError("Embedding dimensions/values do not match database schema")
                with self.engine.begin() as connection:
                    connection.execute(update(table).where(table.c.id == row["id"], table.c.content == row["content"], table.c.user_id == self.user).values(vector=vector))
                count += 1
        return count

    def search(self, query: str, vector: list[float] | None = None, limit: int = 6, include_memories: bool = True) -> list[dict]:
        query_terms, matches = terms(query), []
        tables = (self.memories, self.chunks) if include_memories else (self.chunks,)
        with self.engine.connect() as connection:
            for table in tables:
                rows = connection.execute(select(table).where(table.c.user_id == self.user)).mappings()
                for row in rows:
                    words = terms(row["content"])
                    keyword = len(query_terms & words) / max(1, len(query_terms))
                    similarity = max(0.0, cosine(vector, row["vector"])) if vector and row["vector"] else 0
                    score = keyword if not vector else 0.3 * keyword + 0.7 * similarity
                    if score > 0:
                        matches.append({"content": row["content"], "source": table.name, "id": row["id"], "score": score})
        return sorted(matches, key=lambda m: m["score"], reverse=True)[:limit]

    def record_actions(self, session: str, actions, status: str) -> None:
        with self.engine.begin() as connection:
            for action in actions:
                connection.execute(insert(self.actions).values(id=uid(), user_id=self.user, session_id=session, name=action.name, duration=action.duration, status=status, created=now()))

    def record_skill(self, session: str, kind: str, status: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(insert(self.skills).values(id=uid(), user_id=self.user, session_id=session, kind=kind, status=status, created=now()))
