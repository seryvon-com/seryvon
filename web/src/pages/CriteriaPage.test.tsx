import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { api, ApiError } from "../api/client";
import { I18nProvider } from "../i18n";
import { CriteriaPage } from "./CriteriaPage";

it("shows the criteria loading state", () => {
  vi.spyOn(api, "getAudit").mockReturnValue(new Promise(() => {}));
  render(<MemoryRouter><I18nProvider><CriteriaPage /></I18nProvider></MemoryRouter>);
  expect(screen.getByText(/Loading/)).toBeInTheDocument();
});

it("renders the loaded criteria table", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z", criteria: [{ key: "meta.title", pillars: ["seo"], status: "ok", score: 90, weight: 1, explanation: "Good", raw_value: "Title", threshold: {}, evidence: {}, evidence_tier: "standard" }] } as never);
  render(<MemoryRouter initialEntries={["/audits/a1/report"]}><I18nProvider><Routes><Route path="/audits/:auditId/report" element={<CriteriaPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByText("meta.title")).toBeInTheDocument();
});

it("renders API and generic criteria loading errors", async () => {
  vi.spyOn(api, "getAudit").mockRejectedValueOnce(new ApiError(404, "missing"));
  const { unmount } = render(<MemoryRouter initialEntries={["/audits/a1/report"]}><I18nProvider><Routes><Route path="/audits/:auditId/report" element={<CriteriaPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByText(/404|not found/i)).toBeInTheDocument();
  unmount();
  vi.spyOn(api, "getAudit").mockRejectedValueOnce(new Error("offline"));
  render(<MemoryRouter initialEntries={["/audits/a2/report"]}><I18nProvider><Routes><Route path="/audits/:auditId/report" element={<CriteriaPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByText(/failed to load/i)).toBeInTheDocument();
});
