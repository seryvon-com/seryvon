<!-- Logo : voir docs/ pour l'asset de marque. -->

# Seryvon

**Outil d'audit web déterministe sur 5 piliers — SEO · GEO · GSO · AEO · ASO.**

Seryvon mesure la visibilité d'un site auprès des moteurs traditionnels **et** des
moteurs génératifs, des AI Overviews, des moteurs de réponse, et — fait unique —
des **agents autonomes** (pilier ASO). Chaque score est calculé, traçable et
reproductible : deux audits du même site produisent le même résultat.

> **Hiérarchie de marque :** **Powehi** (éditeur, [powehi.eu](https://powehi.eu)) →
> **Infollution** (marque-ombrelle) → **Seryvon** (produit, [seryvon.com](https://seryvon.com)).

---

## Les 5 piliers

| Pilier | Mesure |
|--------|--------|
| **SEO** | Conformité technique et éditoriale aux moteurs traditionnels |
| **GEO** | Probabilité d'être cité par les moteurs génératifs (ChatGPT, Perplexity, Gemini) |
| **GSO** | Aptitude à apparaître dans les Google AI Overviews / AI Mode |
| **AEO** | Aptitude à être sélectionné comme réponse directe |
| **ASO** | Aptitude à être découvert et **choisi par des agents IA autonomes** *(différenciateur)* |

Un score global unique, pondéré et renormalisé, agrège les cinq piliers. Les
critères non mesurables (faute de clé API, par exemple) sont marqués
`not_measured` et exclus du calcul — **jamais estimés**.

---

## État du projet

🚧 **Phase 0 — Fondations.** Le squelette est en place : CLI, API, moteur de
scoring déterministe, modèle de données, conteneurisation. Le livrable courant :

```bash
seryvon run https://example.com
```

…crawle la home, exécute les règles enregistrées et émet un rapport JSON traçable.
La roadmap complète (Phases 1–6) figure dans la documentation de conception.

---

## Démarrage rapide

### Avec Docker (recommandé)

```bash
cp .env.example .env          # ajuster si besoin
docker compose up --build     # postgres, redis, api, workers
docker compose run --rm api alembic upgrade head   # migrations
```

L'API est alors disponible sur http://localhost:8000 (doc : `/docs`).

### En local (sans Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
seryvon run https://example.com
```

---

## Développement

```bash
ruff check .          # lint
ruff format .         # formatage
mypy src              # typage statique
pytest                # tests + couverture
```

La couverture du moteur de scoring est tenue **> 80 %** (exigence ENF-06).

---

## Architecture

Cœur **Python 3.12** (crawl async httpx, scoring déterministe, API FastAPI,
CLI Typer) + dashboard **TypeScript/React** (phases ultérieures), avec
**PostgreSQL** + **Redis**, le tout containerisé. Le scoring suit un pattern
« rule registry » : chaque critère est une règle auto-enregistrée, ce qui permet
d'en ajouter sans refonte du moteur.

---

## Licence

Seryvon (le cœur) est distribué sous licence **GNU AGPL-3.0-or-later**.
Copyright © 2026 **Powehi** — https://powehi.eu

Vous pouvez utiliser, modifier et redistribuer Seryvon librement. Si vous
exécutez une version modifiée comme **service réseau** (SaaS), l'AGPL exige que
vous mettiez le code source correspondant à disposition de vos utilisateurs.

Les composants tiers réutilisés ([GEO Optimizer](https://github.com/Auriti-Labs/geo-optimizer-skill),
[OpenSEO](https://github.com/every-app/open-seo)) restent sous licence MIT ;
voir [`NOTICE`](./NOTICE) pour les attributions.

> **Open core.** Ce dépôt contient le cœur libre (les 5 piliers d'audit). L'offre
> opérée (hébergement géré, monitoring continu, collaboratif) est un produit
> propriétaire séparé, édité par Powehi sous la marque Infollution.

---

*Built with components adapted from GEO Optimizer (© Juan Camilo Auriti) and
OpenSEO (© Ben Senescu), used under the MIT License.*
