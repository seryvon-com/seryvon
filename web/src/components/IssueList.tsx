// Seryvon — prioritized action plan (PRISM). AGPL-3.0-or-later.

import type { Issue } from "../api/types";

export function IssueList({ issues }: { issues: Issue[] }) {
  if (issues.length === 0) {
    return (
      <div className="notice">
        Aucune action prioritaire — tous les critères mesurés sont au vert.
      </div>
    );
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
              EFFORT {issue.effort}/3
            </div>
            <div style={{ fontSize: 11, color: "var(--c-text-muted)", marginTop: 2 }}>
              prio {issue.priority_score.toFixed(1)}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
