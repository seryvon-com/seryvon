// Seryvon — crawled pages explorer. AGPL-3.0-or-later.

import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { InfoButton } from "./CriterionHint";
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
  const label = mode === "csr" ? "CSR" : mode === "ssr" ? "SSR" : mode.toUpperCase();
  const bg = mode === "csr" ? "rgba(108,143,255,0.15)" : "rgba(60,200,120,0.12)";
  const color = mode === "csr" ? "var(--c-accent)" : "var(--c-ok)";
  return (
    <span style={{ fontSize: 10, padding: "1px 5px", borderRadius: 4, background: bg, color, fontFamily: "monospace", fontWeight: 600 }}>
      {label}
    </span>
  );
}

function jsDelta(p: PageRow): number | null {
  if (p.raw_word_count == null || p.rendered_word_count == null) return null;
  return p.rendered_word_count - p.raw_word_count;
}

const CSV_HEADERS = [
  "url",
  "http",
  "rendu",
  "mots",
  "delta_js",
  "alt_manquants",
  "alt_total",
  "svg_sans_nom",
  "svg_total",
  "forms",
];

function csvRow(p: PageRow): string[] {
  return [
    p.url,
    p.status_code != null ? String(p.status_code) : "",
    p.render_mode ?? "",
    p.word_count != null ? String(p.word_count) : "",
    jsDelta(p) != null ? String(jsDelta(p)) : "",
    p.images_missing_alt != null ? String(p.images_missing_alt) : "",
    p.images_total != null ? String(p.images_total) : "",
    p.svg_missing_name != null ? String(p.svg_missing_name) : "",
    p.svg_total != null ? String(p.svg_total) : "",
    p.agent_usable_forms != null ? String(p.agent_usable_forms) : "",
  ];
}

function downloadPagesCsv(pages: PageRow[]) {
  const rows = [CSV_HEADERS, ...pages.map(csvRow)];
  const csv = rows.map((r) => r.map((cell) => `"${cell.replace(/"/g, '""')}"`).join(",")).join("\n");
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
  const href = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = href;
  a.download = "pages_crawlees.csv";
  a.click();
  URL.revokeObjectURL(href);
}

type SortKey =
  | "url"
  | "status_code"
  | "render_mode"
  | "word_count"
  | "js_delta"
  | "images_missing_alt"
  | "svg_missing_name"
  | "agent_usable_forms";
type SortDir = "asc" | "desc";

const COLUMNS: { key: SortKey; label: string; hint?: string }[] = [
  { key: "url", label: "URL", hint: "URL finale de la page après redirections éventuelles." },
  {
    key: "status_code",
    label: "HTTP",
    hint: "Code de statut HTTP renvoyé par le serveur lors du crawl (200 = OK, 3xx = redirection, 4xx/5xx = erreur).",
  },
  {
    key: "render_mode",
    label: "Rendu",
    hint: "SSR : le contenu est déjà présent dans le HTML brut. CSR : une part significative du contenu n'apparaît qu'après exécution du JavaScript (détection Playwright, comparaison DOM avant/après JS).",
  },
  {
    key: "word_count",
    label: "Mots",
    hint: "Nombre de mots extraits de la page telle que scorée (HTML rendu par Playwright si disponible, sinon HTML brut).",
  },
  {
    key: "js_delta",
    label: "Delta JS",
    hint: "Mots ajoutés par le JavaScript (mots après rendu − mots dans le HTML brut). Un écart important indique du contenu invisible pour un crawler qui n'exécute pas le JS.",
  },
  {
    key: "images_missing_alt",
    label: "Alt",
    hint: "Nombre d'images avec un attribut alt, sur le total d'images de la page.",
  },
  {
    key: "svg_missing_name",
    label: "SVG",
    hint: "Nombre de <svg> de contenu avec un nom accessible (title/aria-label), sur le total de <svg> de contenu de la page. Exclut les icônes décoratives et celles déjà couvertes par le texte d'un bouton/lien parent.",
  },
  {
    key: "agent_usable_forms",
    label: "Forms",
    hint: "Formulaires exploitables par un agent IA : action/method définis, champs avec label ou aria-label.",
  },
];

function sortValue(p: PageRow, key: SortKey): number | string {
  switch (key) {
    case "url":
      return p.url;
    case "status_code":
      return p.status_code ?? -1;
    case "render_mode":
      return p.render_mode ?? "";
    case "word_count":
      return p.word_count ?? -1;
    case "js_delta":
      return jsDelta(p) ?? -1;
    case "images_missing_alt":
      return p.images_missing_alt ?? -1;
    case "svg_missing_name":
      return p.svg_missing_name ?? -1;
    case "agent_usable_forms":
      return p.agent_usable_forms ?? -1;
  }
}

export function CrawledPages({ auditId }: { auditId: string }) {
  const [pages, setPages] = useState<PageRow[] | null>(null);
  const [filter, setFilter] = useState("");
  const [expanded, setExpanded] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  useEffect(() => {
    let active = true;
    api.getAuditPages(auditId).then((p) => { if (active) setPages(p); }).catch(() => {});
    return () => { active = false; };
  }, [auditId]);

  const query = filter.trim().toLowerCase();

  const sorted = useMemo(() => {
    if (!pages) return [];
    const base = query ? pages.filter((p) => p.url.toLowerCase().includes(query)) : pages;
    if (!sortKey) return base;
    const dir = sortDir === "asc" ? 1 : -1;
    return [...base].sort((a, b) => {
      const va = sortValue(a, sortKey);
      const vb = sortValue(b, sortKey);
      if (va < vb) return -1 * dir;
      if (va > vb) return 1 * dir;
      return 0;
    });
  }, [pages, query, sortKey, sortDir]);

  if (!pages) return null;

  const visible = expanded ? sorted : sorted.slice(0, 50);

  const formsTotal = pages.reduce((s, p) => s + (p.agent_usable_forms ?? 0), 0);
  const imgMissing = pages.reduce((s, p) => s + (p.images_missing_alt ?? 0), 0);
  const imgTotal = pages.reduce((s, p) => s + (p.images_total ?? 0), 0);
  const csrPages = pages.filter((p) => p.render_mode === "csr").length;

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  return (
    <section className="crawled-pages-section">
      <div className="section-head">
        <h3 style={{ margin: 0 }}>Pages crawlées</h3>
        <span className="crawled-pages-count">{pages.length}</span>
        <button
          className="btn btn-ghost btn-sm crawled-pages-export"
          onClick={() => downloadPagesCsv(sorted)}
          title={`Exporter ${sorted.length} page(s) au format Excel (CSV)`}
        >
          ↓ Export Excel
        </button>
      </div>

      <div className="crawled-pages-stats">
        <div className="cp-stat">
          <span className="cp-stat-val">{csrPages}</span>
          <span className="cp-stat-cap">rendues JS (CSR)</span>
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
              {COLUMNS.map((col) => {
                const active = sortKey === col.key;
                return (
                  <th
                    key={col.key}
                    onClick={() => toggleSort(col.key)}
                    style={{ cursor: "pointer", userSelect: "none" }}
                    aria-sort={active ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
                  >
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 3 }}>
                      {col.label}
                      <span
                        style={{
                          display: "inline-flex",
                          flexDirection: "column",
                          lineHeight: "6px",
                          fontSize: 7,
                          marginLeft: 1,
                        }}
                        aria-hidden="true"
                      >
                        <span style={{ color: active && sortDir === "asc" ? "var(--c-accent)" : "var(--c-text-faint)" }}>▲</span>
                        <span style={{ color: active && sortDir === "desc" ? "var(--c-accent)" : "var(--c-text-faint)" }}>▼</span>
                      </span>
                      {col.hint && (
                        <span onClick={(e) => e.stopPropagation()} style={{ cursor: "default" }}>
                          <InfoButton label={`${col.label} — aide`} minWidth={220}>
                            <div style={{ fontSize: "0.72rem", color: "var(--c-text-muted)", lineHeight: 1.4, whiteSpace: "normal" }}>
                              {col.hint}
                            </div>
                          </InfoButton>
                        </span>
                      )}
                    </span>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {visible.map((p) => {
              const delta = jsDelta(p);
              return (
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
                  <td
                    className="cp-num"
                    style={{ color: delta != null && delta > 0 ? "var(--c-warn, #e8a94d)" : "var(--c-text-faint)" }}
                    title={
                      p.raw_word_count != null && p.rendered_word_count != null
                        ? `${p.raw_word_count} mots bruts → ${p.rendered_word_count} après JS`
                        : undefined
                    }
                  >
                    {delta != null ? (delta > 0 ? `+${delta}` : delta) : "—"}
                  </td>
                  <td className="cp-num" style={{ color: (p.images_missing_alt ?? 0) > 0 ? "var(--c-error)" : undefined }}>
                    {p.images_missing_alt != null && p.images_total != null
                      ? `${p.images_total - p.images_missing_alt}/${p.images_total}`
                      : "—"}
                  </td>
                  <td className="cp-num" style={{ color: (p.svg_missing_name ?? 0) > 0 ? "var(--c-error)" : undefined }}>
                    {p.svg_missing_name != null && p.svg_total != null
                      ? `${p.svg_total - p.svg_missing_name}/${p.svg_total}`
                      : "—"}
                  </td>
                  <td className="cp-num" style={{ color: (p.agent_usable_forms ?? 0) > 0 ? "var(--c-ok)" : "var(--c-text-faint)" }}>
                    {p.agent_usable_forms ?? "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {sorted.length > 50 && (
        <button className="crawled-pages-more" onClick={() => setExpanded((v) => !v)}>
          {expanded ? `Réduire` : `Voir les ${sorted.length - 50} autres pages`}
        </button>
      )}
    </section>
  );
}
