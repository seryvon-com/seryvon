// Seryvon — i18n dictionary contract. AGPL-3.0-or-later.
//
// English is the base locale; French is kept as a ready second locale. Dynamic
// strings are functions so each locale controls its own interpolation/plurals.

import type { Comparability, CoverageLabel, KeySource, Pillar, PromptIntent, ReadinessLevel, Status } from "../api/types";

export type Locale = "en" | "fr";

export interface Dict {
  localeName: string; // shown in the language selector

  nav: {
    tagline: string;
    analyse: string;
    configuration: string;
    overview: string;
    report: string;
    plan: string;
    citation: string;
    asoReadiness: string;
    history: string;
    rankTracking: string;
    promptSet: string;
    competitors: string;
    keys: string;
    soon: string;
  };

  asoPage: {
    title: string;
    subtitle: string;
    criteriaTitle: string;
  };

  rankTracking: {
    title: string;
    subtitle: string;
    noData: string;
    noKey: string;
    avgPosition: string;
    ctr: string;
    clicks: string;
    impressions: string;
    dateRange: (days: number) => string;
    table: {
      keyword: string;
      position: string;
      clicks: string;
      impressions: string;
      ctr: string;
    };
  };

  status: { mode: string; sub: string };

  topbar: {
    overviewTitle: string;
    overviewSubtitle: string;
    lastAudit: (when: string) => string;
    runAudit: string;
  };

  home: {
    newAudit: string;
    tagline: (pillars: string) => string;
    placeholder: string;
    audit: string;
    auditing: string;
    errorBackend: string;
    errorStatus: (status: number, message: string) => string;
    progress: string;
    queuedWorker: string;
    costFree: string;
    costEstimate: (usd: number) => string;
    costBreakdownTitle: string;
    costNotConfigured: string;
    costCalls: (calls: number, unit: number) => string;
  };

  report: {
    scoreGlobal: string;
    summary: (measured: number, applicable: number, notMeasured: number) => string;
    statCriteria: string;
    statDuration: string;
    statIssues: string;
    statCoverage: string;
    statPages: string;
    issuesTitle: string;
    issuesSub: string;
    noIssues: string;
    spectrum: string;
    downloadPdf: string;
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
    colMeasured: string;
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

  citationTrack: {
    title: string;
    subtitle: string;
    domainLabel: string;
    brandLabel: string;
    brandPlaceholder: string;
    competitorsLabel: string;
    competitorsPlaceholder: string;
    run: string;
    running: string;
    noKeys: string;
    citationRate: string;
    mentionRate: string;
    confidence: string;
    shareOfVoice: string;
    avgPosition: string;
    engines: string;
    prompts: string;
    repetitions: string;
    perEngine: string;
    colEngine: string;
    colCitationRate: string;
    colMentionRate: string;
    colAvgPos: string;
    na: string;
    errorRun: string;
  };

  keys: {
    title: string;
    subtitle: string;
    noEncryption: string;
    save: string;
    saving: string;
    delete: string;
    placeholder: string;
    placeholderJson: string;
    source: Record<KeySource, string>;
    connectorDesc: Record<string, string>;
    connectorDeprecated: Record<string, string>;
    connectorGroups: Record<string, string>;
    getKey: string;
    saved: string;
    deleted: string;
    errorSave: string;
    errorDelete: string;
  };

  promptSetPage: {
    title: string;
    subtitle: string;
    noData: string;
    themeProfile: string;
    brand: string;
    contentType: string;
    topics: string;
    entities: string;
    none: string;
    prompts: string;
    promptCount: (n: number) => string;
    colIntent: string;
    colText: string;
    colQuality: string;
    contentTypes: Record<string, string>;
    intents: Record<PromptIntent, string>;
  };

  pillar: { measured: string; excluded: string };
  issue: {
    effort: (n: number) => string;
    prio: (n: number) => string;
    crossPlatformHintTitle: string;
    crossPlatformHintDetection: string;
    crossPlatformHintPlatforms: string[];
  };

  tracking: {
    markDone: string;
    markUndone: string;
    doneOn: (date: string) => string;
    regressedOn: (date: string) => string;
    addProof: string;
    proofUrlPlaceholder: string;
    proofFile: string;
    fileTooBig: string;
  };

  durationSeconds: (s: number) => string;
  durationMinutes: (m: number, s: number) => string;
}
