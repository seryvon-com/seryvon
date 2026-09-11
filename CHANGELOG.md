# Changelog

## 1.0.0rc1 — 2026-09-11

Première release candidate du Core open source Seryvon.

### Inclus

- Audit déterministe des cinq piliers SEO, GEO, GSO, AEO et ASO.
- Crawler async borné, robots.txt, sitemaps et protection SSRF.
- Connecteurs BYOK pour PageSpeed, DataForSEO, GSC, SERP et moteurs LLM.
- Exports JSON, HTML, Markdown et PDF, avec stockage d’artefacts optionnel.
- Dashboard React avec i18n français/anglais, suivi du plan d’action et rank tracking.
- Profil de mesure hashé, labels de couverture et comparaison de scorecards.
- Profil Docker de test isolé avec PostgreSQL `seryvon_test` et Redis séparé.

### Qualité vérifiée

- 691 tests backend réussis dans Docker.
- Couverture Python globale : 100 % (5 163 statements, 0 manquant).
- Couverture frontend : 100 % lignes, branches, fonctions et statements.
- Ruff et MyPy validés dans Docker.
- Dépendances de production frontend : 0 vulnérabilité avec `npm audit --omit=dev`.

### Hors périmètre Core

L’authentification multi-tenant, les quotas SaaS, la collaboration et les
opérations continues sont développés séparément dans le dépôt privé SaaS.
