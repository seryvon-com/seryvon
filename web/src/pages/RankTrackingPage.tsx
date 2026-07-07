// Seryvon — Rank Tracking page: GSC keyword positions (M10). AGPL-3.0-or-later.

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { AppShell } from "../components/AppShell";
import type {
  AuditReport,
  GscComparison,
  GscPage,
  GscQuery,
  GscResult,
} from "../api/types";
import { useI18n } from "../i18n";

function extractGscData(report: AuditReport): GscResult | null {
  const criterion = report.criteria.find((c) => c.key === "seo.avg_position");
  if (!criterion || !criterion.raw_value) return null;
  const rv = criterion.raw_value as Record<string, unknown>;
  if (rv.avg_position === null || rv.avg_position === undefined) return null;
  return {
    queries: (rv.queries as GscQuery[] | undefined) ?? [],
    pages: (rv.pages as GscPage[] | undefined) ?? [],
    total_clicks: (rv.total_clicks as number) ?? 0,
    total_impressions: (rv.total_impressions as number) ?? 0,
    avg_ctr: (rv.avg_ctr as number) ?? 0,
    avg_position: rv.avg_position as number,
    date_range_days: (rv.date_range_days as number) ?? 90,
    comparison: (rv.comparison as GscComparison | null | undefined) ?? null,
  };
}

/** Signed delta chip. `lowerIsBetter` flips the color logic (position). */
function DeltaChip({
  value,
  lowerIsBetter = false,
  format = (n) => n.toLocaleString(),
}: {
  value: number | null;
  lowerIsBetter?: boolean;
  format?: (n: number) => string;
}) {
  if (value === null || value === 0) {
    return <span className="delta-chip neutral">±0</span>;
  }
  const improved = lowerIsBetter ? value < 0 : value > 0;
  const arrow = value > 0 ? "▲" : "▼";
  const sign = value > 0 ? "+" : "−";
  return (
    <span className={`delta-chip ${improved ? "up" : "down"}`}>
      {arrow} {sign}
      {format(Math.abs(value))}
    </span>
  );
}

function StatCard({
  label,
  value,
  delta,
}: {
  label: string;
  value: string;
  delta?: ReactNode;
}) {
  return (
    <div className="stat-card">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
      {delta && <div className="stat-delta">{delta}</div>}
    </div>
  );
}

function ComparisonBanner({ cmp }: { cmp: GscComparison }) {
  const { t } = useI18n();
  const rt = t.rankTracking;
  return (
    <div className="section-header">
      <span className="kicker">{rt.comparison.title(cmp.period_days)}</span>
    </div>
  );
}

type SortDir = "asc" | "desc";

interface SortColumn<T> {
  id: string;
  label: string;
  value: (row: T) => number | string;
  render: (row: T) => ReactNode;
  cellClassName?: string;
}

function SortArrows({ active, dir }: { active: boolean; dir: SortDir }) {
  return (
    <span className="sort-arrows" aria-hidden="true">
      <span className={active && dir === "asc" ? "on" : ""}>▲</span>
      <span className={active && dir === "desc" ? "on" : ""}>▼</span>
    </span>
  );
}

/** Generic client-side sortable table. Numeric columns sort numerically. */
function SortableTable<T>({
  rows,
  columns,
  initialSortId,
  rowKey,
  searchAccessor,
  searchPlaceholder,
}: {
  rows: T[];
  columns: SortColumn<T>[];
  initialSortId: string;
  rowKey: (row: T) => string;
  /** When provided, renders a search box filtering on this row text. */
  searchAccessor?: (row: T) => string;
  searchPlaceholder?: string;
}) {
  const [sortId, setSortId] = useState(initialSortId);
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q || !searchAccessor) return rows;
    return rows.filter((r) => searchAccessor(r).toLowerCase().includes(q));
  }, [rows, query, searchAccessor]);

  const sorted = useMemo(() => {
    const col = columns.find((c) => c.id === sortId);
    if (!col) return filtered;
    const dir = sortDir === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => {
      const va = col.value(a);
      const vb = col.value(b);
      if (typeof va === "number" && typeof vb === "number") return (va - vb) * dir;
      return String(va).localeCompare(String(vb)) * dir;
    });
  }, [filtered, columns, sortId, sortDir]);

  function toggle(id: string) {
    if (id === sortId) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortId(id);
      setSortDir("desc");
    }
  }

  return (
    <>
      {searchAccessor && (
        <div className="table-search">
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={searchPlaceholder}
            aria-label={searchPlaceholder}
          />
          <span className="table-search-count">{sorted.length}</span>
        </div>
      )}
      <table className="data-table sortable">
        <thead>
        <tr>
          {columns.map((col) => {
            const active = col.id === sortId;
            return (
              <th
                key={col.id}
                onClick={() => toggle(col.id)}
                aria-sort={active ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
              >
                <span className="th-inner">
                  {col.label}
                  <SortArrows active={active} dir={sortDir} />
                </span>
              </th>
            );
          })}
        </tr>
      </thead>
      <tbody>
        {sorted.map((row) => (
          <tr key={rowKey(row)}>
            {columns.map((col) => (
              <td key={col.id} className={col.cellClassName}>
                {col.render(row)}
              </td>
            ))}
          </tr>
        ))}
        </tbody>
      </table>
    </>
  );
}

const PERIOD_PRESETS = [7, 28, 90];

/** Look-back period selector: preset chips + free numeric input (1–480 days). */
function PeriodSelector({
  days,
  loading,
  onApply,
}: {
  days: number;
  loading: boolean;
  onApply: (days: number) => void;
}) {
  const { t } = useI18n();
  const p = t.rankTracking.period;
  const [custom, setCustom] = useState(String(days));

  return (
    <div className="period-selector">
      <span className="period-label">{p.label}</span>
      <div className="period-presets">
        {PERIOD_PRESETS.map((d) => (
          <button
            key={d}
            type="button"
            className={`period-chip ${d === days ? "active" : ""}`}
            onClick={() => onApply(d)}
            disabled={loading}
          >
            {p.days(d)}
          </button>
        ))}
      </div>
      <form
        className="period-custom"
        onSubmit={(e) => {
          e.preventDefault();
          const n = Number(custom);
          if (Number.isFinite(n)) onApply(n);
        }}
      >
        <input
          type="number"
          min={1}
          max={480}
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
          disabled={loading}
          aria-label={p.label}
        />
        <button type="submit" className="btn-ghost btn-sm" disabled={loading}>
          {loading ? p.updating : p.apply}
        </button>
      </form>
    </div>
  );
}

function RankTrackingView({ gsc: initialGsc, auditId }: { gsc: GscResult; auditId: string }) {
  const { t } = useI18n();
  const rt = t.rankTracking;
  const [gsc, setGsc] = useState(initialGsc);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function applyPeriod(next: number) {
    const d = Math.min(480, Math.max(1, Math.round(next)));
    setLoading(true);
    setError(null);
    try {
      setGsc(await api.getRankTracking(auditId, d));
    } catch {
      setError(rt.period.error);
    } finally {
      setLoading(false);
    }
  }

  const ctrPct = (gsc.avg_ctr * 100).toFixed(1);
  const cmp = gsc.comparison;

  return (
    <div className="rank-tracking">
      <div className="rank-tracking-toolbar">
        <div className="section-header">
          <span className="kicker">{rt.dateRange(gsc.date_range_days)}</span>
        </div>
        <PeriodSelector days={gsc.date_range_days} loading={loading} onApply={applyPeriod} />
      </div>

      {error && <div className="notice error">{error}</div>}
      {cmp && <ComparisonBanner cmp={cmp} />}

      <div className="stat-row">
        <StatCard
          label={rt.avgPosition}
          value={gsc.avg_position !== null ? String(gsc.avg_position) : "—"}
          delta={
            cmp ? (
              <DeltaChip
                value={cmp.position_delta}
                lowerIsBetter
                format={(n) => n.toFixed(1)}
              />
            ) : undefined
          }
        />
        <StatCard
          label={rt.ctr}
          value={`${ctrPct}%`}
          delta={
            cmp ? (
              <DeltaChip value={cmp.ctr_delta} format={(n) => `${(n * 100).toFixed(2)}pt`} />
            ) : undefined
          }
        />
        <StatCard
          label={rt.clicks}
          value={gsc.total_clicks.toLocaleString()}
          delta={cmp ? <DeltaChip value={cmp.clicks_delta} /> : undefined}
        />
        <StatCard
          label={rt.impressions}
          value={gsc.total_impressions.toLocaleString()}
          delta={cmp ? <DeltaChip value={cmp.impressions_delta} /> : undefined}
        />
      </div>

      {gsc.queries.length > 0 && (
        <>
          <div className="section-header">
            <span className="kicker">{rt.queriesTitle}</span>
          </div>
          <SortableTable
            rows={gsc.queries}
            initialSortId="clicks"
            rowKey={(q) => q.query}
            searchAccessor={(q) => q.query}
            searchPlaceholder={rt.filter.keyword}
            columns={[
              {
                id: "keyword",
                label: rt.table.keyword,
                value: (q) => q.query,
                render: (q) => q.query,
              },
              {
                id: "position",
                label: rt.table.position,
                value: (q) => q.position,
                render: (q) => q.position.toFixed(1),
              },
              {
                id: "clicks",
                label: rt.table.clicks,
                value: (q) => q.clicks,
                render: (q) => q.clicks.toLocaleString(),
              },
              {
                id: "impressions",
                label: rt.table.impressions,
                value: (q) => q.impressions,
                render: (q) => q.impressions.toLocaleString(),
              },
              {
                id: "ctr",
                label: rt.table.ctr,
                value: (q) => q.ctr,
                render: (q) => `${(q.ctr * 100).toFixed(1)}%`,
              },
            ]}
          />
        </>
      )}

      {gsc.pages.length > 0 && (
        <>
          <div className="section-header">
            <span className="kicker">{rt.pagesTitle}</span>
          </div>
          <SortableTable
            rows={gsc.pages}
            initialSortId="clicks"
            rowKey={(p) => p.page}
            searchAccessor={(p) => p.page}
            searchPlaceholder={rt.filter.page}
            columns={[
              {
                id: "page",
                label: rt.table.page,
                value: (p) => p.page,
                render: (p) => p.page,
                cellClassName: "cell-url",
              },
              {
                id: "position",
                label: rt.table.position,
                value: (p) => p.position,
                render: (p) => p.position.toFixed(1),
              },
              {
                id: "clicks",
                label: rt.table.clicks,
                value: (p) => p.clicks,
                render: (p) => p.clicks.toLocaleString(),
              },
              {
                id: "impressions",
                label: rt.table.impressions,
                value: (p) => p.impressions,
                render: (p) => p.impressions.toLocaleString(),
              },
              {
                id: "ctr",
                label: rt.table.ctr,
                value: (p) => p.ctr,
                render: (p) => `${(p.ctr * 100).toFixed(1)}%`,
              },
            ]}
          />
        </>
      )}
    </div>
  );
}

export function RankTrackingPage() {
  const { auditId } = useParams<{ auditId: string }>();
  const { t, formatDate } = useI18n();
  const navigate = useNavigate();
  const [report, setReport] = useState<AuditReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!auditId) return;
    let active = true;
    setReport(null);
    setError(null);
    api
      .getAudit(auditId)
      .then((r) => {
        if (active) setReport(r);
      })
      .catch((err) => {
        if (active)
          setError(
            err instanceof ApiError ? t.report.notFound(err.status) : t.report.loadError,
          );
      });
    return () => {
      active = false;
    };
  }, [auditId, t]);

  const gsc = report ? extractGscData(report) : null;

  return (
    <AppShell
      domain={report?.domain}
      lastAudit={report ? formatDate(report.started_at) : undefined}
      auditId={auditId}
      active="rankTracking"
      title={t.rankTracking.title}
      subtitle={t.rankTracking.subtitle}
    >
      {error && <div className="notice error">{error}</div>}
      {!error && !report && <div className="notice">{t.report.loading}</div>}
      {report && !gsc && (
        <div className="notice">
          <p>{t.rankTracking.noData}</p>
          <p>{t.rankTracking.noKey}</p>
          <button className="btn" onClick={() => navigate("/")}>
            {t.topbar.runAudit}
          </button>
        </div>
      )}
      {report && gsc && auditId && <RankTrackingView gsc={gsc} auditId={auditId} />}
    </AppShell>
  );
}
