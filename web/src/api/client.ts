// Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
// Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
// Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
//
// Thin typed client over the FastAPI backend. All calls go through the /api proxy
// (see vite.config.ts) so the same code works in dev and behind a reverse proxy.

import type { AuditReport, AuditSummary } from "./types";

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

  /** Run + persist an audit, returns the full report. */
  createAudit: (url: string) =>
    request<AuditReport>("/audits", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),

  /** Reload a persisted audit report by id. */
  getAudit: (auditId: string) =>
    request<AuditReport>(`/audits/${auditId}`),

  /** Audit history for a domain, most recent first. */
  listAudits: (domain: string) =>
    request<AuditSummary[]>(`/audits?domain=${encodeURIComponent(domain)}`),
};
