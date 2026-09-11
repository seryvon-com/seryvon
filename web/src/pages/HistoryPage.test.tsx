import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { api, ApiError } from "../api/client";
import { I18nProvider } from "../i18n";
import { HistoryPage } from "./HistoryPage";

function renderPage() {
  return render(<MemoryRouter initialEntries={["/audits/a1/history"]}><I18nProvider><Routes><Route path="/audits/:auditId/history" element={<HistoryPage />} /></Routes></I18nProvider></MemoryRouter>);
}

it("shows the history loading state", () => {
  vi.spyOn(api, "getAudit").mockReturnValue(new Promise(() => {}));
  renderPage();
  expect(screen.getByText(/Loading/)).toBeInTheDocument();
});

it("shows not found when the audit cannot be loaded", async () => {
  vi.spyOn(api, "getAudit").mockRejectedValue({ status: 404 });
  renderPage();
  expect(await screen.findByText(/Failed to load/)).toBeInTheDocument();
});

it("renders audit history rows", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z" } as never);
  vi.spyOn(api, "listAudits").mockResolvedValue([{ audit_id: "a1", domain: "example.com", score_global: 82.4, started_at: "2026-09-09T10:00:00Z", criteria_measured: 12 }]);
  renderPage();
  expect(await screen.findByText("a1")).toBeInTheDocument();
  expect(screen.getByText("82")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /View/ })).toBeInTheDocument();
});

it("renders an empty history and handles the audit navigation", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z" } as never);
  vi.spyOn(api, "listAudits").mockResolvedValue([]);
  renderPage();
  expect(await screen.findByText(/No prior audit|Aucun historique/)).toBeInTheDocument();
});

it("renders missing score and measured criteria as dashes", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z" } as never);
  vi.spyOn(api, "listAudits").mockResolvedValue([{ audit_id: "a2", domain: "example.com", score_global: null, started_at: "2026-09-09T10:00:00Z", criteria_measured: 0 }]);
  renderPage();
  expect(await screen.findByText("a2")).toBeInTheDocument();
  expect(screen.getAllByText("—")).toHaveLength(2);
  fireEvent.click(screen.getByRole("button", { name: /View|Voir/ }));
});

it("shows a generic error when history loading fails", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z" } as never);
  vi.spyOn(api, "listAudits").mockRejectedValue(new Error("network"));
  renderPage();
  expect(await screen.findByText(/Failed to load|Échec du chargement/)).toBeInTheDocument();
});

it("formats an API error when history loading fails", async () => {
  vi.spyOn(api, "getAudit").mockRejectedValue(new ApiError(404, "missing"));
  renderPage();
  expect(await screen.findByText(/404|not found/i)).toBeInTheDocument();
});

it("does nothing when no audit id is provided", () => {
  render(<MemoryRouter><I18nProvider><HistoryPage /></I18nProvider></MemoryRouter>);
  expect(screen.getByText(/Loading|Chargement/)).toBeInTheDocument();
});

it("ignores a late audit response after unmount", async () => {
  let resolveAudit: ((value: unknown) => void) | undefined;
  const pending = new Promise((resolve) => { resolveAudit = resolve; });
  vi.spyOn(api, "getAudit").mockReturnValue(pending as never);
  const view = renderPage();
  view.unmount();
  resolveAudit?.({ domain: "late.example", started_at: "2026-09-09T10:00:00Z" });
  await Promise.resolve();
});

it("ignores a late audit error after unmount", async () => {
  let rejectAudit: ((reason?: unknown) => void) | undefined;
  const pending = new Promise((_, reject) => { rejectAudit = reject; });
  vi.spyOn(api, "getAudit").mockReturnValue(pending as never);
  const view = renderPage();
  view.unmount();
  rejectAudit?.(new Error("late"));
  await Promise.resolve();
});
