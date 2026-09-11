import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { ApiError, api } from "../api/client";
import { I18nProvider } from "../i18n";
import { AsoPage } from "./AsoPage";

it("shows the ASO loading state", () => {
  vi.spyOn(api, "getAudit").mockReturnValue(new Promise(() => {}));
  render(<MemoryRouter><I18nProvider><AsoPage /></I18nProvider></MemoryRouter>);
  expect(screen.getByText(/Loading/)).toBeInTheDocument();
});

it("shows when ASO readiness is unavailable", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z", pillars: {} } as never);
  render(<MemoryRouter initialEntries={["/audits/a1/aso"]}><I18nProvider><Routes><Route path="/audits/:auditId/aso" element={<AsoPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByText(/not computed/i)).toBeInTheDocument();
});

it("shows the not-found message for an API error", async () => {
  vi.spyOn(api, "getAudit").mockRejectedValue(new ApiError(404, "Not found"));
  render(<MemoryRouter initialEntries={["/audits/missing/aso"]}><I18nProvider><Routes><Route path="/audits/:auditId/aso" element={<AsoPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByText(/not found/i)).toBeInTheDocument();
});

it("renders ASO readiness details", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z", pillars: { aso: { score: 72 } }, aso_readiness: { readiness_level: "ready", agent_ready: true, has_webmcp: true, has_action_schema: true, has_agent_forms: false, has_openapi: false, action_signals: 2, ai_discovery_endpoints: 3, has_nlweb: true, brand_coherence_score: 88, blocked_agent_bots: ["BadBot"] } } as never);
  render(<MemoryRouter initialEntries={["/audits/a1/aso"]}><I18nProvider><Routes><Route path="/audits/:auditId/aso" element={<AsoPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByText(/3/)).toBeInTheDocument();
  expect(screen.getByText("88/100")).toBeInTheDocument();
  const agentRow = document.querySelector('tr[aria-expanded="false"]') as HTMLElement;
  fireEvent.click(agentRow);
  expect(screen.getByText(/action schema/i)).toBeInTheDocument();
});

it("renders negative and unavailable ASO readiness signals", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z", pillars: {}, aso_readiness: { readiness_level: "basic", agent_ready: false, has_webmcp: false, has_action_schema: false, has_agent_forms: false, has_openapi: false, action_signals: 0, ai_discovery_endpoints: 0, has_nlweb: false, brand_coherence_score: null, blocked_agent_bots: [] } } as never);
  render(<MemoryRouter initialEntries={["/audits/a2/aso"]}><I18nProvider><Routes><Route path="/audits/:auditId/aso" element={<AsoPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByText(/No|None|—/i)).toBeInTheDocument();
  expect(screen.getAllByText(/No|None|—/i).length).toBeGreaterThan(0);
});

it("handles a generic ASO API failure and a readiness report without a pillar score", async () => {
  vi.spyOn(api, "getAudit").mockRejectedValue(new Error("offline"));
  render(<MemoryRouter initialEntries={["/audits/a3/aso"]}><I18nProvider><Routes><Route path="/audits/:auditId/aso" element={<AsoPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByText(/Failed to load|Échec du chargement/)).toBeInTheDocument();
});

it("keeps the ASO shell loading without an audit parameter", () => {
  render(<MemoryRouter><I18nProvider><AsoPage /></I18nProvider></MemoryRouter>);
  expect(screen.getByText(/Loading/)).toBeInTheDocument();
});

it("ignores late ASO responses after unmount", async () => {
  let resolveAudit: ((value: unknown) => void) | undefined;
  const pending = new Promise((resolve) => { resolveAudit = resolve; });
  vi.spyOn(api, "getAudit").mockReturnValue(pending as never);
  const view = render(<MemoryRouter initialEntries={["/audits/a1/aso"]}><I18nProvider><Routes><Route path="/audits/:auditId/aso" element={<AsoPage />} /></Routes></I18nProvider></MemoryRouter>);
  view.unmount();
  resolveAudit?.({ domain: "late.example" });
  await Promise.resolve();
});

it("ignores late ASO errors after unmount", async () => {
  let rejectAudit: ((reason?: unknown) => void) | undefined;
  const pending = new Promise((_, reject) => { rejectAudit = reject; });
  vi.spyOn(api, "getAudit").mockReturnValue(pending as never);
  const view = render(<MemoryRouter initialEntries={["/audits/a1/aso"]}><I18nProvider><Routes><Route path="/audits/:auditId/aso" element={<AsoPage />} /></Routes></I18nProvider></MemoryRouter>);
  view.unmount();
  rejectAudit?.(new Error("late"));
  await Promise.resolve();
});
