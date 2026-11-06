"""Typed contracts and a dependency-free validator for research briefs and monitored topics.

The package validates JSON-like documents against two contracts (research briefs and topics
files), enforces cross-field rules that plain JSON Schema cannot express and exports a
JSON Schema 2020-12 description for other languages.
"""

from __future__ import annotations

import logging

from .errors import ContractError, ErrorCode, FieldError
from .models import SCHEMA_VERSION, Finding, ResearchBrief, Source, Topic, TopicsFile, to_dict
from .schema import json_schema
from .validator import validate_brief, validate_topics

__all__ = [
    "SCHEMA_VERSION",
    "ContractError",
    "ErrorCode",
    "FieldError",
    "Finding",
    "ResearchBrief",
    "Source",
    "Topic",
    "TopicsFile",
    "__version__",
    "json_schema",
    "to_dict",
    "validate_brief",
    "validate_topics",
]

__version__ = "0.1.0"

logging.getLogger(__name__).addHandler(logging.NullHandler())
