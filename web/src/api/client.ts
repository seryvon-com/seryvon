// Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
// Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
// Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
//
// Thin typed client over the FastAPI backend. All calls go through the /api proxy
// (see vite.config.ts) so the same code works in dev and behind a reverse proxy.

import type { Locale } from "../i18n/dict";
import type { AuditReport, AuditSummary, ComparisonMode, ComparisonResult } from "./types";

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
  return (await resp.json()) as T;
}

export const api = {
  health: () => request<{ status: string; version: string }>("/health"),

  /** Run + persist an audit, returns the full report. The locale freezes the
   *  produced-text language (explanations, recommendations) at audit time. */
  createAudit: (url: string, locale: Locale) =>
    request<AuditReport>("/audits", {
      method: "POST",
      body: JSON.stringify({ url, locale }),
    }),

  /** Reload a persisted audit report by id. */
  getAudit: (auditId: string) =>
    request<AuditReport>(`/audits/${auditId}`),

  /** Audit history for a domain, most recent first. */
  listAudits: (domain: string) =>
    request<AuditSummary[]>(`/audits?domain=${encodeURIComponent(domain)}`),

  /** Compare two persisted scorecards (M6). Defaults to descriptive mode (always allowed). */
  compareAudits: (leftRunId: string, rightRunId: string, mode: ComparisonMode = "descriptive") =>
    request<ComparisonResult>("/scorecards/compare", {
      method: "POST",
      body: JSON.stringify({ left_run_id: leftRunId, right_run_id: rightRunId, mode }),
    }),
};
