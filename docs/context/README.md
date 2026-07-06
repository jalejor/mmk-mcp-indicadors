# Context Review — mmk-mcp-indicadors

Six-lens context review of the repository, generated **2026-07-05** from the
`development` branch. Each document below captures one lens of the codebase so
that a new contributor (human or AI) can get productive quickly.

| Lens | Document | What it answers |
| ---- | -------- | --------------- |
| Architecture | [architecture.md](architecture.md) | How the system is structured and how a request flows through it. |
| Conventions | [conventions.md](conventions.md) | Coding, naming, config and layout patterns to follow. |
| Decisions | [decisions.md](decisions.md) | Non-obvious design choices and the reasoning behind them. |
| Glossary | [glossary.md](glossary.md) | Domain and code terms (indicators, sizing, regimes, votes). |
| Workflow | [workflow.md](workflow.md) | How to build, run, test and deploy. |
| Known errors | [known-errors.md](known-errors.md) | Bugs, doc contradictions and traps found during the review. |

> This review is **read-only**: no application code was changed. Findings that
> look like bugs or documentation contradictions are collected in
> [known-errors.md](known-errors.md) rather than fixed in place.

## One-paragraph summary

`mmk-mcp-indicadors` is a **FastAPI** service that computes crypto technical
indicators, trading signals, position sizing and backtests over exchange OHLCV
data (via **ccxt**), and exposes the same compute both as versioned HTTP
endpoints (`/v1/*`) and as **MCP** (Model Context Protocol) tools for AI code
editors. It is stateless (no database), caches market data in-process, and is
deployed as a container to Google Cloud Run.
