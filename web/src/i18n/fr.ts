// Seryvon — French locale (second). AGPL-3.0-or-later.

import type { Dict } from "./dict";

export const fr: Dict = {
  localeName: "Français",

  nav: {
    analyse: "ANALYSE",
    configuration: "CONFIGURATION",
    overview: "Vue d'ensemble",
    report: "Rapport d'audit",
    plan: "Plan d'action",
    citation: "Citation Tracking",
    asoReadiness: "Readiness ASO",
    history: "Historique",
    promptSet: "Prompt Set",
    competitors: "Concurrents",
    keys: "Clés & BYOK",
    soon: "bientôt",
  },

  status: { mode: "Mode 100 % gratuit + BYOK", sub: "Scoring déterministe · traçable" },

  topbar: {
    overviewTitle: "Vue d'ensemble",
    overviewSubtitle: "Scorecard déterministe sur les cinq piliers",
    lastAudit: (when) => `Dernier audit · ${when}`,
    runAudit: "Lancer un audit",
  },

  home: {
    tagline: (pillars) =>
      `Audit web déterministe sur cinq piliers — ${pillars}. Chaque score est traçable jusqu'à sa donnée source et reproductible (variance < 2 %).`,
    placeholder: "https://exemple.com",
    audit: "Auditer",
    auditing: "Audit en cours…",
    errorBackend: "Échec de l'audit — le backend FastAPI est-il démarré ?",
    errorStatus: (status, message) => `Échec de l'audit (${status}) : ${message}`,
  },

  report: {
    scoreGlobal: "SCORE GLOBAL DE VISIBILITÉ",
    summary: (measured, applicable, notMeasured) =>
      `${measured} critères mesurés sur ${applicable} · ${notMeasured} marqués`,
    statCriteria: "CRITÈRES MESURÉS",
    statDuration: "DURÉE",
    statIssues: "PROBLÈMES",
    statCoverage: "COUVERTURE",
    issuesTitle: "Problèmes prioritaires",
    issuesSub: "Priorité calculée : (impact × sévérité) / effort",
    noIssues: "Aucune action prioritaire — tous les critères mesurés sont au vert.",
    spectrum: "Spectre de visibilité",
    loading: "Chargement du rapport…",
    notFound: (status) => `Rapport introuvable (${status})`,
    loadError: "Échec du chargement — le backend est-il démarré ?",
  },

  pillarFull: {
    seo: "Search Engine Optimization",
    geo: "Generative Engine Optimization",
    gso: "Generative Search Optimization",
    aeo: "Answer Engine Optimization",
    aso: "Agentic Search Optimization",
  },

  coverage: {
    complete: "couverture complète",
    substantial: "couverture substantielle",
    partial: "couverture partielle",
    insufficient: "couverture insuffisante",
  },

  readiness: { none: "None", basic: "Basic", ready: "Ready", advanced: "Advanced" },

  aso: {
    kicker: "READINESS AGENTIQUE · ASO",
    score: (n) => `· score ${n}/100`,
    blurbLead: "Le pilier que ",
    blurbStrong: "personne d'autre n'audite",
    webmcpPresent: "WebMCP présent",
    webmcpAbsent: (endpoints) => `WebMCP absent · ${endpoints} endpoint(s) de découverte IA`,
  },

  pillar: { measured: "mesurés", excluded: "exclus" },
  issue: { effort: (n) => `EFFORT ${n}/3`, prio: (n) => `prio ${n.toFixed(1)}` },

  durationSeconds: (s) => `${s} s`,
  durationMinutes: (m, s) => `${m} m ${String(s).padStart(2, "0")} s`,
};
