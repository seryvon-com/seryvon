<!-- Logo: see docs/ for the brand asset. -->

# Seryvon

**Deterministic web audit tool across 5 pillars — SEO · GEO · GSO · AEO · ASO.**

Seryvon measures a site's visibility to traditional search engines **and** to
generative engines, AI Overviews, answer engines and — uniquely — **autonomous
agents** (the ASO pillar). Every score is computed, traceable and reproducible:
two audits of the same site yield the same result.

> **Brand hierarchy:** **Powehi** (publisher, [powehi.eu](https://powehi.eu)) →
> **Infollution** (umbrella brand) → **Seryvon** (product, [seryvon.com](https://seryvon.com)).

---

## The 5 pillars

| Pillar | What it measures |
|--------|------------------|
| **SEO** | Technical and editorial conformance to traditional search engines |
| **GEO** | Likelihood of being cited by generative engines (ChatGPT, Perplexity, Gemini) |
| **GSO** | Ability to appear in Google AI Overviews / AI Mode |
| **AEO** | Ability to be selected as a direct answer |
| **ASO** | Ability to be discovered and **chosen by autonomous AI agents** *(differentiator)* |

A single weighted, renormalized global score aggregates the five pillars.
Criteria that cannot be measured (e.g. a missing API key) are marked
`not_measured` and excluded from the computation — **never estimated**.

---

## Project status

🚧 **Active development — Phase 4 (open core Observe + Diagnose layer).**

What is already delivered:

| Phase | What |
|-------|------|
| 0–1 | Async crawler, robots/sitemaps, full SEO scorecard (26 criteria), PageSpeed Insights + OpenPageRank connectors |
| 2 | GSO, AEO, ASO (static) scorecards; on-page GEO signals; Wikidata; prioritized action plan |
| 3 | LLM citation tracking M4 (Perplexity, OpenAI, Anthropic, Gemini) — bring-your-own-key; cost estimator |
| 4 C-P1 | Measurement profile hash + coverage labels (SIC doc 04 §4+6) |

Next: MinIO artifact storage (C-P2), scorecard comparison M6 (C-P3).

```bash
seryvon run https://example.com      # full audit -> JSON/HTML/Markdown report
seryvon aso https://example.com      # ASO pillar only (agentic readiness)
seryvon citations https://example.com --dry-run   # LLM citation tracking (BYOK)
seryvon history example.com          # history of persisted audits
```

The full design documentation lives in [`docs/sic/`](docs/sic/) (Search Intelligence
Core — the internal name for Seryvon's measurement kernel).

---

## Quick start

### With Docker (recommended)

```bash
cp .env.example .env          # adjust if needed
docker compose up --build     # postgres, redis, api, workers
docker compose run --rm api alembic upgrade head   # migrations
```

The API is then available at http://localhost:8000 (docs: `/docs`).

### Locally (without Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
seryvon run https://example.com
```

---

## Development

```bash
ruff check .          # lint
ruff format .         # formatting
mypy src              # static typing
pytest                # tests + coverage
```

The scoring engine is kept under thorough automated test coverage.

---

## Architecture

A **Python 3.12+** core (async httpx crawl, deterministic scoring, FastAPI API,
Typer CLI) plus a **TypeScript/React** dashboard (later phases), backed by
**PostgreSQL** + **Redis** (+ MinIO for raw artifacts, upcoming), fully
containerized. Scoring follows a "rule registry" pattern: each criterion is a
self-registering rule, so new ones can be added without reworking the engine.

The internal design follows the **Search Intelligence Core** (SIC) model:

```
OBSERVE → DIAGNOSE → ACT → PROVE
```

`Observe` and `Diagnose` are open core. `Act` (Content Action Studio) and
`Prove` (experimentation) are part of the proprietary SaaS offering.
Design specifications: [`docs/sic/`](docs/sic/).

---

## License

Seryvon (the core) is distributed under the **GNU AGPL-3.0-or-later** license.
Copyright © 2026 **Powehi** — https://powehi.eu

You may freely use, modify and redistribute Seryvon. If you run a modified
version as a **network service** (SaaS), the AGPL requires you to make the
corresponding source code available to your users.

Reused third-party components ([GEO Optimizer](https://github.com/Auriti-Labs/geo-optimizer-skill),
[OpenSEO](https://github.com/every-app/open-seo)) remain under the MIT License;
see [`NOTICE`](./NOTICE) for attributions.

> **Open core.** This repository holds the free core (the 5 audit pillars). The
> operated offering (managed hosting, continuous monitoring, collaboration) is a
> separate proprietary product, published by Powehi under the Infollution brand.

---

*Built with components adapted from GEO Optimizer (© Juan Camilo Auriti) and
OpenSEO (© Ben Senescu), used under the MIT License.*
