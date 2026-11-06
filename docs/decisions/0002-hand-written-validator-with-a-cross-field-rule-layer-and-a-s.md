# Hand-written validator with a cross-field rule layer and a separately built schema

Status: accepted (generated, pending human review)

## Context

Pipelines exchange research briefs and topic lists as JSON. Plain JSON Schema cannot express rules such as every finding must cite an existing source, unique ids or disjoint keyword lists, and a general framework such as pydantic or jsonschema would add a runtime dependency. Consumers in other languages still need a schema, and callers want every problem reported at once without unbounded output or leaked input.

## Decision

Implement a small table-driven validator in the standard library only. Each object type is a dict of field handlers that run in the order the keys appear in the document; handlers return None after recording a FieldError, and the cross-field rules (duplicate ids, evidence references resolved against a pre-collected set of source ids, casefolded keyword overlap) run inside that pass. The error list is capped at 100 plus a too_many_errors marker, and all size and depth limits are named constants in one module. The JSON Schema is built by separate code from the same limits and pinned by golden files in the tests, and its description states that cross-field rules are only enforced by the validators. Dataclasses are frozen and uncited_sources is a computed property.

## Consequences

There are no runtime dependencies and error order, codes and limits are fully controlled and tested. The schema and the validator are two implementations that can drift, so golden schema files and tests tie them together. Adding a field means updating the handler table, the dataclass, to_dict, the schema builder and the golden files. Some interpretations (error order by document key order, a version error that stops validation, format code for enum violations) are documented in docs/CONTRACT.md and must be kept in sync with the tests.
