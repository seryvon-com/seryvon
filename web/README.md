# Seryvon — Frontend (web)

Interface React + TypeScript + Vite pour l'audit déterministe Seryvon (open core,
AGPL-3.0). Couvre la couche **Diagnose** : lancer un audit et lire la scorecard
(score global, 5 piliers, plan d'action priorisé).

## Développement

```bash
npm install
npm run dev        # http://localhost:5173 (proxy /api -> http://localhost:8000)
npm run build      # tsc + vite build
npm run typecheck  # tsc --noEmit
```

Le frontend appelle le backend FastAPI via le proxy `/api` (voir `vite.config.ts`).
Démarrer le backend en parallèle :

```bash
# depuis la racine du dépôt
.venv/Scripts/python -m uvicorn seryvon.api.main:app --port 8000
```

Les endpoints d'audit persistent en base : un PostgreSQL accessible
(`SERYVON_DATABASE_URL`) est requis pour le cycle complet
lancer → persister → recharger le rapport.

## Structure

```
src/
├── api/         types (miroir des modèles Pydantic) + client typé
├── components/  ScoreGauge, PillarCard, IssueList, ReportView, TopBar
├── lib/         helpers d'affichage (couleurs piliers, statuts, dates)
├── pages/       HomePage (formulaire) + ReportPage (rapport par id)
└── styles/      tokens.css (design tokens) + app.css (layout)
```

## À suivre

- Re-skin sur la maquette Claude Design (palette / typographie définitives).
- Détail par critère (drill-down), historique par domaine, comparaison M6
  (`POST /scorecards/compare`).
- Génération des types depuis l'OpenAPI du backend (remplacer `api/types.ts`).
