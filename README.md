<!-- Logo: see docs/ for the brand asset. -->

# Seryvon

**Deterministic web audit tool across 5 pillars — SEO · GEO · GSO · AEO · ASO.**

Seryvon measures a site's visibility to traditional search engines **and** to
generative engines, AI Overviews, answer engines and — uniquely — **autonomous
agents** (the ASO pillar). Every score is computed, traceable and reproducible:
two audits of the same site yield the same result.

> **Product identity:** **Seryvon** is published by **Powehi** ([powehi.eu](https://powehi.eu)).

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

✅ **Open core complete — Observe + Diagnose stable (through Phase 10).**

What is already delivered:

| Phase | What |
|-------|------|
| 0–1 | Async crawler, robots/sitemaps, full SEO scorecard (26 criteria), PageSpeed Insights + OpenPageRank connectors |
| 2 | GSO, AEO, ASO (static) scorecards; on-page GEO signals; Wikidata; prioritized action plan |
| 3 | LLM citation tracking M4 (Perplexity, OpenAI, Anthropic, Gemini) — bring-your-own-key; cost estimator |
| 4 C-P1 | Measurement profile hash + coverage labels (SIC doc 04 §4+6) |
| 4 C-P2/C-P3 | Content-addressed artifacts and scorecard comparison |
| 5–10 | React UI/i18n, action-plan tracking, PDF export, GSC rank tracking, SERP/AIO, UX stabilization |

Current verification: 691 backend tests pass in the dedicated Docker profile, with
100% Python coverage (5,163 statements, zero missed). The frontend has 200 tests,
with a clean typecheck and 100% coverage for lines, branches and functions.
The frontend uses React Router 7.18.3 and has no known production dependency
vulnerability (`npm audit --omit=dev`).

Next: hardening of the local open core, release automation and connector maintenance.

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
docker compose up --build     # postgres, redis, api, workers and frontend
```

The local stack binds to loopback only: frontend at http://localhost:3000,
API at http://localhost:8000 (docs: `/docs`). PostgreSQL and Redis are also
loopback-only. Migrations run automatically through the one-shot `migrate`
service. Stop with `docker compose down`; add `-v` only when intentionally
resetting local data.

Run the complete backend/PDF test suite in its dedicated Docker image:

```bash
docker compose --profile test build test
docker compose --profile test run --rm test
```

The integration suite must run in this profile: PostgreSQL uses `seryvon_test`,
Redis is separate from the runtime, and each test is limited to 30 seconds so
hangs become immediately visible.

The `test` profile is never started by the normal runtime stack and therefore
does not add development dependencies to the production API or worker images.
Its image reuses the PDF runtime layer from `base`, so subsequent builds only
install the development tools when source metadata changes.

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
ruff format --check . # formatting check
mypy src              # static typing
pytest                # backend tests
cd web && npm run test:coverage -- --run
```

Current verification: 691 backend tests pass in Docker, 200 frontend tests pass,
and the frontend reports 100% statements, branches, functions and lines. The
backend coverage command reports 100% globally (5,163 statements, 0 missed).
Backend tests requiring a live database should be run with
`SERYVON_TEST_DATABASE_URL` set; PDF tests additionally require WeasyPrint's
native libraries. The production Docker image includes the PDF runtime, while
development test dependencies stay outside that image.

### Technical performance and limits

Measurements below are local reference values, not a performance SLA:

| Check | Result |
|-------|--------|
| Frontend production build | ~1.5 s |
| Frontend test suite (200 tests) | ~14 s |
| Backend test suite (691 tests) | ~18–20 s |
| Full audit crawl limit | 300 pages per audit |
| Sitemap discovery limit | 5,000 URLs |
| Default crawler concurrency | 5 (reduced to 1 with `crawl-delay`) |
| General request timeout | 15 s |
| Playwright timeout | 30 s |

Crawler requests are bounded, robots-aware and SSRF-validated. PDF and other
non-HTML resources are not sent to Playwright. External connector calls remain
dependent on provider latency, quotas and credentials.

---

## Architecture

A **Python 3.12+** core (async httpx crawl, deterministic scoring, FastAPI API,
Typer CLI) plus a **TypeScript/React** dashboard, backed by
**PostgreSQL** + **Redis** (+ optional S3/MinIO for raw artifacts), fully
containerized. Scoring follows a "rule registry" pattern: each criterion is a
self-registering rule, so new ones can be added without reworking the engine.

The internal design follows the **Search Intelligence Core** (SIC) model:

```
OBSERVE → DIAGNOSE → ACT → PROVE
```

`Observe` and `Diagnose` define the current open-core scope.
Design specifications: [`docs/sic/`](docs/sic/).

The multi-tenant SaaS is intentionally maintained outside this repository in
the private [`seryvon-saas`](https://github.com/seryvon-com/seryvon-saas) repository.
Core remains local-first and single-tenant; SaaS-specific authentication,
isolation, quotas and continuous operations must not be added here.

---

## License

Seryvon (the core) is distributed under the **GNU AGPL-3.0-or-later** license.
Copyright © 2026 **Powehi** — https://powehi.eu

You may freely use, modify and redistribute Seryvon. If you run a modified
version as a network service, the AGPL requires you to make the corresponding
source code available to your users.

Reused third-party components ([GEO Optimizer](https://github.com/Auriti-Labs/geo-optimizer-skill),
[OpenSEO](https://github.com/every-app/open-seo)) remain under the MIT License;
see [`NOTICE`](./NOTICE) for attributions.

> **Open core.** This repository holds the free core (the 5 audit pillars). The
> operated offering (managed hosting, continuous monitoring, collaboration) is a
> separate proprietary product, published by Powehi.

---

*Built with components adapted from GEO Optimizer (© Juan Camilo Auriti) and
OpenSEO (© Ben Senescu), used under the MIT License.*
