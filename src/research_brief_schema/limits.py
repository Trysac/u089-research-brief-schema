"""Named size limits enforced by the validator and reflected in the exported schema."""

from __future__ import annotations

from typing import Final

MAX_ERRORS: Final = 100
MAX_FINDINGS: Final = 1000
MAX_SOURCES: Final = 1000
MAX_TOPICS: Final = 500
MAX_OPEN_QUESTIONS: Final = 100
MAX_TAGS: Final = 100
MAX_EVIDENCE: Final = 1000
MAX_KEYWORDS: Final = 100
MAX_EXTRAS_DEPTH: Final = 10
MAX_EXTRAS_NODES: Final = 10_000
MAX_EXTRAS_STRING: Final = 10_000
MAX_URL_LENGTH: Final = 2048
MAX_DATETIME_LENGTH: Final = 64
MAX_TITLE: Final = 200
MAX_SUMMARY: Final = 2000
MAX_CLAIM: Final = 1000
MAX_QUESTION: Final = 1000
MAX_SOURCE_TITLE: Final = 500
MAX_NAME: Final = 200
MAX_TAG_LENGTH: Final = 64
MAX_KEYWORD_LENGTH: Final = 100
MAX_KEY_IN_PATH: Final = 64
