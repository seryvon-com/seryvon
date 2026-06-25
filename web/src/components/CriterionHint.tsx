// Seryvon — per-criterion info tooltips. AGPL-3.0-or-later.

import { useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useI18n } from "../i18n";

// Mirrors _PLATFORM_HOSTS in src/seryvon/crawler/extract.py
const RECOGNIZED_PLATFORMS: { key: string; label: string }[] = [
  { key: "twitter",    label: "Twitter / X" },
  { key: "linkedin",   label: "LinkedIn" },
  { key: "facebook",   label: "Facebook" },
  { key: "instagram",  label: "Instagram" },
  { key: "youtube",    label: "YouTube" },
  { key: "github",     label: "GitHub" },
  { key: "tiktok",     label: "TikTok" },
  { key: "pinterest",  label: "Pinterest" },
  { key: "mastodon",   label: "Mastodon" },
  { key: "reddit",     label: "Reddit" },
  { key: "bluesky",    label: "Bluesky" },
  { key: "threads",    label: "Threads" },
  { key: "crunchbase", label: "Crunchbase" },
];

function InfoButton({
  label,
  children,
  minWidth = 260,
}: {
  label: string;
  children: React.ReactNode;
  minWidth?: number;
}) {
  const btnRef = useRef<HTMLButtonElement>(null);
  const [rect, setRect] = useState<DOMRect | null>(null);

  function handleOpen() {
    if (btnRef.current) setRect(btnRef.current.getBoundingClientRect());
  }
  function handleClose() {
    setRect(null);
  }

  const tooltip =
    rect &&
    createPortal(
      <div
        className="cost-tooltip"
        role="tooltip"
        style={{
          position: "fixed",
          top: rect.bottom + 8,
          left: Math.max(8, Math.min(window.innerWidth - minWidth - 8, rect.left + rect.width / 2 - minWidth / 2)),
          minWidth,
          zIndex: 9999,
        }}
      >
        {children}
      </div>,
      document.body,
    );

  return (
    <span className="cost-info-wrap" style={{ position: "static" }}>
      <button
        ref={btnRef}
        className="cost-info-btn"
        aria-label={label}
        onMouseEnter={handleOpen}
        onMouseLeave={handleClose}
        onFocus={handleOpen}
        onBlur={handleClose}
        type="button"
      >
        ⓘ
      </button>
      {tooltip}
    </span>
  );
}

function CrossPlatformHint({ rawValue }: { rawValue: unknown }) {
  const { t } = useI18n();
  const h = t.criterionHints;
  const detected: string[] =
    rawValue !== null &&
    typeof rawValue === "object" &&
    "platforms" in (rawValue as object) &&
    Array.isArray((rawValue as { platforms: unknown }).platforms)
      ? ((rawValue as { platforms: string[] }).platforms)
      : [];

  return (
    <InfoButton label={h.crossPlatformTitle} minWidth={280}>
      <div className="cost-tooltip-title">{h.crossPlatformTitle}</div>
      <div style={{ fontSize: "0.74rem", color: "var(--c-text-muted)", marginBottom: 8, lineHeight: 1.4 }}>
        {h.crossPlatformDetection}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 6px" }}>
        {RECOGNIZED_PLATFORMS.map(({ key, label }) => {
          const found = detected.includes(key);
          return (
            <span
              key={key}
              title={found ? h.crossPlatformDetectedLabel : h.crossPlatformMissingLabel}
              style={{
                fontSize: "0.72rem",
                borderRadius: 4,
                padding: "1px 6px",
                background: found ? "var(--c-accent-dim, #1f3a5f)" : "var(--c-border, #30363d)",
                color: found ? "var(--c-accent, #4f9cf9)" : "var(--c-text-muted, #8b949e)",
                fontWeight: found ? 600 : 400,
              }}
            >
              {found ? "✓ " : ""}{label}
            </span>
          );
        })}
      </div>
    </InfoButton>
  );
}

function TextHint({ title, body }: { title: string; body: string }) {
  return (
    <InfoButton label={title} minWidth={300}>
      <div className="cost-tooltip-title">{title}</div>
      <div style={{ fontSize: "0.74rem", color: "var(--c-text-primary, #e6edf3)", lineHeight: 1.5 }}>
        {body}
      </div>
    </InfoButton>
  );
}

export function CriterionHint({
  criterionKey,
  rawValue,
}: {
  criterionKey: string;
  rawValue: unknown;
}) {
  const { t } = useI18n();
  const h = t.criterionHints;

  switch (criterionKey) {
    case "geo.cross_platform":
      return <CrossPlatformHint rawValue={rawValue} />;
    case "aeo.comparison_tables":
      return <TextHint title={h.comparisonTablesTitle} body={h.comparisonTablesBody} />;
    case "geo.primary_sources":
      return <TextHint title={h.primarySourcesTitle} body={h.primarySourcesBody} />;
    case "aso.mcp_readiness":
      return <TextHint title={h.mcpReadinessTitle} body={h.mcpReadinessBody} />;
    default:
      return null;
  }
}
