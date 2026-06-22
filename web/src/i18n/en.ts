// Seryvon — English locale (base). AGPL-3.0-or-later.

import type { Dict } from "./dict";

export const en: Dict = {
  localeName: "English",

  nav: {
    analyse: "ANALYSIS",
    configuration: "CONFIGURATION",
    overview: "Overview",
    report: "Audit report",
    plan: "Action plan",
    citation: "Citation Tracking",
    asoReadiness: "ASO Readiness",
    history: "History",
    promptSet: "Prompt Set",
    competitors: "Competitors",
    keys: "Keys & BYOK",
    soon: "soon",
  },

  status: { mode: "100% free + BYOK", sub: "Deterministic · traceable scoring" },

  topbar: {
    overviewTitle: "Overview",
    overviewSubtitle: "Deterministic scorecard across the five pillars",
    lastAudit: (when) => `Last audit · ${when}`,
    runAudit: "Run an audit",
  },

  home: {
    tagline: (pillars) =>
      `Deterministic web audit across five pillars — ${pillars}. Every score is traceable to its source data and reproducible (variance < 2%).`,
    placeholder: "https://example.com",
    audit: "Audit",
    auditing: "Auditing…",
    errorBackend: "Audit failed — is the FastAPI backend running?",
    errorStatus: (status, message) => `Audit failed (${status}): ${message}`,
  },

  report: {
    scoreGlobal: "GLOBAL VISIBILITY SCORE",
    summary: (measured, applicable, notMeasured) =>
      `${measured} criteria measured out of ${applicable} · ${notMeasured} marked`,
    statCriteria: "CRITERIA MEASURED",
    statDuration: "DURATION",
    statIssues: "ISSUES",
    statCoverage: "COVERAGE",
    issuesTitle: "Priority issues",
    issuesSub: "Priority = (impact × severity) / effort",
    noIssues: "No priority action — every measured criterion is green.",
    spectrum: "Visibility spectrum",
    loading: "Loading report…",
    notFound: (status) => `Report not found (${status})`,
    loadError: "Failed to load — is the backend running?",
  },

  pillarFull: {
    seo: "Search Engine Optimization",
    geo: "Generative Engine Optimization",
    gso: "Generative Search Optimization",
    aeo: "Answer Engine Optimization",
    aso: "Agentic Search Optimization",
  },

  coverage: {
    complete: "complete coverage",
    substantial: "substantial coverage",
    partial: "partial coverage",
    insufficient: "insufficient coverage",
  },

  readiness: { none: "None", basic: "Basic", ready: "Ready", advanced: "Advanced" },

  aso: {
    kicker: "AGENTIC READINESS · ASO",
    score: (n) => `· score ${n}/100`,
    blurbLead: "The pillar ",
    blurbStrong: "no one else audits",
    webmcpPresent: "WebMCP present",
    webmcpAbsent: (endpoints) => `WebMCP absent · ${endpoints} AI discovery endpoint(s)`,
  },

  pillar: { measured: "measured", excluded: "excluded" },
  issue: { effort: (n) => `EFFORT ${n}/3`, prio: (n) => `prio ${n.toFixed(1)}` },

  durationSeconds: (s) => `${s} s`,
  durationMinutes: (m, s) => `${m} m ${String(s).padStart(2, "0")} s`,
};
