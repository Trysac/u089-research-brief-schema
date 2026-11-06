# research-brief-schema

[![PyPI version](https://img.shields.io/pypi/v/trysac-research-brief-schema)](https://pypi.org/project/trysac-research-brief-schema/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-research-brief-schema)](LICENSE)
[![CI](https://github.com/Trysac/u089-research-brief-schema/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u089-research-brief-schema/actions/workflows/ci.yml)

Typed contracts and a dependency-free validator for research briefs and monitored topics, with cross-field rules and JSON Schema 2020-12 export

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-research-brief-schema
# or
uv add trysac-research-brief-schema
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import research_brief_schema

# normalize() trims surrounding whitespace and lower-cases the text.
print(research_brief_schema.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    research_brief_schema.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
