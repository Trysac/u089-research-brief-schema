"""Tests for the research brief and topics contracts."""

from __future__ import annotations

import dataclasses
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from research_brief_schema import (
    SCHEMA_VERSION,
    ContractError,
    FieldError,
    ResearchBrief,
    TopicsFile,
    json_schema,
    to_dict,
    validate_brief,
    validate_topics,
)

GOLDEN = Path(__file__).parent / "golden"
UTC = timezone.utc


def _load(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((GOLDEN / name).read_text(encoding="utf-8"))
    return loaded


def _brief_doc() -> dict[str, Any]:
    return _load("research_brief.json")


def _topics_doc() -> dict[str, Any]:
    return _load("topics.json")


def _problems(doc: Any, *, strict: bool = True) -> list[tuple[str, str]]:
    with pytest.raises(ContractError) as info:
        validate_brief(doc, strict=strict)
    return [(error.path, error.code) for error in info.value.errors]


def _topic_problems(doc: Any, *, strict: bool = True) -> list[tuple[str, str]]:
    with pytest.raises(ContractError) as info:
        validate_topics(doc, strict=strict)
    return [(error.path, error.code) for error in info.value.errors]


def _nested_dicts(levels: int) -> dict[str, Any]:
    value: dict[str, Any] = {"leaf": 1}
    for _ in range(levels - 1):
        value = {"k": value}
    return value


def _nested_lists(levels: int) -> Any:
    value: Any = 1
    for _ in range(levels):
        value = [value]
    return value


def _bad_findings(count: int) -> list[dict[str, Any]]:
    return [{"claim": "c", "evidence": ["src-1"], "confidence": 2} for _ in range(count)]


def test_schema_version_constant() -> None:
    assert SCHEMA_VERSION == "1.0"
    assert validate_brief(_brief_doc()).schema_version == SCHEMA_VERSION


def test_golden_brief_round_trips() -> None:
    doc = _brief_doc()
    brief = validate_brief(doc)
    assert isinstance(brief, ResearchBrief)
    assert to_dict(brief) == doc
    assert list(to_dict(brief)) == list(doc)
    assert brief.created_at == datetime(2026, 11, 5, 10, 0, tzinfo=UTC)
    assert brief.findings[1].confidence == 1.0
    assert isinstance(brief.findings[1].confidence, float)
    assert brief.uncited_sources == ()
    assert doc == _brief_doc()


def test_golden_topics_round_trips() -> None:
    doc = _topics_doc()
    topics = validate_topics(doc)
    assert isinstance(topics, TopicsFile)
    assert to_dict(topics) == doc
    assert topics.topics[1].exclude_keywords == ()
    assert topics.topics[0].active is True


def test_key_order_follows_declaration() -> None:
    result = to_dict(validate_brief(_brief_doc()))
    assert list(result["findings"][0]) == ["claim", "evidence", "confidence"]
    assert list(result["sources"][0]) == ["id", "url", "title", "retrieved_at", "kind"]
    topic = to_dict(validate_topics(_topics_doc()))["topics"][0]
    assert list(topic) == [
        "id",
        "name",
        "keywords",
        "exclude_keywords",
        "cadence",
        "priority",
        "active",
    ]


def test_models_are_frozen() -> None:
    brief = validate_brief(_brief_doc())
    with pytest.raises(dataclasses.FrozenInstanceError):
        brief.title = "other"
    with pytest.raises(dataclasses.FrozenInstanceError):
        brief.findings[0].claim = "other"


def test_optional_collections_default_to_empty() -> None:
    doc = _brief_doc()
    for name in ("open_questions", "tags", "extras"):
        del doc[name]
    brief = validate_brief(doc)
    assert brief.open_questions == ()
    assert brief.tags == ()
    assert dict(brief.extras) == {}
    result = to_dict(brief)
    assert result["tags"] == []
    assert result["extras"] == {}


def test_validation_does_not_alias_input_or_output() -> None:
    doc = _brief_doc()
    brief = validate_brief(doc)
    doc["extras"]["scores"].append(9)
    assert brief.extras["scores"] == [1, 2.5, None, True]
    exported = to_dict(brief)
    exported["extras"]["scores"].append(7)
    assert brief.extras["scores"] == [1, 2.5, None, True]


def test_accepts_other_mappings_and_sequences() -> None:
    doc = _brief_doc()
    doc["findings"] = tuple(doc["findings"])
    brief = validate_brief(MappingProxyType(doc))
    assert len(brief.findings) == 2


def test_uncited_sources_are_a_warning_not_an_error() -> None:
    doc = _brief_doc()
    doc["sources"].append(
        {
            "id": "src-3",
            "url": "https://example.net/c",
            "title": "Unused",
            "retrieved_at": "2026-11-04T10:00:00Z",
            "kind": "other",
        }
    )
    assert validate_brief(doc).uncited_sources == ("src-3",)
    doc["findings"] = []
    assert validate_brief(doc).uncited_sources == ("src-1", "src-2", "src-3")
    assert "uncited_sources" not in to_dict(validate_brief(doc))


def test_unknown_evidence_reference() -> None:
    doc = _brief_doc()
    doc["findings"][1]["evidence"][0] = "src-9"
    with pytest.raises(ContractError) as info:
        validate_brief(doc)
    assert len(info.value.errors) == 1
    error = info.value.errors[0]
    assert error.path == "findings[1].evidence[0]"
    assert error.code == "reference"
    assert error == FieldError(
        path="findings[1].evidence[0]", code="reference", message=error.message
    )


def test_three_independent_problems_give_three_errors() -> None:
    doc = _brief_doc()
    doc["title"] = ""
    doc["findings"][0]["confidence"] = 1.5
    doc["sources"][0]["url"] = "ftp://x"
    assert _problems(doc) == [
        ("title", "range"),
        ("findings[0].confidence", "range"),
        ("sources[0].url", "format"),
    ]


def test_errors_follow_document_order() -> None:
    doc = _brief_doc()
    doc["title"] = ""
    doc["sources"][0]["url"] = "ftp://x"
    reordered = dict(reversed(list(doc.items())))
    assert _problems(reordered) == [("sources[0].url", "format"), ("title", "range")]


def test_missing_required_fields_are_reported_in_declared_order() -> None:
    doc = _brief_doc()
    del doc["summary"]
    del doc["title"]
    assert _problems(doc) == [("title", "required"), ("summary", "required")]


def test_150_problems_give_101_errors() -> None:
    doc = _brief_doc()
    doc["findings"] = _bad_findings(150)
    with pytest.raises(ContractError) as info:
        validate_brief(doc)
    errors = info.value.errors
    assert len(errors) == 101
    assert errors[-1].path == ""
    assert errors[-1].code == "too_many_errors"
    assert [e.path for e in errors[:100]] == [f"findings[{i}].confidence" for i in range(100)]
    assert info.value.code == "invalid"


def test_exactly_100_problems_give_no_marker() -> None:
    doc = _brief_doc()
    doc["findings"] = _bad_findings(100)
    problems = _problems(doc)
    assert len(problems) == 100
    assert {code for _, code in problems} == {"range"}


@pytest.mark.parametrize(
    "value", [1.5, -0.1, float("nan"), float("inf"), -float("inf"), 2, 10**400]
)
def test_confidence_out_of_range(value: Any) -> None:
    doc = _brief_doc()
    doc["findings"][0]["confidence"] = value
    assert _problems(doc) == [("findings[0].confidence", "range")]


@pytest.mark.parametrize("value", [True, False, "0.5", None, [0.5]])
def test_confidence_wrong_type(value: Any) -> None:
    doc = _brief_doc()
    doc["findings"][0]["confidence"] = value
    assert _problems(doc) == [("findings[0].confidence", "type")]


@pytest.mark.parametrize("value", [0, 1, 0.0, 1.0, 0.25])
def test_confidence_boundaries_are_accepted(value: Any) -> None:
    doc = _brief_doc()
    doc["findings"][0]["confidence"] = value
    confidence = validate_brief(doc).findings[0].confidence
    assert confidence == value
    assert isinstance(confidence, float)


def test_true_for_priority_gives_type() -> None:
    doc = _topics_doc()
    doc["topics"][0]["priority"] = True
    assert _topic_problems(doc) == [("topics[0].priority", "type")]
    doc["topics"][0]["priority"] = False
    assert _topic_problems(doc) == [("topics[0].priority", "type")]


@pytest.mark.parametrize(
    ("value", "code"), [(2.0, "type"), ("3", "type"), (0, "range"), (6, "range")]
)
def test_priority_problems(value: Any, code: str) -> None:
    doc = _topics_doc()
    doc["topics"][0]["priority"] = value
    assert _topic_problems(doc) == [("topics[0].priority", code)]


@pytest.mark.parametrize("value", [1, 5])
def test_priority_boundaries_are_accepted(value: int) -> None:
    doc = _topics_doc()
    doc["topics"][0]["priority"] = value
    assert validate_topics(doc).topics[0].priority == value


BAD_DATETIMES = [
    "2026-11-05T10:00:00",
    "2026-11-05 10:00:00Z",
    "20261105T100000Z",
    "2026-11-05T10:00:00Z\n",
    "2026-13-05T10:00:00Z",
    "2026-11-05T24:00:00Z",
    "2026-11-05T10:00:00+99:99",
    "2026-11-05T10:00:00.Z",
    "2026-11-05T10:00:00 Z",
    "2026-11-05T10:00:00+0100",
    "2026-11-05",
    "",
    "9" * 100,
    "".join(chr(0xFF10 + int(digit)) for digit in "2026") + "-11-05T10:00:00Z",
]


@pytest.mark.parametrize("value", BAD_DATETIMES)
def test_bad_datetimes_give_format(value: str) -> None:
    doc = _brief_doc()
    doc["created_at"] = value
    assert _problems(doc) == [("created_at", "format")]


def test_bad_source_datetime_path_and_non_string_type() -> None:
    doc = _brief_doc()
    doc["sources"][0]["retrieved_at"] = "2026-11-05 10:00:00Z"
    assert _problems(doc) == [("sources[0].retrieved_at", "format")]
    doc["sources"][0]["retrieved_at"] = 20261105
    assert _problems(doc) == [("sources[0].retrieved_at", "type")]


def test_lowercase_rfc3339_datetime_is_accepted() -> None:
    doc = _brief_doc()
    doc["created_at"] = "2026-11-05t10:00:00.5z"
    brief = validate_brief(doc)
    assert brief.created_at == datetime(2026, 11, 5, 10, 0, 0, 500000, tzinfo=UTC)
    assert to_dict(brief)["created_at"] == "2026-11-05T10:00:00.500000Z"


@pytest.mark.parametrize(
    ("text", "micro"),
    [
        ("2026-11-05T10:00:00z", 0),
        ("2026-11-05T10:00:00.1234567891Z", 123456),
        ("2026-11-05T10:00:00.12Z", 120000),
    ],
)
def test_fraction_is_padded_or_cut_to_microseconds(text: str, micro: int) -> None:
    doc = _brief_doc()
    doc["created_at"] = text
    assert validate_brief(doc).created_at.microsecond == micro


def test_offsets_are_kept_and_utc_is_rendered_as_z() -> None:
    doc = _brief_doc()
    doc["created_at"] = "2026-11-05T10:00:00+01:00"
    brief = validate_brief(doc)
    assert brief.created_at.utcoffset() == timedelta(hours=1)
    assert to_dict(brief)["created_at"] == "2026-11-05T10:00:00+01:00"
    doc["created_at"] = "2026-11-05T10:00:00+00:00"
    assert to_dict(validate_brief(doc))["created_at"] == "2026-11-05T10:00:00Z"
    doc["created_at"] = "2026-11-05T10:00:00-05:30"
    assert validate_brief(doc).created_at.utcoffset() == -timedelta(hours=5, minutes=30)


BAD_URLS = [
    "ftp://x",
    "https://user:pass@host",
    "https://user@host",
    "https://exa mple.com",
    "https://",
    "https:///path",
    "http://host:99999",
    "https://host\n",
    "https://exa\tmple.com",
    "javascript:alert(1)",
    "//example.com",
    "example.com",
    "",
    "https://[::1",
    "https://" + "a" * 2050,
]


@pytest.mark.parametrize("value", BAD_URLS)
def test_bad_urls_give_format(value: str) -> None:
    doc = _brief_doc()
    doc["sources"][0]["url"] = value
    with pytest.raises(ContractError) as info:
        validate_brief(doc)
    assert [(e.path, e.code) for e in info.value.errors] == [("sources[0].url", "format")]
    message = info.value.errors[0].message
    assert "pass" not in message
    assert "user" not in message


@pytest.mark.parametrize(
    "value",
    [
        "HTTPS://example.com/a",
        "https://[::1]/",
        "http://localhost:8080/x?y=1#z",
        "https://example.com/a@b",
    ],
)
def test_good_urls_are_accepted(value: str) -> None:
    doc = _brief_doc()
    doc["sources"][0]["url"] = value
    assert validate_brief(doc).sources[0].url == value


def test_url_must_be_a_string() -> None:
    doc = _brief_doc()
    doc["sources"][0]["url"] = 5
    assert _problems(doc) == [("sources[0].url", "type")]


BAD_IDS = ["", "Abc", "a b", "-abc", "a" * 65, "abc\n", "ab_c", chr(233)]


@pytest.mark.parametrize("value", BAD_IDS)
def test_bad_ids_give_format(value: str) -> None:
    doc = _brief_doc()
    doc["id"] = value
    doc["topic_id"] = value
    assert _problems(doc) == [("id", "format"), ("topic_id", "format")]
    topics = _topics_doc()
    topics["topics"][0]["id"] = value
    assert _topic_problems(topics) == [("topics[0].id", "format")]


@pytest.mark.parametrize("value", ["a", "0", "a-", "a" * 64, "a0-b1"])
def test_good_ids_are_accepted(value: str) -> None:
    doc = _brief_doc()
    doc["id"] = value
    assert validate_brief(doc).id == value


def test_id_must_be_a_string() -> None:
    doc = _brief_doc()
    doc["id"] = 7
    assert _problems(doc) == [("id", "type")]


def test_unknown_field_strict_and_lenient() -> None:
    doc = _brief_doc()
    doc["bogus"] = {"a": 1}
    assert _problems(doc) == [("bogus", "unknown_field")]
    brief = validate_brief(doc, strict=False)
    assert brief.extras == {
        "reviewer": "agent-1",
        "scores": [1, 2.5, None, True],
        "bogus": {"a": 1},
    }
    assert "bogus" in to_dict(brief)["extras"]


def test_unknown_nested_fields() -> None:
    doc = _brief_doc()
    doc["sources"][0]["x"] = 1
    doc["findings"][0]["y"] = 2
    assert _problems(doc) == [("findings[0].y", "unknown_field"), ("sources[0].x", "unknown_field")]
    assert len(validate_brief(doc, strict=False).sources) == 2
    topics = _topics_doc()
    topics["color"] = "red"
    topics["topics"][0]["color"] = "red"
    assert _topic_problems(topics) == [
        ("topics[0].color", "unknown_field"),
        ("color", "unknown_field"),
    ]
    assert len(validate_topics(topics, strict=False).topics) == 2


def test_unknown_field_values_are_checked_when_lenient() -> None:
    doc = _brief_doc()
    doc["bogus"] = {1, 2}
    assert _problems(doc, strict=False) == [("bogus", "type")]
    doc["bogus"] = _nested_lists(10)
    assert [c for _, c in _problems(doc, strict=False)] == ["too_deep"]
    doc["bogus"] = _nested_lists(9)
    assert validate_brief(doc, strict=False).extras["bogus"] == _nested_lists(9)


def test_long_unknown_keys_are_clipped_in_paths() -> None:
    doc = _brief_doc()
    doc["k" * 5000] = 1
    problems = _problems(doc)
    assert len(problems) == 1
    assert len(problems[0][0]) <= 70
    assert problems[0][1] == "unknown_field"


def test_extras_depth_limit() -> None:
    doc = _brief_doc()
    doc["extras"] = _nested_dicts(10)
    assert validate_brief(doc).extras == _nested_dicts(10)
    doc["extras"] = _nested_dicts(11)
    problems = _problems(doc)
    assert [code for _, code in problems] == ["too_deep"]
    assert problems[0][0].startswith("extras")
    doc["extras"] = {"a": _nested_lists(9)}
    assert validate_brief(doc).extras == {"a": _nested_lists(9)}
    doc["extras"] = {"a": _nested_lists(10)}
    assert [code for _, code in _problems(doc)] == ["too_deep"]


def test_extras_accepts_only_json_types() -> None:
    doc = _brief_doc()
    doc["extras"] = {"x": object()}
    assert _problems(doc) == [("extras.x", "type")]
    doc["extras"] = {"x": (1, 2)}
    assert _problems(doc) == [("extras.x", "type")]
    doc["extras"] = {"x": float("nan")}
    assert _problems(doc) == [("extras.x", "range")]
    doc["extras"] = {"x": float("inf")}
    assert _problems(doc) == [("extras.x", "range")]
    doc["extras"] = {1: "a"}
    assert _problems(doc) == [("extras", "type")]
    doc["extras"] = {"x": [{1: "a"}]}
    assert _problems(doc) == [("extras.x[0]", "type")]
    doc["extras"] = []
    assert _problems(doc) == [("extras", "type")]
    doc["extras"] = {"a": [1, "s", 2.5, False, None, {"b": []}]}
    assert validate_brief(doc).extras == doc["extras"]


def test_extras_size_limits() -> None:
    doc = _brief_doc()
    doc["extras"] = {"x": "a" * 10_000}
    assert len(validate_brief(doc).extras["x"]) == 10_000
    doc["extras"] = {"x": "a" * 10_001}
    assert _problems(doc) == [("extras.x", "range")]
    doc["extras"] = {"x": [0] * 9000}
    assert len(validate_brief(doc).extras["x"]) == 9000
    doc["extras"] = {"x": [0] * 10_000}
    assert [code for _, code in _problems(doc)] == ["too_many"]


@pytest.mark.parametrize("value", ["2.0", "0.9", "10.1"])
def test_unsupported_major_version(value: str) -> None:
    doc = _brief_doc()
    doc["schema_version"] = value
    assert _problems(doc) == [("schema_version", "version")]
    doc["title"] = ""
    assert _problems(doc) == [("schema_version", "version")]
    topics = _topics_doc()
    topics["schema_version"] = value
    assert _topic_problems(topics) == [("schema_version", "version")]


def test_any_minor_version_is_accepted() -> None:
    doc = _brief_doc()
    doc["schema_version"] = "1.3"
    assert validate_brief(doc).schema_version == "1.3"
    assert to_dict(validate_brief(doc))["schema_version"] == "1.3"
    topics = _topics_doc()
    topics["schema_version"] = "1.12"
    assert validate_topics(topics).schema_version == "1.12"


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ("1", "format"),
        ("1.x", "format"),
        ("v1.0", "format"),
        ("1.0\n", "format"),
        ("01.0", "format"),
        (1.0, "type"),
        (None, "type"),
    ],
)
def test_malformed_versions(value: Any, code: str) -> None:
    doc = _brief_doc()
    doc["schema_version"] = value
    assert _problems(doc) == [("schema_version", code)]


def test_collection_limits() -> None:
    doc = _brief_doc()
    doc["findings"] = [doc["findings"][0]] * 1001
    assert _problems(doc) == [("findings", "too_many")]
    doc["findings"] = [doc["findings"][0]] * 1000
    assert len(validate_brief(doc).findings) == 1000
    doc = _brief_doc()
    doc["sources"] = [doc["sources"][0]] * 1001
    assert _problems(doc) == [("sources", "too_many")]
    doc = _brief_doc()
    doc["open_questions"] = ["q"] * 101
    assert _problems(doc) == [("open_questions", "too_many")]
    doc = _brief_doc()
    doc["tags"] = [f"t{i}" for i in range(101)]
    assert _problems(doc) == [("tags", "too_many")]
    doc = _brief_doc()
    doc["findings"][0]["evidence"] = ["src-1"] * 1001
    assert _problems(doc) == [("findings[0].evidence", "too_many")]
    topics = _topics_doc()
    topics["topics"] = [topics["topics"][0]] * 501
    assert _topic_problems(topics) == [("topics", "too_many")]
    topics = _topics_doc()
    topics["topics"][0]["keywords"] = ["k"] * 101
    assert _topic_problems(topics) == [("topics[0].keywords", "too_many")]


def test_wrong_container_types() -> None:
    doc = _brief_doc()
    doc["findings"] = "nope"
    doc["sources"] = {}
    assert _problems(doc) == [("findings", "type"), ("sources", "type")]
    doc = _brief_doc()
    doc["findings"] = [1]
    assert _problems(doc) == [("findings[0]", "type")]
    doc = _brief_doc()
    doc["findings"][0]["evidence"] = "src-1"
    assert _problems(doc) == [("findings[0].evidence", "type")]


@pytest.mark.parametrize("value", [[], "text", 5, None])
def test_document_must_be_an_object(value: Any) -> None:
    assert _problems(value) == [("", "type")]
    assert _topic_problems(value) == [("", "type")]


def test_object_keys_must_be_strings() -> None:
    doc = _brief_doc()
    doc[1] = "x"
    assert ("", "type") in _problems(doc)


def test_string_length_limits() -> None:
    doc = _brief_doc()
    doc["title"] = "t" * 200
    doc["summary"] = "s" * 2000
    validate_brief(doc)
    doc["title"] = "t" * 201
    doc["summary"] = "s" * 2001
    assert _problems(doc) == [("title", "range"), ("summary", "range")]
    doc = _brief_doc()
    doc["title"] = 5
    assert _problems(doc) == [("title", "type")]
    doc = _brief_doc()
    doc["findings"][0]["claim"] = ""
    doc["sources"][0]["title"] = ""
    doc["open_questions"] = [""]
    assert _problems(doc) == [
        ("findings[0].claim", "range"),
        ("sources[0].title", "range"),
        ("open_questions[0]", "range"),
    ]
    doc = _brief_doc()
    doc["findings"][0]["claim"] = "c" * 1001
    assert _problems(doc) == [("findings[0].claim", "range")]


def test_evidence_rules() -> None:
    doc = _brief_doc()
    doc["findings"][0]["evidence"] = []
    assert _problems(doc) == [("findings[0].evidence", "range")]
    doc["findings"][0]["evidence"] = ["src-1", 5]
    assert _problems(doc) == [("findings[0].evidence[1]", "type")]
    doc["findings"][0]["evidence"] = ["SRC-1"]
    assert _problems(doc) == [("findings[0].evidence[0]", "reference")]
    doc["findings"][0]["evidence"] = ["src-1", "src-1"]
    assert validate_brief(doc).findings[0].evidence == ("src-1", "src-1")


def test_source_kind() -> None:
    doc = _brief_doc()
    for kind in ("web", "paper", "video", "dataset", "other"):
        doc["sources"][0]["kind"] = kind
        assert validate_brief(doc).sources[0].kind == kind
    doc["sources"][0]["kind"] = "blog"
    assert _problems(doc) == [("sources[0].kind", "format")]
    doc["sources"][0]["kind"] = 1
    assert _problems(doc) == [("sources[0].kind", "type")]


def test_duplicate_source_ids() -> None:
    doc = _brief_doc()
    doc["sources"][1]["id"] = "src-1"
    doc["findings"][1]["evidence"] = ["src-1"]
    assert _problems(doc) == [("sources[1].id", "duplicate")]


def test_tags_are_collapsed_and_validated() -> None:
    doc = _brief_doc()
    doc["tags"] = ["b", "a", "b", "a-b", "a"]
    brief = validate_brief(doc)
    assert brief.tags == ("b", "a", "a-b")
    assert to_dict(brief)["tags"] == ["b", "a", "a-b"]


@pytest.mark.parametrize("tag", ["Bad", "a_b", "-a", "a-", "a--b", "", "a" * 65, "a b"])
def test_bad_tags(tag: str) -> None:
    doc = _brief_doc()
    doc["tags"] = [tag]
    assert _problems(doc) == [("tags[0]", "format")]


def test_tag_must_be_a_string() -> None:
    doc = _brief_doc()
    doc["tags"] = [5]
    assert _problems(doc) == [("tags[0]", "type")]


def test_topics_rules() -> None:
    doc = _topics_doc()
    doc["topics"] = []
    assert _topic_problems(doc) == [("topics", "range")]
    doc = _topics_doc()
    doc["topics"][0]["keywords"] = []
    assert _topic_problems(doc) == [("topics[0].keywords", "range")]
    doc = _topics_doc()
    doc["topics"][0]["active"] = "yes"
    doc["topics"][0]["cadence"] = "hourly"
    doc["topics"][1]["cadence"] = 5
    assert _topic_problems(doc) == [
        ("topics[0].cadence", "format"),
        ("topics[0].active", "type"),
        ("topics[1].cadence", "type"),
    ]
    doc = _topics_doc()
    doc["topics"][0]["name"] = ""
    del doc["topics"][0]["exclude_keywords"]
    del doc["topics"][1]["active"]
    assert _topic_problems(doc) == [("topics[0].name", "range"), ("topics[1].active", "required")]
    doc = _topics_doc()
    doc["topics"] = [1]
    assert _topic_problems(doc) == [("topics[0]", "type")]
    doc = _topics_doc()
    del doc["topics"]
    assert _topic_problems(doc) == [("topics", "required")]


def test_exclude_keywords_are_optional() -> None:
    doc = _topics_doc()
    del doc["topics"][0]["exclude_keywords"]
    assert validate_topics(doc).topics[0].exclude_keywords == ()


def test_duplicate_topic_ids() -> None:
    doc = _topics_doc()
    doc["topics"][1]["id"] = doc["topics"][0]["id"]
    assert _topic_problems(doc) == [("topics[1].id", "duplicate")]


def test_keywords_and_exclusions_must_be_disjoint_after_casefold() -> None:
    doc = _topics_doc()
    doc["topics"][0]["keywords"] = ["Solar", "wind"]
    doc["topics"][0]["exclude_keywords"] = ["hype", "SOLAR"]
    assert _topic_problems(doc) == [("topics[0].exclude_keywords[1]", "duplicate")]
    doc["topics"][0]["keywords"] = ["Stra\u00dfe"]
    doc["topics"][0]["exclude_keywords"] = ["STRASSE"]
    assert _topic_problems(doc) == [("topics[0].exclude_keywords[0]", "duplicate")]
    doc["topics"][0]["keywords"] = ["solar"]
    doc["topics"][0]["exclude_keywords"] = ["solar panel", "sol"]
    assert validate_topics(doc).topics[0].exclude_keywords == ("solar panel", "sol")


def test_overlap_is_found_even_when_other_fields_are_wrong() -> None:
    doc = _topics_doc()
    doc["topics"][0]["keywords"] = ["a"]
    doc["topics"][0]["exclude_keywords"] = ["A"]
    doc["topics"][0]["priority"] = 9
    assert _topic_problems(doc) == [
        ("topics[0].priority", "range"),
        ("topics[0].exclude_keywords[0]", "duplicate"),
    ]


def test_json_schema_matches_golden() -> None:
    brief = json_schema("research-brief")
    assert brief == _load("research-brief.schema.json")
    assert brief["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert brief["additionalProperties"] is False
    assert "Cross-field" in brief["description"]
    assert json_schema("topics") == _load("topics.schema.json")


def test_json_schema_returns_fresh_copies() -> None:
    json_schema("research-brief")["properties"].clear()
    json_schema("topics")["$defs"].clear()
    assert json_schema("research-brief") == _load("research-brief.schema.json")
    assert json_schema("topics") == _load("topics.schema.json")


def test_json_schema_rejects_unknown_kind() -> None:
    with pytest.raises(ContractError) as info:
        json_schema("other")  # type: ignore[arg-type]
    assert info.value.errors[0].path == "kind"


def test_to_dict_rejects_other_objects() -> None:
    with pytest.raises(ContractError) as info:
        to_dict({})  # type: ignore[arg-type]
    assert info.value.errors[0].code == "type"


def test_contract_error_message_is_short() -> None:
    errors = tuple(FieldError("p" * 500, "type", "m") for _ in range(3))
    error = ContractError(errors)
    assert len(str(error)) <= 200
    assert error.code == "invalid"
    assert error.errors == errors
    assert "<root>" in str(ContractError((FieldError("", "type", "m"),)))
    assert str(ContractError(())) == "0 contract violation(s)"


def test_messages_never_echo_input() -> None:
    doc = _brief_doc()
    doc["title"] = "s3cr3t" * 50
    doc["id"] = "y" * 10_000
    doc["k" * 10_000] = 1
    doc["findings"][0]["evidence"] = ["z" * 10_000]
    with pytest.raises(ContractError) as info:
        validate_brief(doc)
    for error in info.value.errors:
        assert len(error.message) <= 200
        assert "s3cr3t" not in error.message
        assert "yyyy" not in error.message
        assert "zzzz" not in error.message
        assert len(error.path) <= 200
    assert len(str(info.value)) <= 200


def test_failure_is_logged_without_content(caplog: pytest.LogCaptureFixture) -> None:
    doc = _brief_doc()
    doc["title"] = "s3cr3t" * 50
    with (
        caplog.at_level(logging.DEBUG, logger="research_brief_schema"),
        pytest.raises(ContractError),
    ):
        validate_brief(doc)
    assert "validation failed with 1 error(s)" in caplog.text
    assert "s3cr3t" not in caplog.text


def test_package_logger_has_only_a_null_handler() -> None:
    handlers = logging.getLogger("research_brief_schema").handlers
    assert any(isinstance(handler, logging.NullHandler) for handler in handlers)
