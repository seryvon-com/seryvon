// Seryvon — app shell: PRISM sidebar + topbar. AGPL-3.0-or-later.

import type { ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";

interface NavItem {
  label: string;
  active?: boolean;
  soon?: boolean;
}

const NAV_MAIN: NavItem[] = [
  { label: "Vue d'ensemble", active: true },
  { label: "Rapport d'audit", soon: true },
  { label: "Plan d'action", soon: true },
  { label: "Citation Tracking", soon: true },
  { label: "Readiness ASO", soon: true },
  { label: "Historique", soon: true },
];

const NAV_CONFIG: NavItem[] = [
  { label: "Prompt Set", soon: true },
  { label: "Concurrents", soon: true },
  { label: "Clés & BYOK", soon: true },
];

interface Props {
  title: string;
  subtitle?: string;
  domain?: string;
  lastAudit?: string;
  children: ReactNode;
}

export function AppShell({ title, subtitle, domain, lastAudit, children }: Props) {
  const navigate = useNavigate();
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

        <div className="group-label">ANALYSE</div>
        <nav>
          {NAV_MAIN.map((it) => (
            <NavButton key={it.label} item={it} />
          ))}
        </nav>

        <div className="group-label">CONFIGURATION</div>
        <nav>
          {NAV_CONFIG.map((it) => (
            <NavButton key={it.label} item={it} />
          ))}
        </nav>

        <div className="status-card">
          <div className="row">
            <span className="dot" />
            <span className="label">Mode 100 % gratuit + BYOK</span>
          </div>
          <div className="sub">Scoring déterministe · traçable</div>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div style={{ minWidth: 0 }}>
            <h1>{title}</h1>
            {subtitle && <div className="subtitle">{subtitle}</div>}
          </div>
          <div className="actions">
            {domain && (
              <span className="domain-chip">
                <span className="prism-mark mark" />
                {domain}
              </span>
            )}
            {lastAudit && (
              <span className="audit-pill">
                <span className="dot" />
                <span>Dernier audit · {lastAudit}</span>
              </span>
            )}
            <button className="btn" onClick={() => navigate("/")}>
              Lancer un audit
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

function NavButton({ item }: { item: NavItem }) {
  const cls = ["nav-item", item.active ? "active" : "", item.soon ? "disabled" : ""]
    .filter(Boolean)
    .join(" ");
  return (
    <button className={cls} disabled={item.soon} type="button">
      <span style={{ flex: 1 }}>{item.label}</span>
      {item.soon && <span className="badge-soon">bientôt</span>}
    </button>
  );
}
