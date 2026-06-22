// Seryvon — i18n dictionary contract. AGPL-3.0-or-later.
//
// English is the base locale; French is kept as a ready second locale. Dynamic
// strings are functions so each locale controls its own interpolation/plurals.

import type { Comparability, CoverageLabel, KeySource, Pillar, ReadinessLevel, Status } from "../api/types";

export type Locale = "en" | "fr";

export interface Dict {
  localeName: string; // shown in the language selector

  nav: {
    analyse: string;
    configuration: string;
    overview: string;
    report: string;
    plan: string;
    citation: string;
    asoReadiness: string;
    history: string;
    promptSet: string;
    competitors: string;
    keys: string;
    soon: string;
  };

  status: { mode: string; sub: string };

  topbar: {
    overviewTitle: string;
    overviewSubtitle: string;
    lastAudit: (when: string) => string;
    runAudit: string;
  };

  home: {
    tagline: (pillars: string) => string;
    placeholder: string;
    audit: string;
    auditing: string;
    errorBackend: string;
    errorStatus: (status: number, message: string) => string;
    progress: string;
  };

  report: {
    scoreGlobal: string;
    summary: (measured: number, applicable: number, notMeasured: number) => string;
    statCriteria: string;
    statDuration: string;
    statIssues: string;
    statCoverage: string;
    issuesTitle: string;
    issuesSub: string;
    noIssues: string;
    spectrum: string;
    loading: string;
    notFound: (status: number) => string;
    loadError: string;
  };

  criteria: {
    title: string;
    subtitle: string;
    filterAll: string;
    statusFilter: string;
    pillarTags: string;
    colCriterion: string;
    colScore: string;
    colWeight: string;
    tierExperimental: string;
    rawValue: string;
    threshold: string;
    explanation: string;
    evidence: string;
    noExplanation: string;
    none: string;
    empty: string;
    count: (n: number) => string;
  };

  plan: {
    title: string;
    subtitle: string;
    empty: string;
    affected: (n: number) => string;
    total: (n: number) => string;
  };

  asoDetail: {
    title: string;
    subtitle: string;
    agentReady: string;
    yes: string;
    no: string;
    webmcp: string;
    actionSchema: string;
    aiDiscovery: string;
    nlweb: string;
    brandCoherence: string;
    blockedBots: string;
    none: string;
    unavailable: string;
  };

  history: {
    title: string;
    subtitle: string;
    empty: string;
    colDate: string;
    colScore: string;
    colId: string;
    view: string;
    count: (n: number) => string;
  };

  pillarFull: Record<Pillar, string>;
  coverage: Record<CoverageLabel, string>;
  readiness: Record<ReadinessLevel, string>;
  statusLabel: Record<Status, string>;
  ruleLabel: Record<string, string>;

  aso: {
    kicker: string;
    score: (n: number) => string;
    blurbLead: string;
    blurbStrong: string;
    webmcpPresent: string;
    webmcpAbsent: (endpoints: number) => string;
  };

  compare: {
    title: string;
    subtitle: string;
    leftAudit: string;
    rightAudit: string;
    domainPlaceholder: string;
    loadHistory: string;
    loadingHistory: string;
    compareBtn: string;
    noHistory: (domain: string) => string;
    globalDelta: string;
    recomputed: string;
    comparability: Record<Comparability, string>;
    profileDiffs: (n: number) => string;
    colLeft: string;
    colRight: string;
    colDelta: string;
    onlyChanges: string;
    errorCompare: string;
  };

  keys: {
    title: string;
    subtitle: string;
    noEncryption: string;
    save: string;
    saving: string;
    delete: string;
    placeholder: string;
    source: Record<KeySource, string>;
    connectorDesc: Record<string, string>;
    getKey: string;
    saved: string;
    deleted: string;
    errorSave: string;
    errorDelete: string;
  };

  pillar: { measured: string; excluded: string };
  issue: { effort: (n: number) => string; prio: (n: number) => string };

  durationSeconds: (s: number) => string;
  durationMinutes: (m: number, s: number) => string;
}
