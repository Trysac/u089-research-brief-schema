# research-brief-schema

[![PyPI version](https://img.shields.io/pypi/v/trysac-research-brief-schema)](https://pypi.org/project/trysac-research-brief-schema/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-research-brief-schema)](LICENSE)
[![CI](https://github.com/Trysac/u089-research-brief-schema/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u089-research-brief-schema/actions/workflows/ci.yml)

Typed contracts and a dependency-free validator for research briefs and monitored topics, with cross-field rules and JSON Schema 2020-12 export

## Problem

Pipelines that research topics and hand results to writers or agents exchange JSON documents whose
shape drifts between producer and consumer. Plain JSON Schema catches types but not rules such as
"every finding must cite an existing source". This library gives every stage the same typed contract,
a complete list of errors per document, and an exported schema for other languages.

## Install

```sh
pip install trysac-research-brief-schema
# or
uv add trysac-research-brief-schema
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import json

from research_brief_schema import ContractError, json_schema, to_dict, validate_brief

with open("tests/golden/research_brief.json", encoding="utf-8") as fh:
    doc = json.load(fh)

try:
    brief = validate_brief(doc)
    print(brief.title, brief.uncited_sources)
    print(to_dict(brief) == doc)
except ContractError as exc:
    for error in exc.errors:
        print(error.path, error.code, error.message)

schema = json_schema("research-brief")
print(schema["$schema"])  # https://json-schema.org/draft/2020-12/schema
```

The golden schemas are in [tests/golden/research-brief.schema.json](tests/golden/research-brief.schema.json)
and [tests/golden/topics.schema.json](tests/golden/topics.schema.json). Cross-field rules (unique ids,
evidence references, disjoint keywords) cannot be expressed in JSON Schema; only the validator enforces them.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
