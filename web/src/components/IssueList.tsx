// Seryvon — prioritized action plan. AGPL-3.0-or-later.

import type { Issue } from "../api/types";

export function IssueList({ issues }: { issues: Issue[] }) {
  if (issues.length === 0) {
    return <div className="notice">Aucune action prioritaire — tous les critères mesurés sont au vert.</div>;
  }
  return (
    <div>
      {issues.map((issue, i) => (
        <div className="issue" key={`${issue.criterion_key}-${i}`}>
          <span className="bucket">{issue.priority_bucket}</span>
          <div>
            <div className="reco">{issue.recommendation || issue.criterion_key}</div>
            <div className="key">{issue.criterion_key}</div>
          </div>
          <span className={`badge ${issue.severity}`}>{issue.severity}</span>
        </div>
      ))}
    </div>
  );
}
