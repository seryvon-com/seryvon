// Seryvon — prioritized action plan (PRISM). AGPL-3.0-or-later.

import type { Issue } from "../api/types";
import { useI18n } from "../i18n";
import { useIssueTracking } from "../hooks/useIssueTracking";
import { TrackableIssue } from "./TrackableIssue";

interface Props {
  issues: Issue[];
  auditId?: string;
  domain?: string;
}

export function IssueList({ issues, auditId, domain }: Props) {
  const { t } = useI18n();
  const { getTracking, toggleDone, setDoneAt, addProof, removeProof } =
    useIssueTracking(domain);

  if (issues.length === 0) {
    return <div className="notice">{t.report.noIssues}</div>;
  }
  return (
    <div className="issues">
      {issues.map((issue, i) => (
        <TrackableIssue
          key={`${issue.criterion_key}-${i}`}
          issue={issue}
          tracking={getTracking(issue.criterion_key)}
          currentAuditId={auditId}
          onToggle={() => auditId && toggleDone(issue.criterion_key, auditId)}
          onSetDate={(date) => setDoneAt(issue.criterion_key, date)}
          onAddProof={(proof) => addProof(issue.criterion_key, proof)}
          onRemoveProof={(id) => removeProof(issue.criterion_key, id)}
        />
      ))}
    </div>
  );
}
