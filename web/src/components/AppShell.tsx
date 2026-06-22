// Seryvon — app shell: PRISM sidebar + topbar. AGPL-3.0-or-later.

import type { ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useI18n } from "../i18n";
import { LanguageSelector } from "./LanguageSelector";

interface Props {
  domain?: string;
  lastAudit?: string;
  /** Persisted audit id, enabling the Overview / Audit report nav links. */
  auditId?: string;
  /** Which primary nav entry is the current screen. */
  active?: "overview" | "report" | "plan" | "asoReadiness" | "history" | "rankTracking";
  /** Topbar heading; defaults to the Overview labels. */
  title?: string;
  subtitle?: string;
  children: ReactNode;
}

export function AppShell({
  domain,
  lastAudit,
  auditId,
  active = "overview",
  title,
  subtitle,
  children,
}: Props) {
  const navigate = useNavigate();
  const { t } = useI18n();

  const navMain = [
    {
      label: t.nav.overview,
      active: active === "overview",
      to: auditId ? `/audits/${auditId}` : undefined,
      soon: !auditId,
    },
    {
      label: t.nav.report,
      active: active === "report",
      to: auditId ? `/audits/${auditId}/report` : undefined,
      soon: !auditId,
    },
    {
      label: t.nav.plan,
      active: active === "plan",
      to: auditId ? `/audits/${auditId}/plan` : undefined,
      soon: !auditId,
    },
    { label: t.nav.citation, soon: true },
    {
      label: t.nav.asoReadiness,
      active: active === "asoReadiness",
      to: auditId ? `/audits/${auditId}/aso` : undefined,
      soon: !auditId,
    },
    {
      label: t.nav.history,
      active: active === "history",
      to: auditId ? `/audits/${auditId}/history` : undefined,
      soon: !auditId,
    },
    {
      label: t.nav.rankTracking,
      active: active === "rankTracking",
      to: auditId ? `/audits/${auditId}/rank-tracking` : undefined,
      soon: !auditId,
    },
  ];
  const navConfig = [
    { label: t.nav.promptSet, soon: true },
    { label: t.nav.competitors, soon: true },
    { label: t.nav.keys, soon: true },
  ];

  return (
    <div className="shell">
      <aside className="sidebar">
        <Link to="/" className="brand">
          <span className="prism-mark mark" />
          <div>
            <div className="name">seryvon</div>
            <div className="pillars-line">SEO · GEO · GSO · AEO · ASO</div>
          </div>
        </Link>

        <div className="group-label">{t.nav.analyse}</div>
        <nav>
          {navMain.map((it) => (
            <NavButton
              key={it.label}
              label={it.label}
              active={it.active}
              soon={it.soon}
              onClick={it.to ? () => navigate(it.to as string) : undefined}
            />
          ))}
        </nav>

        <div className="group-label">{t.nav.configuration}</div>
        <nav>
          {navConfig.map((it) => (
            <NavButton key={it.label} label={it.label} soon={it.soon} />
          ))}
        </nav>

        <div className="status-card">
          <div className="row">
            <span className="dot" />
            <span className="label">{t.status.mode}</span>
          </div>
          <div className="sub">{t.status.sub}</div>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div style={{ minWidth: 0 }}>
            <h1>{title ?? t.topbar.overviewTitle}</h1>
            <div className="subtitle">{subtitle ?? t.topbar.overviewSubtitle}</div>
          </div>
          <div className="actions">
            <LanguageSelector />
            {domain && (
              <span className="domain-chip">
                <span className="prism-mark mark" />
                {domain}
              </span>
            )}
            {lastAudit && (
              <span className="audit-pill">
                <span className="dot" />
                <span>{t.topbar.lastAudit(lastAudit)}</span>
              </span>
            )}
            <button className="btn" onClick={() => navigate("/")}>
              {t.topbar.runAudit}
            </button>
          </div>
        </header>
        <main className="content">
          <div className="canvas">{children}</div>
        </main>
      </div>
    </div>
  );
}

function NavButton({
  label,
  active,
  soon,
  onClick,
}: {
  label: string;
  active?: boolean;
  soon?: boolean;
  onClick?: () => void;
}) {
  const { t } = useI18n();
  const cls = ["nav-item", active ? "active" : "", soon ? "disabled" : ""]
    .filter(Boolean)
    .join(" ");
  return (
    <button className={cls} disabled={soon} type="button" onClick={onClick}>
      <span style={{ flex: 1 }}>{label}</span>
      {soon && <span className="badge-soon">{t.nav.soon}</span>}
    </button>
  );
}
