# Project record

## Objective

Typed contracts and a dependency-free validator for research briefs and monitored topics, with cross-field rules and JSON Schema 2020-12 export

## Scope

- In scope: the public API documented in [README.md](../README.md), typed and tested.
- Out of scope: anything that needs runtime dependencies or I/O without an accepted ADR.

## Timeline

| Date | Event |
|---|---|
| 2026 | Repository created from the factory utility template. |

## Effort metrics

Measured values only; a value that has not been measured stays "pending measurement".

| Metric | Value |
|---|---|
| Tokens (input / output) | 688399 / 127696 |
| Hours (human) | pending measurement |
| Cost (USD) | 1.0564 |

## Factory run u089 (measured from API usage)

| Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|
| generation | claude-sonnet-5-5 | yes | 2373 | 109372 | 0 | 4246 | 0.5497 |
| fix-1 | claude-sonnet-5-5 | no | 6 | 555 | 6050 | 39750 | 0.0247 |
| fix-2 | claude-sonnet-5-5 | no | 14 | 2745 | 13672 | 124500 | 0.0741 |
| audit | claude-sonnet-5-5 | no | 12 | 5997 | 48828 | 151238 | 0.1972 |
| fix-3 | claude-sonnet-5-5 | no | 10 | 2695 | 11208 | 80251 | 0.0630 |
| fix-4 | claude-sonnet-5-5 | no | 16 | 2123 | 11713 | 140655 | 0.0646 |
| docs | claude-haiku-5-5 | no | 145328 | 4209 | 0 | 0 | 0.0832 |

Total: $1.0564. Prices: Anthropic list prices.
