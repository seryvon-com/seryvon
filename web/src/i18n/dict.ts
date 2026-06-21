// Seryvon — i18n dictionary contract. AGPL-3.0-or-later.
//
// English is the base locale; French is kept as a ready second locale. Dynamic
// strings are functions so each locale controls its own interpolation/plurals.

import type { CoverageLabel, Pillar, ReadinessLevel } from "../api/types";

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

  pillarFull: Record<Pillar, string>;
  coverage: Record<CoverageLabel, string>;
  readiness: Record<ReadinessLevel, string>;

  aso: {
    kicker: string;
    score: (n: number) => string;
    blurbLead: string;
    blurbStrong: string;
    webmcpPresent: string;
    webmcpAbsent: (endpoints: number) => string;
  };

  pillar: { measured: string; excluded: string };
  issue: { effort: (n: number) => string; prio: (n: number) => string };

  durationSeconds: (s: number) => string;
  durationMinutes: (m: number, s: number) => string;
}
