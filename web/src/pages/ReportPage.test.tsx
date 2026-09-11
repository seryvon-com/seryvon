import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { api, ApiError } from "../api/client";
import { I18nProvider } from "../i18n";
import { ReportPage } from "./ReportPage";

vi.mock("../components/ReportView", () => ({ ReportView: () => <div>Report content</div> }));
vi.mock("../components/CrawledPages", () => ({ CrawledPages: () => <div>Crawled pages</div> }));

it("shows the report loading state", () => {
  vi.spyOn(api, "getAudit").mockReturnValue(new Promise(() => {}));
  render(<MemoryRouter initialEntries={["/audits/a1/report"]}><I18nProvider><Routes><Route path="/audits/:auditId/report" element={<ReportPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(screen.getByText(/Loading/)).toBeInTheDocument();
});

it("shows the report load error", async () => {
  vi.spyOn(api, "getAudit").mockRejectedValue(new Error("offline"));
  render(<MemoryRouter initialEntries={["/audits/a1/report"]}><I18nProvider><Routes><Route path="/audits/:auditId/report" element={<ReportPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByText(/Failed to load/)).toBeInTheDocument();
});

it("shows the translated not-found error for an API error", async () => {
  vi.spyOn(api, "getAudit").mockRejectedValue(new ApiError(404, "missing"));
  render(<MemoryRouter initialEntries={["/audits/a1/report"]}><I18nProvider><Routes><Route path="/audits/:auditId/report" element={<ReportPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByText(/Failed to load|not found/i)).toBeInTheDocument();
});

it("renders a loaded report and exposes the PDF download action", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z" } as never);
  render(<MemoryRouter initialEntries={["/audits/a1/report"]}><I18nProvider><Routes><Route path="/audits/:auditId/report" element={<ReportPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByText("Report content")).toBeInTheDocument();
  const download = screen.getByRole("button", { name: /download.*pdf/i });
  expect(download).toBeInTheDocument();
  fireEvent.click(download);
  expect(download).toBeDisabled();
});

it("keeps the report shell loading without an audit parameter", () => {
  render(<MemoryRouter><I18nProvider><ReportPage /></I18nProvider></MemoryRouter>);
  expect(screen.getByText(/Loading/)).toBeInTheDocument();
});
