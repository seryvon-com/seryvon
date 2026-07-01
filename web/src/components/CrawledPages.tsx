// Seryvon — crawled pages explorer. AGPL-3.0-or-later.

import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { PageRow } from "../api/types";

const STATUS_COLOR: Record<string, string> = {
  "2": "var(--c-ok)",
  "3": "var(--c-warn, #e8a94d)",
  "4": "var(--c-error)",
  "5": "var(--c-error)",
};

function statusColor(code: number | null): string {
  if (code == null) return "var(--c-text-faint)";
  return STATUS_COLOR[String(code)[0]] ?? "var(--c-text-faint)";
}

function renderBadge(mode: string | null) {
  if (!mode) return null;
  const label = mode === "js" ? "JS" : mode === "static" ? "SSR" : mode.toUpperCase();
  const bg = mode === "js" ? "rgba(108,143,255,0.15)" : "rgba(60,200,120,0.12)";
  const color = mode === "js" ? "var(--c-accent)" : "var(--c-ok)";
  return (
    <span style={{ fontSize: 10, padding: "1px 5px", borderRadius: 4, background: bg, color, fontFamily: "monospace", fontWeight: 600 }}>
      {label}
    </span>
  );
}

export function CrawledPages({ auditId }: { auditId: string }) {
  const [pages, setPages] = useState<PageRow[] | null>(null);
  const [filter, setFilter] = useState("");
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    let active = true;
    api.getAuditPages(auditId).then((p) => { if (active) setPages(p); }).catch(() => {});
    return () => { active = false; };
  }, [auditId]);

  if (!pages) return null;

  const query = filter.trim().toLowerCase();
  const filtered = query ? pages.filter((p) => p.url.toLowerCase().includes(query)) : pages;
  const visible = expanded ? filtered : filtered.slice(0, 50);

  const formsTotal = pages.reduce((s, p) => s + (p.agent_usable_forms ?? 0), 0);
  const imgMissing = pages.reduce((s, p) => s + (p.images_missing_alt ?? 0), 0);
  const imgTotal = pages.reduce((s, p) => s + (p.images_total ?? 0), 0);
  const jsPages = pages.filter((p) => p.render_mode === "js").length;

  return (
    <section className="crawled-pages-section">
      <div className="section-head">
        <h3 style={{ margin: 0 }}>Pages crawlées</h3>
        <span className="crawled-pages-count">{pages.length}</span>
      </div>

      <div className="crawled-pages-stats">
        <div className="cp-stat">
          <span className="cp-stat-val">{jsPages}</span>
          <span className="cp-stat-cap">rendues JS</span>
        </div>
        <div className="cp-stat">
          <span className="cp-stat-val">{formsTotal}</span>
          <span className="cp-stat-cap">formulaires agents</span>
        </div>
        <div className="cp-stat">
          <span className="cp-stat-val" style={{ color: imgMissing > 0 ? "var(--c-error)" : "var(--c-ok)" }}>
            {imgMissing}
          </span>
          <span className="cp-stat-cap">images sans alt / {imgTotal}</span>
        </div>
      </div>

      <input
        className="crawled-pages-search"
        type="search"
        placeholder="Filtrer par URL…"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        aria-label="Filtrer les pages crawlées"
      />

      <div className="crawled-pages-table-wrap">
        <table className="crawled-pages-table">
          <thead>
            <tr>
              <th>URL</th>
              <th>HTTP</th>
              <th>Rendu</th>
              <th title="Mots">Mots</th>
              <th title="Images sans alt / total">Alt</th>
              <th title="Formulaires exploitables par un agent">Forms</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((p) => (
              <tr key={p.url} className={p.agent_usable_forms ? "cp-row has-form" : "cp-row"}>
                <td className="cp-url">
                  <a href={p.url} target="_blank" rel="noopener noreferrer" title={p.title ?? p.url}>
                    {p.url}
                  </a>
                </td>
                <td style={{ color: statusColor(p.status_code), fontFamily: "monospace", fontWeight: 600 }}>
                  {p.status_code ?? "—"}
                </td>
                <td>{renderBadge(p.render_mode)}</td>
                <td className="cp-num">{p.word_count ?? "—"}</td>
                <td className="cp-num" style={{ color: (p.images_missing_alt ?? 0) > 0 ? "var(--c-error)" : undefined }}>
                  {p.images_missing_alt != null && p.images_total != null
                    ? `${p.images_missing_alt}/${p.images_total}`
                    : "—"}
                </td>
                <td className="cp-num" style={{ color: (p.agent_usable_forms ?? 0) > 0 ? "var(--c-ok)" : "var(--c-text-faint)" }}>
                  {p.agent_usable_forms ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {filtered.length > 50 && (
        <button className="crawled-pages-more" onClick={() => setExpanded((v) => !v)}>
          {expanded ? `Réduire` : `Voir les ${filtered.length - 50} autres pages`}
        </button>
      )}
    </section>
  );
}
