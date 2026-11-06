"""JSON Schema (Draft 2020-12) export of the two contracts."""

from __future__ import annotations

from typing import Any, Literal

from . import limits
from .errors import ContractError, FieldError

_DRAFT = "https://json-schema.org/draft/2020-12/schema"
_VERSION_PATTERN = "^1[.](0|[1-9][0-9]{0,8})$"
_ID_PATTERN = "^[a-z0-9][a-z0-9-]{0,63}$"
_TAG_PATTERN = "^[a-z0-9]+(-[a-z0-9]+)*$"
_SOURCE_KINDS = ("web", "paper", "video", "dataset", "other")
_CADENCES = ("daily", "weekly", "monthly")

_BRIEF_DESCRIPTION = (
    "Research brief contract, version 1.x. Cross-field rules cannot be expressed in JSON "
    "Schema and are enforced only by research_brief_schema.validate_brief: source ids must "
    "be unique and every finding evidence entry must reference an existing source id."
)
_TOPICS_DESCRIPTION = (
    "Monitored topics contract, version 1.x. Cross-field rules cannot be expressed in JSON "
    "Schema and are enforced only by research_brief_schema.validate_topics: topic ids must "
    "be unique and keywords and exclude_keywords must be disjoint after case folding."
)


def _ref(name: str) -> dict[str, Any]:
    return {"$ref": f"#/$defs/{name}"}


def _string(low: int, high: int) -> dict[str, Any]:
    return {"type": "string", "minLength": low, "maxLength": high}


def _array(items: dict[str, Any], maximum: int, minimum: int = 0) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "array", "maxItems": maximum, "items": items}
    if minimum:
        schema["minItems"] = minimum
    return schema


def _object(required: list[str], properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


def _version() -> dict[str, Any]:
    return {"type": "string", "pattern": _VERSION_PATTERN}


def _id_def() -> dict[str, Any]:
    return {"type": "string", "pattern": _ID_PATTERN}


def _brief_schema() -> dict[str, Any]:
    finding = _object(
        ["claim", "evidence", "confidence"],
        {
            "claim": _string(1, limits.MAX_CLAIM),
            "evidence": _array(_ref("id"), limits.MAX_EVIDENCE, 1),
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
    )
    source = _object(
        ["id", "url", "title", "retrieved_at", "kind"],
        {
            "id": _ref("id"),
            "url": {"type": "string", "format": "uri", "maxLength": limits.MAX_URL_LENGTH},
            "title": _string(1, limits.MAX_SOURCE_TITLE),
            "retrieved_at": _ref("datetime"),
            "kind": {"type": "string", "enum": list(_SOURCE_KINDS)},
        },
    )
    tag = {**_string(1, limits.MAX_TAG_LENGTH), "pattern": _TAG_PATTERN}
    schema = _object(
        [
            "schema_version",
            "id",
            "topic_id",
            "created_at",
            "title",
            "summary",
            "findings",
            "sources",
        ],
        {
            "schema_version": _version(),
            "id": _ref("id"),
            "topic_id": _ref("id"),
            "created_at": _ref("datetime"),
            "title": _string(1, limits.MAX_TITLE),
            "summary": _string(1, limits.MAX_SUMMARY),
            "findings": _array(_ref("finding"), limits.MAX_FINDINGS),
            "sources": _array(_ref("source"), limits.MAX_SOURCES),
            "open_questions": _array(_string(1, limits.MAX_QUESTION), limits.MAX_OPEN_QUESTIONS),
            "tags": _array(tag, limits.MAX_TAGS),
            "extras": {"type": "object"},
        },
    )
    return {
        "$schema": _DRAFT,
        "title": "Research brief",
        "description": _BRIEF_DESCRIPTION,
        **schema,
        "$defs": {
            "id": _id_def(),
            "datetime": {"type": "string", "format": "date-time"},
            "finding": finding,
            "source": source,
        },
    }


def _topics_schema() -> dict[str, Any]:
    keyword = _string(1, limits.MAX_KEYWORD_LENGTH)
    topic = _object(
        ["id", "name", "keywords", "cadence", "priority", "active"],
        {
            "id": _ref("id"),
            "name": _string(1, limits.MAX_NAME),
            "keywords": _array(keyword, limits.MAX_KEYWORDS, 1),
            "exclude_keywords": _array(dict(keyword), limits.MAX_KEYWORDS),
            "cadence": {"type": "string", "enum": list(_CADENCES)},
            "priority": {"type": "integer", "minimum": 1, "maximum": 5},
            "active": {"type": "boolean"},
        },
    )
    schema = _object(
        ["schema_version", "topics"],
        {
            "schema_version": _version(),
            "topics": _array(_ref("topic"), limits.MAX_TOPICS, 1),
        },
    )
    return {
        "$schema": _DRAFT,
        "title": "Monitored topics",
        "description": _TOPICS_DESCRIPTION,
        **schema,
        "$defs": {"id": _id_def(), "topic": topic},
    }


def json_schema(kind: Literal["research-brief", "topics"]) -> dict[str, Any]:
    """Return the JSON Schema (Draft 2020-12) of a contract as a fresh dictionary.

    Cross-field rules (unique ids, evidence references, disjoint keywords) cannot be expressed
    in JSON Schema; the schema description says so and points to the validators.

    Raises:
        ContractError: if ``kind`` is not ``"research-brief"`` or ``"topics"``.
    """
    if kind == "research-brief":
        return _brief_schema()
    if kind == "topics":
        return _topics_schema()
    raise ContractError((FieldError("kind", "format", "must be 'research-brief' or 'topics'"),))
