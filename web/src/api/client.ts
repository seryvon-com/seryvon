// Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
// Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
// Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
//
// Thin typed client over the FastAPI backend. All calls go through the /api proxy
// (see vite.config.ts) so the same code works in dev and behind a reverse proxy.

import type { Locale } from "../i18n/dict";
import type {
  AuditReport,
  AuditSummary,
  AuditTask,
  AuditTaskStatus,
  CitationTaskStatus,
  ComparisonMode,
  ComparisonResult,
  DomainSummary,
  KeyEntry,
  PageRow,
  PromptSet,
} from "./types";

const BASE = "/api";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = (await resp.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // non-JSON error body — keep the status text
    }
    throw new ApiError(resp.status, detail);
  }
  // 204 No Content — no body to parse.
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export const api = {
  health: () => request<{ status: string; version: string }>("/health"),

  /** Indicative cost breakdown for one audit based on active BYOK keys. */
  getAuditCostEstimate: () =>
    request<import("./types").AuditCostEstimate>("/audits/cost-estimate"),

  /** Submit an audit (async 202). Returns a task to poll with getAuditTask(). */
  createAudit: (url: string, locale: Locale) =>
    request<AuditTask>("/audits", {
      method: "POST",
      body: JSON.stringify({ url, locale }),
    }),

  /** Poll an async audit job until done/failed. */
  getAuditTask: (taskId: string) =>
    request<AuditTaskStatus>(`/audits/tasks/${taskId}`),

  /** Reload a persisted audit report by id. */
  getAudit: (auditId: string) =>
    request<AuditReport>(`/audits/${auditId}`),

  /** Audit history for a domain, most recent first. */
  listAudits: (domain: string) =>
    request<AuditSummary[]>(`/audits?domain=${encodeURIComponent(domain)}`),

  /** Every audited domain with a pointer to its latest audit (most recent first). */
  listDomains: () => request<DomainSummary[]>("/domains"),

  /** Compare two persisted scorecards (M6). Defaults to descriptive mode (always allowed). */
  compareAudits: (leftRunId: string, rightRunId: string, mode: ComparisonMode = "descriptive") =>
    request<ComparisonResult>("/scorecards/compare", {
      method: "POST",
      body: JSON.stringify({ left_run_id: leftRunId, right_run_id: rightRunId, mode }),
    }),

  /** Submit LLM citation tracking (async 202). Poll with getCitationTask(). */
  runCitations: (domain: string, brand?: string, competitors?: string[]) =>
    request<{ task_id: string; status_url: string }>("/citations", {
      method: "POST",
      body: JSON.stringify({ domain, brand: brand ?? null, competitors: competitors ?? [] }),
    }),

  /** Poll a citation-tracking job. */
  getCitationTask: (taskId: string) =>
    request<CitationTaskStatus>(`/citations/tasks/${taskId}`),

  /** Prompt set generated deterministically from the audit crawl (M4b). */
  getPromptSet: (auditId: string) => request<PromptSet>(`/audits/${auditId}/prompt-set`),

  /** All pages crawled during an audit with per-page signals. */
  getAuditPages: (auditId: string) => request<PageRow[]>(`/audits/${auditId}/pages`),

  /** Live GSC rank-tracking re-fetch over a custom look-back window (days). */
  getRankTracking: (auditId: string, days: number) =>
    request<import("./types").GscResult>(
      `/audits/${auditId}/rank-tracking?days=${encodeURIComponent(days)}`,
    ),

  /** List BYOK key statuses for all connectors (masked values only). */
  listKeys: () => request<KeyEntry[]>("/keys"),

  /** Store or update a BYOK key for a connector. */
  upsertKey: (connector: string, value: string) =>
    request<KeyEntry>(`/keys/${connector}`, {
      method: "PUT",
      body: JSON.stringify({ value }),
    }),

  /** Delete a stored BYOK key for a connector. */
  deleteKey: (connector: string) =>
    request<void>(`/keys/${connector}`, { method: "DELETE" }),
};
