# Contract reference and demo

`research_brief_schema` validates two JSON documents, a research brief and a topics file. It
returns immutable dataclasses, reports every problem at once and exports a JSON Schema
(Draft 2020-12) for other languages. It has no runtime dependencies.

## Quick start

```python
from research_brief_schema import ContractError, validate_brief

doc = {
    "schema_version": "1.0",
    "id": "b-1",
    "topic_id": "t-1",
    "title": "T",
    "summary": "S",
    "created_at": "2026-11-05T10:00:00Z",
    "sources": [],
    "findings": [{"claim": "c", "evidence": ["s-9"], "confidence": 0.5}],
}
try:
    validate_brief(doc)
except ContractError as exc:
    print([(e.path, e.code) for e in exc.errors])  # [('findings[0].evidence[0]', 'reference')]
```

## Public API

| Name | Purpose |
|---|---|
| `validate_brief(data, *, strict=True)` | Returns a `ResearchBrief` or raises `ContractError`. |
| `validate_topics(data, *, strict=True)` | Returns a `TopicsFile` or raises `ContractError`. |
| `to_dict(obj)` | JSON-ready dictionary, keys in declaration order, datetimes as RFC 3339 with `Z`. |
| `json_schema(kind)` | Draft 2020-12 schema for `"research-brief"` or `"topics"`. |
| `ContractError`, `FieldError` | One error class with `code == "invalid"` and a tuple of field errors. |
| `SCHEMA_VERSION` | `"1.0"`. Any `1.x` document is accepted; other majors give code `version`. |

## Error codes

`required`, `type`, `range`, `format`, `unknown_field`, `reference`, `duplicate`, `version`,
`too_many`, `too_deep` and `too_many_errors`. At most 100 problems are listed; a 101st entry with
path `""` and code `too_many_errors` marks truncation. Errors follow the order of the keys in the
document; missing required fields are listed last in declared order. Messages never quote input.
An unsupported major version stops validation, so it is the only error reported.

## Rules

- Ids match `^[a-z0-9][a-z0-9-]{0,63}$`. Source ids and topic ids are unique (`duplicate`).
- Every `findings[].evidence` entry must be an existing source id (`reference`).
- `keywords` and `exclude_keywords` must be disjoint after `str.casefold` (`duplicate`, reported at
  the `exclude_keywords` entry).
- `bool` is never accepted as an int or float; ints are accepted for float fields and returned as
  float. Non-finite numbers are rejected (`range`).
- Enumerations (`kind`, `cadence`) report `format` when the string is not an allowed value.
- Datetimes follow RFC 3339 section 5.6: `Z` or an offset is required, `T` and `Z` may be lower
  case, fractions are padded or cut to 6 digits, leap seconds (`:60`) are rejected.
- URLs are `http` or `https` (any case) with a host, no userinfo, no whitespace or control
  characters and at most 2048 characters.
- `uncited_sources` is a property listing sources no finding cites. It is a warning and is not part
  of `to_dict` or the schema.
- `open_questions`, `tags` and `extras` are optional on input; `tags` are lowercase kebab-case and
  duplicates collapse, keeping the first occurrence. Topic `exclude_keywords` is optional.
- With `strict=False`, unknown top-level brief fields move into `extras`; unknown nested fields
  and unknown topics-file fields are ignored. With `strict=True` they give `unknown_field`.

## Limits

| Item | Limit |
|---|---|
| findings / sources | 1000 each |
| topics | 500 |
| open questions | 100, each 1-1000 characters |
| tags | 100, each at most 64 characters |
| evidence entries per finding | 1000 |
| keywords / exclude keywords per topic | 100, each 1-100 characters |
| title / summary / claim | 200 / 2000 / 1000 characters |
| source title / topic name | 500 / 200 characters |
| extras | depth 10 (the extras object is level 1), 10000 values, strings up to 10000 characters |
| URL / datetime text | 2048 / 64 characters |

## Exported schema

`json_schema` returns a fresh dictionary on every call. The schemas set `additionalProperties` to
`false`, list required fields and use string patterns plus the formats `date-time` and `uri`.
Cross-field rules (unique ids, evidence references, disjoint keywords) cannot be expressed in JSON
Schema; the schema `description` says so. The golden schemas used by the tests are
`tests/golden/research-brief.schema.json` and `tests/golden/topics.schema.json`.

## Out of scope

Migrations between versions, storage and fetching sources.

## Compared with pydantic or jsonschema

This library has zero dependencies, enforces the cross-field rules above and ships a schema that
other languages can use. It does not try to be a general validation framework.
