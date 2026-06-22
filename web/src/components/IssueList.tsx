// Seryvon — prioritized action plan (PRISM). AGPL-3.0-or-later.

import type { Issue } from "../api/types";
import { useI18n } from "../i18n";

export function IssueList({ issues }: { issues: Issue[] }) {
  const { t } = useI18n();
  if (issues.length === 0) {
    return <div className="notice">{t.report.noIssues}</div>;
  }
  return (
    <div className="issues">
      {issues.map((issue, i) => (
        <div className="issue" key={`${issue.criterion_key}-${i}`}>
          <span className="bucket">{issue.priority_bucket}</span>
          <div className="grow">
            <div className="label">{issue.recommendation || issue.criterion_key}</div>
            <div className="key">{issue.criterion_key}</div>
          </div>
          <span className={`sev ${issue.severity}`}>{issue.severity}</span>
          <div style={{ textAlign: "right", minWidth: 84 }}>
            <div
              style={{ fontSize: 10, color: "var(--c-text-faint)", fontFamily: "var(--font-mono)" }}
            >
              {t.issue.effort(issue.effort)}
            </div>
            <div style={{ fontSize: 11, color: "var(--c-text-muted)", marginTop: 2 }}>
              {t.issue.prio(issue.priority_score)}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
