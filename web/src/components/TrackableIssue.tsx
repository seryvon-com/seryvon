// Seryvon — trackable issue card (done toggle, date, proof attachments). AGPL-3.0-or-later.

import { useRef, useState } from "react";
import type { Issue } from "../api/types";
import { useI18n } from "../i18n";
import type { IssueTracking, ProofItem } from "../hooks/useIssueTracking";
import { MAX_FILE_BYTES } from "../hooks/useIssueTracking";

interface Props {
  issue: Issue;
  tracking: IssueTracking;
  currentAuditId?: string;
  onToggle: () => void;
  onSetDate: (date: string) => void;
  onAddProof: (proof: ProofItem) => void;
  onRemoveProof: (id: string) => void;
}

function ProofThumb({
  proof,
  onRemove,
}: {
  proof: ProofItem;
  onRemove: () => void;
}) {
  const [hovered, setHovered] = useState(false);

  const inner =
    proof.type === "image" && proof.dataUrl ? (
      <img src={proof.dataUrl} alt={proof.name ?? "proof"} className="proof-img" />
    ) : proof.type === "pdf" ? (
      <div className="proof-pdf">
        <span className="proof-pdf-icon">PDF</span>
        <span className="proof-pdf-name">{proof.name ?? "document.pdf"}</span>
      </div>
    ) : (
      <div className="proof-url">
        <span className="proof-url-icon">🔗</span>
        <span className="proof-url-name">
          {(() => {
            try {
              return new URL(proof.url ?? "").hostname;
            } catch {
              return proof.name ?? proof.url ?? "link";
            }
          })()}
        </span>
      </div>
    );

  return (
    <div
      className="proof-thumb"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={() => {
        if (proof.type === "url" && proof.url) window.open(proof.url, "_blank");
        else if (proof.dataUrl) {
          const w = window.open();
          if (w) w.document.write(`<img src="${proof.dataUrl}" style="max-width:100%">`);
        }
      }}
      title={proof.name ?? proof.url ?? ""}
    >
      {inner}
      {hovered && (
        <button
          className="proof-remove"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
        >
          ×
        </button>
      )}
    </div>
  );
}

export function TrackableIssue({
  issue,
  tracking,
  currentAuditId,
  onToggle,
  onSetDate,
  onAddProof,
  onRemoveProof,
}: Props) {
  const { t } = useI18n();
  const { done, doneAt, doneInAuditId, proofs } = tracking;
  const regressed =
    done &&
    doneInAuditId !== undefined &&
    currentAuditId !== undefined &&
    doneInAuditId !== currentAuditId;
  const [proofOpen, setProofOpen] = useState(false);
  const [urlInput, setUrlInput] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const showBottom = done || proofs.length > 0 || proofOpen;

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > MAX_FILE_BYTES) {
      alert(t.tracking.fileTooBig);
      e.target.value = "";
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      onAddProof({
        id: crypto.randomUUID(),
        type: file.type === "application/pdf" ? "pdf" : "image",
        dataUrl: reader.result as string,
        name: file.name,
      });
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  }

  function handleAddUrl() {
    const raw = urlInput.trim();
    if (!raw) return;
    const href = raw.startsWith("http") ? raw : `https://${raw}`;
    onAddProof({
      id: crypto.randomUUID(),
      type: "url",
      url: href,
      name: href,
    });
    setUrlInput("");
  }

  return (
    <div className={`issue trackable${done ? " done" : ""}${regressed ? " regressed" : ""}`}>
      {/* ── top row ── */}
      <div className="issue-top-row">
        <button
          className={`track-check${done ? " checked" : ""}`}
          onClick={onToggle}
          title={done ? t.tracking.markUndone : t.tracking.markDone}
          aria-label={done ? t.tracking.markUndone : t.tracking.markDone}
        >
          {done && (
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
              <path d="M1.5 5l2.5 2.5 4.5-4.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
        </button>

        <span className="bucket">{issue.priority_bucket}</span>

        <div className="grow">
          <div className="label">{issue.recommendation || issue.criterion_key}</div>
          {issue.explanation && (
            <div className="issue-explanation">{issue.explanation}</div>
          )}
          <div className="key">{issue.criterion_key}</div>
        </div>

        <span className={`sev ${issue.severity}`}>{issue.severity}</span>

        <div style={{ textAlign: "right", minWidth: 84 }}>
          <div style={{ fontSize: 10, color: "var(--c-text-faint)", fontFamily: "var(--font-mono)" }}>
            {t.issue.effort(issue.effort)}
          </div>
          <div style={{ fontSize: 11, color: "var(--c-text-muted)", marginTop: 2 }}>
            {t.issue.prio(issue.priority_score)}
          </div>
        </div>

        {/* attach button — always in top row */}
        <button
          className={`attach-btn${proofOpen ? " active" : ""}`}
          onClick={() => setProofOpen((o) => !o)}
          title={t.tracking.addProof}
          aria-label={t.tracking.addProof}
        >
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
            <path d="M10.5 6.5H6.5V2.5M6.5 6.5H2.5M6.5 6.5V10.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </button>
      </div>

      {/* ── affected pages ── */}
      {issue.affected_pages.length > 0 && (
        <div className="issue-affected-pages">
          {issue.affected_pages.slice(0, 5).map((p) => (
            <span key={p} className="issue-page-chip" title={p}>
              {p}
            </span>
          ))}
          {issue.affected_pages.length > 5 && (
            <span className="issue-page-chip issue-page-more">
              +{issue.affected_pages.length - 5}
            </span>
          )}
        </div>
      )}

      {/* ── bottom strip (done state + proofs) ── */}
      {showBottom && (
        <div className="issue-bottom">
          {regressed && doneAt && (
            <span className="regression-badge" title={t.tracking.regressedOn(doneAt)}>
              ⚠ {t.tracking.regressedOn(doneAt)}
            </span>
          )}
          {done && !regressed && (
            <input
              type="date"
              className="done-date-input"
              value={doneAt ?? ""}
              onChange={(e) => onSetDate(e.target.value)}
              title={t.tracking.doneOn(doneAt ?? "")}
            />
          )}

          {proofs.map((proof) => (
            <ProofThumb
              key={proof.id}
              proof={proof}
              onRemove={() => onRemoveProof(proof.id)}
            />
          ))}

          {proofOpen && (
            <div className="proof-input-row">
              <input
                type="text"
                className="proof-url-input"
                placeholder={t.tracking.proofUrlPlaceholder}
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAddUrl()}
                autoFocus
              />
              <button className="proof-confirm-btn" onClick={handleAddUrl} title="Add URL">
                ↵
              </button>
              <button
                className="proof-file-btn"
                onClick={() => fileRef.current?.click()}
                title={t.tracking.proofFile}
              >
                📎
              </button>
              <input
                ref={fileRef}
                type="file"
                accept="image/*,.pdf"
                style={{ display: "none" }}
                onChange={handleFile}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
