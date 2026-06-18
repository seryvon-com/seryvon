# HANDOFF — Reprise du projet Seryvon (Claude Code)

> Document de passation pour reprendre Seryvon dans une nouvelle session.
> Rédigé le 2026-06-18. **Lis d'abord** ce fichier, puis `CLAUDE.md`, puis les
> mémoires (voir §1). Les détails de conception sont dans `docs/`.

## 0. TL;DR
Outil d'audit web **déterministe** sur 5 piliers (SEO · GEO · GSO · AEO · ASO),
open core (AGPL-3.0). Phases 0, 1 (`v0.1`), 2 (`v0.2`), 2.6 (cœur GEO) et la
persistance synchrone (M8) sont **faites**. HEAD = `340052e`, branche `main`,
working tree propre. **226 tests verts**, `ruff` + `ruff format` + `mypy --strict`
à 0 erreur, scoring 100 %, couverture globale ~95 %. 58 critères enregistrés.

## 1. À lire en premier (ordre)
1. Ce `HANDOFF.md`.
2. `CLAUDE.md` (racine) — contexte, conventions, état/roadmap à jour, pièges.
3. Mémoires (chargées automatiquement via `MEMORY.md`) dans
   `C:\Users\x-v-i\.claude\projects\H--seryvon\memory\` :
   - `phase1-decisions.md` (D1–D5), `phase2-decisions.md` (D6–D10),
     `geo-persistence-decisions.md` (DG1–DG4, DB1–DB3 + statut).
4. `docs/` (gitignoré, présent localement) : `04-criteres-et-scoring.md` (catalogue
   + formules), `05-modele-de-donnees.md`, `06-roadmap.md`, `11-module-m11-aso.md`,
   `12-reutilisation-briques-open-source.md`.

## 2. Environnement (Windows / PowerShell)
- Python **3.14** dans un venv `.venv` (déjà créé). Binaires : `.\.venv\Scripts\…`.
- **Postgres + Redis** tournent via Docker (`seryvon-postgres:5432`,
  `seryvon-redis:6379`, user/pwd/db = `seryvon`). Base de test : `seryvon_test`.
  Si arrêtés : `docker compose up -d postgres redis` (ou relancer les conteneurs).
- PowerShell 5.1 : **pas** de `&&`/`||`. Here-strings pour messages de commit
  (`@'… '@`, `'@` en colonne 0). Éviter `2>&1` sur les exe natifs (alembic logge
  en stderr → faux « RemoteException », l'exit code reste fiable).

## 3. Pipeline de vérification (doit rester vert avant chaque commit)
```
.\.venv\Scripts\ruff.exe format .
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe src
$env:SERYVON_TEST_DATABASE_URL = "postgresql+psycopg://seryvon:seryvon@localhost:5432/seryvon_test"
.\.venv\Scripts\pytest.exe -q
```
> Sans `SERYVON_TEST_DATABASE_URL`, les tests DB (`test_repository.py`, endpoints
> d'audit de `test_api.py`) sont **skippés proprement** — c'est voulu (DB1).

Démo réelle : `.\.venv\Scripts\seryvon.exe run https://example.com -f md -o rapport.md`
(formats : `json|html|md|both`; `--persist` pour écrire en base; `seryvon history <host>`).

## 4. Règles de travail (NON négociables — respectées tout du long)
- **Déterminisme sacré** : aucune I/O dans une règle de scoring ; `evaluate(signals,
  thresholds=None)` est pur ; même `SignalBundle` ⇒ mêmes scores.
- **Un critère = une règle `@register`** ; ne jamais modifier le moteur pour ajouter
  un critère.
- Critère non mesurable ⇒ `not_measured` (exclu + renormalisé), **jamais d'estimation**.
- `ruff`, `ruff format`, `mypy --strict` verts ; tests scoring > 80 % (réel : 100 %).
- En-tête AGPL 7 lignes en tête des `.py` de `src/` ; 3 lignes pour `tests/`.
- Caractères FR autorisés (RUF001/2/3 ignorés).
- **Cadence** : avancer par *vertical slice* → pipeline vert → **commit atomique** →
  **s'arrêter pour validation de l'utilisateur** avant la slice suivante. Proposer un
  **plan avant de coder** une nouvelle phase ; en cas d'ambiguïté (critère/pondération/
  formule) **DEMANDER**, ne pas inventer. Connecteurs testés sans réseau
  (`httpx.MockTransport` / fetch injecté) ; DB testée gated (Postgres réel).

## 5. Architecture (src/seryvon/)
- `core/` : `config` (Settings env `SERYVON_` + clés BYOK `PSI_API_KEY`/`OPR_API_KEY` ;
  `AuditConfig` YAML) ; `audit.run_audit` (orchestrateur **pur**, asynchrone :
  discover → crawl → extract → external/sondes/Wikidata → scoring → readiness →
  issues → rapport ; un site injoignable ⇒ rapport vide, pas d'exception).
- `crawler/` : `discovery` (M1 robots `protego`/sitemaps/frontière + `AGENT_BOTS`),
  `crawl` (M2 BFS async, heuristique SSR/CSR), `extract` (M3.1/3.2/3.3 — signaux purs),
  `fetch`.
- `connectors/` : `pagespeed`, `openpagerank`, `ai_discovery` (+ NLWeb), `wikidata`.
  Tous : parsing pur + fetch httpx **injectable** ; erreur ⇒ dégradation gracieuse.
- `models/` : `signals` (`SignalBundle`, `signal_schema_version = 7`, `audited_at`),
  `criterion` (interface + `RULES` + `@register` + `ThresholdConfig`), `report`, `enums`.
- `scoring/` : `engine` (agrégation + renormalisation), `rules/` (seo, perf, authority,
  gso, aeo, geo, aso), `readiness` (none/basic/ready/advanced), `issues` (P1–P4).
- `reporting/` : `json` (source de vérité), `html` (Jinja2 autoescape), `markdown`.
- `db/` : `base` (engine/SessionLocal/`session_scope`), `models` (8 tables ORM PG),
  `repository` (`persist_report`/`load_report`/`list_audits`). Migration Alembic
  `d8ddd3948ee0` (valide). `tasks/` : Celery app + `run_audit_task` (**pas encore
  câblé async** — voir §7 B3).
- `api/` (FastAPI : `/health`, `POST/GET /audits`, `GET /audits?domain=`),
  `cli/` (Typer : `run`, `history`, stubs `aso`/`compare`).

## 6. Couverture par pilier (58 critères ; natifs implémentés / doc 04)
- **SEO 26/26** ✅ — `perf.*`×4 + `authority.opr` `not_measured` sans clé ;
  `authority.backlinks` `not_measured` (D3, pas de source gratuite).
- **GSO 8/8** ✅ — `gso.longtail` `not_measured` (D6), `gso.ai_overview_presence`
  `not_measured` (SERP, Phase 4), `gso.cwv_eligible` dépend de PSI.
- **AEO 8/8** ✅ — `aeo.kg_presence` via Wikidata ; `aeo.llm_citation` `not_measured`
  (M4, Phase 3).
- **ASO 9/10** ✅ (statique complet) — `aso.agent_selection_rate` (v2 dynamique) non
  implémenté.
- **GEO 7/10** ✅ on-page (ssr, noise_ratio, entity_density, primary_sources, authors,
  cross_platform, freshness). **Manquent** : `geo.citation_rate`, `geo.mention_rate`,
  `geo.citation_confidence` → **Phase 3** (citation LLM/M4).
- Tags multi-piliers actifs : `struct.schema`→seo/gso/aeo/aso ; `perf.*`→seo/gso ;
  `geo.ssr`→geo/aeo/aso ; etc.

## 7. Prochaines étapes (par priorité)
1. **B3 — Celery async (optionnel, DB2)** : `POST /audits` → enqueue `run_audit_task`
   → `202` + `job_id` ; `GET /audits/{id}` renvoie statut puis résultat ; le worker
   **persiste** via `repository.persist_report`. Redis up. Tests en `task_always_eager`.
   ~2–3 j. Change la sémantique API (202/polling).
2. **Phase 3 — Citation tracking LLM (M4)** + finir GEO : connecteurs OpenAI/Gemini/
   Anthropic/Perplexity (BYOK, interface commune), prompt set, K répétitions, `--dry-run`,
   estimation de coût → active `geo.citation_rate/mention_rate/citation_confidence`,
   `aeo.llm_citation`. (doc 07/08.)
3. **Phase 4** : M10 GSC (rank, gratuit) + M9 SERP (DataForSEO) + `gso.ai_overview_presence`
   + M6 comparaison concurrentielle + M8 historisation avancée + mode `seryvon ci
   --fail-under`. (doc 10.)
4. **Phase 5** : UI React + publication OSS.

### Quick wins (faible effort, valeur immédiate)
- CLI `aso` est un stub `exit 2` alors que le scoring ASO existe → l'implémenter
  (audit ASO seul, rapide).
- `.gitattributes` (`* text=auto eol=lf`) pour supprimer les avertissements LF→CRLF.
- `.claude/launch.json` a été commité avec un chemin machine (`.venv/...`) → envisager
  de l'ignorer (`.gitignore` + `git rm --cached`).
- `/docs` (Swagger) ne s'affiche pas hors-ligne (assets CDN) → option : servir Swagger
  en local (~15 lignes dans `api/main.py`).

## 8. Dette / limitations connues
- **Câblage `thresholds:` partiel** : seul `content.depth.target_words` est surchargeable.
- **Pas de cache** (Redis non utilisé par les connecteurs ; chaque audit refait les appels).
- **Pages/signaux non persistés** (le rapport ne les porte pas ; snapshot de re-scoring
  = backlog) → seuls audit/critères/piliers/issues/readiness sont en base.
- **Approximations à raffiner** : `geo.ssr` heuristique (pas Playwright) ; sonde **NLWeb**
  sur convention `/ask` (standard non figé) ; `aso.agent_access` lit robots.txt seul
  (pas de simulation CDN) ; `brand_coherence` = recouvrement de tokens, 2 surfaces ;
  `entity_density` heuristique (capitalisation, sans NLP) ; PSI = home seule.
- **Déterminisme** garanti au niveau scoring ; un re-run live n'est pas bit-identique
  (PSI/Wikidata/sondes = monde réel) — conforme à « hors temps réel » (doc 01 O3).
- `db/`+`tasks/` async : worker Celery non câblé (B3).

## 9. Réutilisation MIT (crédit obligatoire)
`scoring/rules/aso.py` et `connectors/ai_discovery.py` sont transposés d'`audit_webmcp.py`
/ `audit_ai_discovery.py` (GEO Optimizer, MIT — Juan Camilo Auriti). Crédit dans `NOTICE`
(déjà présent). Conserver les notices pour toute nouvelle transposition (doc 12).
