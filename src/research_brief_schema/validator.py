"""Dependency-free validation of research briefs and topics files."""

from __future__ import annotations

import logging
import math
import re
import unicodedata
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any, Final, TypeVar
from urllib.parse import urlsplit

from . import limits
from .errors import ContractError, ErrorCode, FieldError
from .models import Finding, ResearchBrief, Source, Topic, TopicsFile

_LOG = logging.getLogger(__name__)
_T = TypeVar("_T")
_Handler = Callable[[str, Any], Any]

_ID_RE: Final = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
_TAG_RE: Final = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
_VERSION_RE: Final = re.compile(r"(0|[1-9][0-9]{0,8})[.](0|[1-9][0-9]{0,8})")
_DATETIME_RE: Final = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"([.][0-9]+)?([Zz]|[+-][0-9]{2}:[0-9]{2})"
)
_SOURCE_KINDS: Final = ("web", "paper", "video", "dataset", "other")
_CADENCES: Final = ("daily", "weekly", "monthly")
_BRIEF_OPTIONAL: Final = frozenset({"open_questions", "tags", "extras"})
_TOPIC_OPTIONAL: Final = frozenset({"exclude_keywords"})
_BAD: Final = object()


class _Stop(Exception):
    """Internal signal: the error list is final and validation must stop."""


class _Ctx:
    """Mutable state of a single validation run."""

    def __init__(self, strict: bool) -> None:
        self.strict = strict
        self.errors: list[FieldError] = []
        self.nodes = 0

    def add(self, path: str, code: ErrorCode, message: str) -> None:
        """Record a problem; past the error limit, add a marker and stop."""
        if len(self.errors) >= limits.MAX_ERRORS:
            note = "too many problems; further errors were omitted"
            self.errors.append(FieldError("", "too_many_errors", note))
            raise _Stop
        self.errors.append(FieldError(path, code, message))


def validate_brief(data: Mapping[str, Any], *, strict: bool = True) -> ResearchBrief:
    """Validate a research brief document and return it as a ``ResearchBrief``.

    All problems are collected (at most 100, then a ``too_many_errors`` marker) and raised
    together. With ``strict=False`` unknown top-level fields are kept in ``extras`` instead of
    being reported; unknown fields of nested objects are ignored.

    Raises:
        ContractError: if the document violates the contract.
    """
    return _run(_build_brief, data, strict)


def validate_topics(data: Mapping[str, Any], *, strict: bool = True) -> TopicsFile:
    """Validate a topics document and return it as a ``TopicsFile``.

    With ``strict=False`` unknown fields are ignored instead of being reported.

    Raises:
        ContractError: if the document violates the contract.
    """
    return _run(_build_topics, data, strict)


def _run(build: Callable[[_Ctx, Any], _T | None], data: Any, strict: bool) -> _T:
    ctx = _Ctx(strict)
    try:
        result = build(ctx, data)
    except _Stop:
        result = None
    if result is None or ctx.errors:
        _LOG.debug("validation failed with %d error(s)", len(ctx.errors))
        raise ContractError(tuple(ctx.errors))
    return result


def _join(path: str, key: str) -> str:
    clipped = key if len(key) <= limits.MAX_KEY_IN_PATH else key[: limits.MAX_KEY_IN_PATH] + "..."
    return f"{path}.{clipped}" if path else clipped


def _open_document(ctx: _Ctx, data: Any) -> Mapping[str, Any] | None:
    if not isinstance(data, Mapping):
        ctx.add("", "type", "document must be an object")
        return None
    if "schema_version" in data:
        problem = _version_problem(data["schema_version"])
        if problem is not None and problem[0] == "version":
            ctx.add("schema_version", problem[0], problem[1])
            raise _Stop
    return data


def _object(
    ctx: _Ctx,
    path: str,
    value: Any,
    handlers: Mapping[str, _Handler],
    optional: frozenset[str] | None = None,
    unknown: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bool]:
    """Run ``handlers`` over an object; return the valid values and an all-valid flag."""
    if not isinstance(value, Mapping):
        ctx.add(path, "type", "must be an object")
        return {}, False
    out: dict[str, Any] = {}
    ok = True
    for key, item in value.items():
        if not isinstance(key, str):
            ctx.add(path, "type", "object keys must be strings")
            ok = False
            continue
        sub = _join(path, key)
        handler = handlers.get(key)
        if handler is None:
            if ctx.strict:
                ctx.add(sub, "unknown_field", "unknown field")
                ok = False
            elif unknown is not None:
                copied = _json(ctx, sub, item, 2)
                if copied is _BAD:
                    ok = False
                else:
                    unknown[key] = copied
            continue
        result = handler(sub, item)
        if result is None:
            ok = False
        else:
            out[key] = result
    skipped = optional or frozenset()
    for name in handlers:
        if name not in value and name not in skipped:
            ctx.add(_join(path, name), "required", "field is required")
            ok = False
    return out, ok


def _array(
    ctx: _Ctx,
    path: str,
    value: Any,
    limit: int,
    item: _Handler,
    minimum: int = 0,
) -> tuple[Any, ...] | None:
    if not isinstance(value, list | tuple):
        ctx.add(path, "type", "must be an array")
        return None
    if len(value) > limit:
        ctx.add(path, "too_many", f"must contain at most {limit} items")
        return None
    if len(value) < minimum:
        ctx.add(path, "range", f"must contain at least {minimum} item(s)")
        return None
    out: list[Any] = []
    ok = True
    for index, element in enumerate(value):
        result = item(f"{path}[{index}]", element)
        if result is None:
            ok = False
        else:
            out.append(result)
    return tuple(out) if ok else None


def _json(ctx: _Ctx, path: str, value: Any, depth: int) -> Any:
    """Copy a JSON-typed value; return ``_BAD`` after recording the first problem."""
    ctx.nodes += 1
    if ctx.nodes > limits.MAX_EXTRAS_NODES:
        ctx.add(path, "too_many", f"extras may hold at most {limits.MAX_EXTRAS_NODES} values")
        return _BAD
    if value is None or isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        ctx.add(path, "range", "numbers must be finite")
        return _BAD
    if isinstance(value, str):
        if len(value) <= limits.MAX_EXTRAS_STRING:
            return value
        ctx.add(path, "range", f"strings may have at most {limits.MAX_EXTRAS_STRING} characters")
        return _BAD
    if isinstance(value, list | dict):
        if depth > limits.MAX_EXTRAS_DEPTH:
            ctx.add(path, "too_deep", f"nesting exceeds {limits.MAX_EXTRAS_DEPTH} levels")
            return _BAD
        if isinstance(value, list):
            items: list[Any] = []
            for index, element in enumerate(value):
                copied = _json(ctx, f"{path}[{index}]", element, depth + 1)
                if copied is _BAD:
                    return _BAD
                items.append(copied)
            return items
        members: dict[str, Any] = {}
        for key, element in value.items():
            if not isinstance(key, str):
                ctx.add(path, "type", "object keys must be strings")
                return _BAD
            copied = _json(ctx, _join(path, key), element, depth + 1)
            if copied is _BAD:
                return _BAD
            members[key] = copied
        return members
    ctx.add(path, "type", "value is not a JSON type")
    return _BAD


def _text(ctx: _Ctx, path: str, value: Any, low: int, high: int) -> str | None:
    if not isinstance(value, str):
        ctx.add(path, "type", "must be a string")
        return None
    if not low <= len(value) <= high:
        ctx.add(path, "range", f"length must be between {low} and {high} characters")
        return None
    return value


def _ident(ctx: _Ctx, path: str, value: Any) -> str | None:
    if not isinstance(value, str):
        ctx.add(path, "type", "must be a string")
        return None
    if _ID_RE.fullmatch(value) is None:
        ctx.add(path, "format", "must match ^[a-z0-9][a-z0-9-]{0,63}$")
        return None
    return value


def _unique_ident(ctx: _Ctx, seen: set[str]) -> _Handler:
    def handler(path: str, value: Any) -> str | None:
        ident = _ident(ctx, path, value)
        if ident is None:
            return None
        if ident in seen:
            ctx.add(path, "duplicate", "id is already used by an earlier entry")
            return None
        seen.add(ident)
        return ident

    return handler


def _version_problem(value: Any) -> tuple[ErrorCode, str] | None:
    if not isinstance(value, str):
        return ("type", "must be a string")
    match = _VERSION_RE.fullmatch(value)
    if match is None:
        return ("format", "must look like MAJOR.MINOR, for example 1.0")
    if int(match.group(1)) != 1:
        return ("version", f"unsupported major version {match.group(1)}; supported: 1")
    return None


def _version(ctx: _Ctx, path: str, value: Any) -> str | None:
    problem = _version_problem(value)
    if problem is not None:
        ctx.add(path, problem[0], problem[1])
        return None
    return str(value)


def _parse_datetime(text: str) -> datetime | None:
    """Parse an RFC 3339 section 5.6 date-time into an aware datetime."""
    if len(text) > limits.MAX_DATETIME_LENGTH:
        return None
    match = _DATETIME_RE.fullmatch(text)
    if match is None:
        return None
    fraction = match.group(1)
    zone = match.group(2)
    micro = "" if fraction is None else "." + fraction[1:7].ljust(6, "0")
    offset = "+00:00" if zone in ("Z", "z") else zone
    iso = f"{text[:10]}T{text[11:19]}{micro}{offset}"
    try:
        return datetime.fromisoformat(iso)
    except ValueError:
        return None


def _datetime(ctx: _Ctx, path: str, value: Any) -> datetime | None:
    if not isinstance(value, str):
        ctx.add(path, "type", "must be a string")
        return None
    parsed = _parse_datetime(value)
    if parsed is None:
        message = "must be an RFC 3339 date-time such as 2026-11-05T10:00:00Z"
        ctx.add(path, "format", message)
        return None
    return parsed


def _url_is_valid(text: str) -> bool:
    if not text or len(text) > limits.MAX_URL_LENGTH:
        return False
    if any(char.isspace() or unicodedata.category(char) == "Cc" for char in text):
        return False
    try:
        parts = urlsplit(text)
        _ = parts.port
    except ValueError:
        return False
    if parts.scheme not in ("http", "https") or "@" in parts.netloc:
        return False
    return bool(parts.hostname)


def _url(ctx: _Ctx, path: str, value: Any) -> str | None:
    if not isinstance(value, str):
        ctx.add(path, "type", "must be a string")
        return None
    if not _url_is_valid(value):
        ctx.add(path, "format", "must be a plain http(s) URL of at most 2048 characters")
        return None
    return value


def _choice(ctx: _Ctx, path: str, value: Any, allowed: tuple[str, ...]) -> str | None:
    if not isinstance(value, str):
        ctx.add(path, "type", "must be a string")
        return None
    if value not in allowed:
        ctx.add(path, "format", "must be one of: " + ", ".join(allowed))
        return None
    return value


def _confidence(ctx: _Ctx, path: str, value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        ctx.add(path, "type", "must be a number")
        return None
    if not 0 <= value <= 1:
        ctx.add(path, "range", "must be a finite number between 0 and 1")
        return None
    return float(value)


def _priority(ctx: _Ctx, path: str, value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        ctx.add(path, "type", "must be an integer")
        return None
    if not 1 <= value <= 5:
        ctx.add(path, "range", "must be between 1 and 5")
        return None
    return value


def _boolean(ctx: _Ctx, path: str, value: Any) -> bool | None:
    if not isinstance(value, bool):
        ctx.add(path, "type", "must be a boolean")
        return None
    return value


def _tag(ctx: _Ctx, path: str, value: Any) -> str | None:
    if not isinstance(value, str):
        ctx.add(path, "type", "must be a string")
        return None
    if len(value) > limits.MAX_TAG_LENGTH or _TAG_RE.fullmatch(value) is None:
        ctx.add(path, "format", "must be lowercase kebab-case of at most 64 characters")
        return None
    return value


def _tags(ctx: _Ctx, path: str, value: Any) -> tuple[str, ...] | None:
    items = _array(ctx, path, value, limits.MAX_TAGS, lambda p, v: _tag(ctx, p, v))
    return None if items is None else tuple(dict.fromkeys(items))


def _open_questions(ctx: _Ctx, path: str, value: Any) -> tuple[str, ...] | None:
    return _array(
        ctx,
        path,
        value,
        limits.MAX_OPEN_QUESTIONS,
        lambda p, v: _text(ctx, p, v, 1, limits.MAX_QUESTION),
    )


def _extras(ctx: _Ctx, path: str, value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        ctx.add(path, "type", "must be an object")
        return None
    result = _json(ctx, path, value, 1)
    if result is _BAD:
        return None
    copied: dict[str, Any] = result
    return copied


class _AnyId(frozenset[str]):
    """Matches every id; used when the sources list is rejected as too long."""

    def __contains__(self, item: object) -> bool:
        return True


def _source_ids(value: Any) -> frozenset[str]:
    """Collect source ids from raw data so findings can be checked in document order."""
    if not isinstance(value, list | tuple):
        return frozenset()
    if len(value) > limits.MAX_SOURCES:
        return _AnyId()
    ids: set[str] = set()
    for item in value:
        if isinstance(item, Mapping) and isinstance(item.get("id"), str):
            ids.add(item["id"])
    return frozenset(ids)


def _evidence(ctx: _Ctx, path: str, value: Any, known: frozenset[str]) -> tuple[str, ...] | None:
    def reference(item_path: str, item: Any) -> str | None:
        if not isinstance(item, str):
            ctx.add(item_path, "type", "must be a string")
            return None
        if item not in known:
            ctx.add(item_path, "reference", "does not reference an existing source id")
            return None
        return item

    return _array(ctx, path, value, limits.MAX_EVIDENCE, reference, 1)


def _findings(
    ctx: _Ctx, path: str, value: Any, known: frozenset[str]
) -> tuple[Finding, ...] | None:
    handlers: dict[str, _Handler] = {
        "claim": lambda p, v: _text(ctx, p, v, 1, limits.MAX_CLAIM),
        "evidence": lambda p, v: _evidence(ctx, p, v, known),
        "confidence": lambda p, v: _confidence(ctx, p, v),
    }

    def finding(item_path: str, item: Any) -> Finding | None:
        out, ok = _object(ctx, item_path, item, handlers)
        return Finding(**out) if ok else None

    return _array(ctx, path, value, limits.MAX_FINDINGS, finding)


def _sources(ctx: _Ctx, path: str, value: Any) -> tuple[Source, ...] | None:
    handlers: dict[str, _Handler] = {
        "id": _unique_ident(ctx, set()),
        "url": lambda p, v: _url(ctx, p, v),
        "title": lambda p, v: _text(ctx, p, v, 1, limits.MAX_SOURCE_TITLE),
        "retrieved_at": lambda p, v: _datetime(ctx, p, v),
        "kind": lambda p, v: _choice(ctx, p, v, _SOURCE_KINDS),
    }

    def source(item_path: str, item: Any) -> Source | None:
        out, ok = _object(ctx, item_path, item, handlers)
        return Source(**out) if ok else None

    return _array(ctx, path, value, limits.MAX_SOURCES, source)


def _build_brief(ctx: _Ctx, data: Any) -> ResearchBrief | None:
    document = _open_document(ctx, data)
    if document is None:
        return None
    known = _source_ids(document.get("sources"))
    handlers: dict[str, _Handler] = {
        "schema_version": lambda p, v: _version(ctx, p, v),
        "id": lambda p, v: _ident(ctx, p, v),
        "topic_id": lambda p, v: _ident(ctx, p, v),
        "created_at": lambda p, v: _datetime(ctx, p, v),
        "title": lambda p, v: _text(ctx, p, v, 1, limits.MAX_TITLE),
        "summary": lambda p, v: _text(ctx, p, v, 1, limits.MAX_SUMMARY),
        "findings": lambda p, v: _findings(ctx, p, v, known),
        "sources": lambda p, v: _sources(ctx, p, v),
        "open_questions": lambda p, v: _open_questions(ctx, p, v),
        "tags": lambda p, v: _tags(ctx, p, v),
        "extras": lambda p, v: _extras(ctx, p, v),
    }
    unknown: dict[str, Any] = {}
    out, ok = _object(ctx, "", document, handlers, _BRIEF_OPTIONAL, unknown)
    if not ok:
        return None
    fields: dict[str, Any] = {"open_questions": (), "tags": (), **out}
    fields["extras"] = {**out.get("extras", {}), **unknown}
    return ResearchBrief(**fields)


def _keywords(ctx: _Ctx, path: str, value: Any, minimum: int) -> tuple[str, ...] | None:
    return _array(
        ctx,
        path,
        value,
        limits.MAX_KEYWORDS,
        lambda p, v: _text(ctx, p, v, 1, limits.MAX_KEYWORD_LENGTH),
        minimum,
    )


def _topic_item(ctx: _Ctx) -> _Handler:
    handlers: dict[str, _Handler] = {
        "id": _unique_ident(ctx, set()),
        "name": lambda p, v: _text(ctx, p, v, 1, limits.MAX_NAME),
        "keywords": lambda p, v: _keywords(ctx, p, v, 1),
        "exclude_keywords": lambda p, v: _keywords(ctx, p, v, 0),
        "cadence": lambda p, v: _choice(ctx, p, v, _CADENCES),
        "priority": lambda p, v: _priority(ctx, p, v),
        "active": lambda p, v: _boolean(ctx, p, v),
    }

    def topic(path: str, value: Any) -> Topic | None:
        out, ok = _object(ctx, path, value, handlers, _TOPIC_OPTIONAL)
        include = out.get("keywords")
        exclude = out.get("exclude_keywords")
        if include is not None and exclude is not None:
            folded = {word.casefold() for word in include}
            for index, word in enumerate(exclude):
                if word.casefold() in folded:
                    where = f"{path}.exclude_keywords[{index}]"
                    ctx.add(where, "duplicate", "keyword is also listed in keywords")
                    ok = False
        if not ok:
            return None
        fields: dict[str, Any] = {"exclude_keywords": (), **out}
        return Topic(**fields)

    return topic


def _build_topics(ctx: _Ctx, data: Any) -> TopicsFile | None:
    document = _open_document(ctx, data)
    if document is None:
        return None
    item = _topic_item(ctx)
    handlers: dict[str, _Handler] = {
        "schema_version": lambda p, v: _version(ctx, p, v),
        "topics": lambda p, v: _array(ctx, p, v, limits.MAX_TOPICS, item, 1),
    }
    out, ok = _object(ctx, "", document, handlers)
    if not ok:
        return None
    return TopicsFile(**out)
