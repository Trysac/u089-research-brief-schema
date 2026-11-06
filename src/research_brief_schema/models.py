"""Immutable data model of the contracts and their dictionary form."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final, Literal

from .errors import ContractError, FieldError

SCHEMA_VERSION: Final = "1.0"

SourceKind = Literal["web", "paper", "video", "dataset", "other"]
Cadence = Literal["daily", "weekly", "monthly"]


@dataclass(frozen=True)
class Finding:
    """A claim backed by at least one source id and a confidence in [0, 1]."""

    claim: str
    evidence: tuple[str, ...]
    confidence: float


@dataclass(frozen=True)
class Source:
    """A consulted source."""

    id: str
    url: str
    title: str
    retrieved_at: datetime
    kind: SourceKind


@dataclass(frozen=True)
class ResearchBrief:
    """A validated research brief.

    ``extras`` holds JSON-typed data kept next to the contract; treat it as read-only.
    """

    schema_version: str
    id: str
    topic_id: str
    created_at: datetime
    title: str
    summary: str
    findings: tuple[Finding, ...]
    sources: tuple[Source, ...]
    open_questions: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    extras: Mapping[str, Any] = field(default_factory=dict)

    @property
    def uncited_sources(self) -> tuple[str, ...]:
        """Ids of sources that no finding cites; a warning list, never an error."""
        cited = {ref for finding in self.findings for ref in finding.evidence}
        return tuple(source.id for source in self.sources if source.id not in cited)


@dataclass(frozen=True)
class Topic:
    """A monitored topic."""

    id: str
    name: str
    keywords: tuple[str, ...]
    exclude_keywords: tuple[str, ...]
    cadence: Cadence
    priority: int
    active: bool


@dataclass(frozen=True)
class TopicsFile:
    """A validated topics file."""

    schema_version: str
    topics: tuple[Topic, ...]


def _iso(value: datetime) -> str:
    text = value.isoformat()
    return text[:-6] + "Z" if text.endswith("+00:00") else text


def _finding_dict(finding: Finding) -> dict[str, Any]:
    return {
        "claim": finding.claim,
        "evidence": list(finding.evidence),
        "confidence": finding.confidence,
    }


def _source_dict(source: Source) -> dict[str, Any]:
    return {
        "id": source.id,
        "url": source.url,
        "title": source.title,
        "retrieved_at": _iso(source.retrieved_at),
        "kind": source.kind,
    }


def _topic_dict(topic: Topic) -> dict[str, Any]:
    return {
        "id": topic.id,
        "name": topic.name,
        "keywords": list(topic.keywords),
        "exclude_keywords": list(topic.exclude_keywords),
        "cadence": topic.cadence,
        "priority": topic.priority,
        "active": topic.active,
    }


def to_dict(obj: ResearchBrief | TopicsFile) -> dict[str, Any]:
    """Return the JSON-ready dictionary of a brief or topics file.

    Keys appear in declaration order and datetimes are RFC 3339 strings that use ``Z`` for UTC.
    The computed ``uncited_sources`` property is not part of the document.

    Raises:
        ContractError: if ``obj`` is neither a ``ResearchBrief`` nor a ``TopicsFile``.
    """
    if isinstance(obj, ResearchBrief):
        return {
            "schema_version": obj.schema_version,
            "id": obj.id,
            "topic_id": obj.topic_id,
            "created_at": _iso(obj.created_at),
            "title": obj.title,
            "summary": obj.summary,
            "findings": [_finding_dict(item) for item in obj.findings],
            "sources": [_source_dict(item) for item in obj.sources],
            "open_questions": list(obj.open_questions),
            "tags": list(obj.tags),
            "extras": copy.deepcopy(dict(obj.extras)),
        }
    if isinstance(obj, TopicsFile):
        return {
            "schema_version": obj.schema_version,
            "topics": [_topic_dict(item) for item in obj.topics],
        }
    raise ContractError((FieldError("", "type", "expected a ResearchBrief or a TopicsFile"),))
