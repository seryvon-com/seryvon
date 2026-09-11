import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { api, ApiError } from "../api/client";
import { I18nProvider } from "../i18n";
import { pageClicksValue, pageCtrValue, pageImpressionsValue, pagePositionValue, pageValue, queryClicksValue, queryCtrValue, queryImpressionsValue, queryKeywordValue, queryPositionValue, RankTrackingPage, RankTrackingView, SortableTable } from "./RankTrackingPage";

it("shows the rank tracking loading state", () => {
  vi.spyOn(api, "getAudit").mockReturnValue(new Promise(() => {}));
  render(<MemoryRouter initialEntries={["/audits/a1/rank-tracking"]}><I18nProvider><Routes><Route path="/audits/:auditId/rank-tracking" element={<RankTrackingPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(screen.getByText(/Loading/)).toBeInTheDocument();
});

it("shows the rank tracking load error", async () => {
  vi.spyOn(api, "getAudit").mockRejectedValue(new Error("offline"));
  render(<MemoryRouter initialEntries={["/audits/a1/rank-tracking"]}><I18nProvider><Routes><Route path="/audits/:auditId/rank-tracking" element={<RankTrackingPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByText(/Failed to load/)).toBeInTheDocument();
});

it("renders GSC ranking data", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z", criteria: [{ key: "seo.avg_position", raw_value: { avg_position: 4.2, total_clicks: 10, total_impressions: 100, avg_ctr: 0.1, date_range_days: 90, queries: [{ query: "alpha", position: 4.2, clicks: 10, impressions: 100, ctr: 0.1 }], pages: [{ page: "https://example.com/alpha", position: 4.2, clicks: 10, impressions: 100, ctr: 0.1 }], comparison: { avg_position: 5.1, total_clicks: 8, total_impressions: 80, avg_ctr: 0.1 } } }] } as never);
  render(<MemoryRouter initialEntries={["/audits/a1/rank-tracking"]}><I18nProvider><Routes><Route path="/audits/:auditId/rank-tracking" element={<RankTrackingPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect((await screen.findAllByText("4.2")).length).toBeGreaterThan(0);
  screen.getAllByRole("columnheader").forEach((header) => {
    fireEvent.click(header);
    fireEvent.click(header);
  });
});

it("shows the unavailable state when GSC data is missing", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z", criteria: [] } as never);
  render(<MemoryRouter initialEntries={["/audits/a1/rank-tracking"]}><I18nProvider><Routes><Route path="/audits/:auditId/rank-tracking" element={<RankTrackingPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByText(/No GSC data available/i)).toBeInTheDocument();
  fireEvent.click(document.querySelector(".notice .btn") as HTMLElement);
});

it("handles incomplete GSC raw values", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z", criteria: [{ key: "seo.avg_position", raw_value: { avg_position: 3.4 } }] } as never);
  render(<MemoryRouter initialEntries={["/audits/a1/rank-tracking"]}><I18nProvider><Routes><Route path="/audits/:auditId/rank-tracking" element={<RankTrackingPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByText("3.4")).toBeInTheDocument();
});

it("rejects a GSC criterion without an average position", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z", criteria: [{ key: "seo.avg_position", raw_value: { avg_position: null } }] } as never);
  render(<MemoryRouter initialEntries={["/audits/a1/rank-tracking"]}><I18nProvider><Routes><Route path="/audits/:auditId/rank-tracking" element={<RankTrackingPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByText(/No GSC data available/i)).toBeInTheDocument();
});

it("filters ranking tables and applies a bounded custom period", async () => {
  const getRankTracking = vi.spyOn(api, "getRankTracking").mockResolvedValue({
    avg_position: 3.1,
    total_clicks: 20,
    total_impressions: 200,
    avg_ctr: 0.2,
    date_range_days: 480,
    queries: [{ query: "alpha", position: 3.1, clicks: 12, impressions: 120, ctr: 0.2 }, { query: "beta", position: 8, clicks: 8, impressions: 80, ctr: 0.1 }],
    pages: [{ page: "https://example.com/a", position: 3.1, clicks: 12, impressions: 120, ctr: 0.2 }],
    comparison: { period_days: 28, position_delta: -1, clicks_delta: 2, impressions_delta: 0, ctr_delta: 0.01 },
  } as never);
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z", criteria: [{ key: "seo.avg_position", raw_value: { avg_position: 4.2, total_clicks: 10, total_impressions: 100, avg_ctr: 0.1, date_range_days: 90, queries: [{ query: "alpha", position: 4.2, clicks: 4, impressions: 40, ctr: 0.1 }], pages: [], comparison: null } }] } as never);
  render(<MemoryRouter initialEntries={["/audits/a1/rank-tracking"]}><I18nProvider><Routes><Route path="/audits/:auditId/rank-tracking" element={<RankTrackingPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByText("alpha")).toBeInTheDocument();
  const rankHeaders = screen.getAllByRole("columnheader");
  rankHeaders.forEach((header) => { fireEvent.click(header); fireEvent.click(header); });
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "missing" } });
  expect(screen.getByText("0")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "7d" }));
  await waitFor(() => expect(getRankTracking).toHaveBeenCalledWith("a1", 7));
  fireEvent.change(screen.getAllByRole("searchbox")[0], { target: { value: "" } });
  expect(await screen.findByText("beta")).toBeInTheDocument();
  fireEvent.change(document.querySelector(".period-custom input") as HTMLInputElement, { target: { value: "30" } });
  fireEvent.submit(document.querySelector(".period-custom") as HTMLFormElement);
});

it("shows the period update error when GSC refresh fails", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z", criteria: [{ key: "seo.avg_position", raw_value: { avg_position: 4.2, total_clicks: 10, total_impressions: 100, avg_ctr: 0.1, date_range_days: 90, queries: [], pages: [], comparison: null } }] } as never);
  vi.spyOn(api, "getRankTracking").mockRejectedValue(new Error("offline"));
  render(<MemoryRouter initialEntries={["/audits/a1/rank-tracking"]}><I18nProvider><Routes><Route path="/audits/:auditId/rank-tracking" element={<RankTrackingPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByText("4.2")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "7d" }));
  expect(await screen.findByText(/Could not refresh GSC/i)).toBeInTheDocument();
});

it("renders an unavailable average position after refresh", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z", criteria: [{ key: "seo.avg_position", raw_value: { avg_position: 4.2 } }] } as never);
  vi.spyOn(api, "getRankTracking").mockResolvedValue({ avg_position: null, total_clicks: 0, total_impressions: 0, avg_ctr: 0, date_range_days: 7, queries: [], pages: [], comparison: null } as never);
  render(<MemoryRouter initialEntries={["/audits/a1/rank-tracking"]}><I18nProvider><Routes><Route path="/audits/:auditId/rank-tracking" element={<RankTrackingPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByText("4.2")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "7d" }));
  expect(await screen.findAllByText("—")).not.toHaveLength(0);
});

it("formats API errors from the rank audit request", async () => {
  vi.spyOn(api, "getAudit").mockRejectedValue(new ApiError(404, "missing"));
  render(<MemoryRouter initialEntries={["/audits/a1/rank-tracking"]}><I18nProvider><Routes><Route path="/audits/:auditId/rank-tracking" element={<RankTrackingPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByText(/404|not found/i)).toBeInTheDocument();
});

it("keeps the rank tracking shell loading without an audit parameter", () => {
  render(<MemoryRouter><I18nProvider><RankTrackingPage /></I18nProvider></MemoryRouter>);
  expect(screen.getByText(/Loading/)).toBeInTheDocument();
});

it("renders an empty sortable table when its initial column is missing", () => {
  render(<I18nProvider><SortableTable rows={[{ value: 1 }]} columns={[]} initialSortId="missing" rowKey={() => "row"} /></I18nProvider>);
  expect(screen.getByRole("table")).toBeInTheDocument();
});

it("sorts a generic sortable table with text values and toggles direction", () => {
  render(<SortableTable
    rows={[{ value: "z" }, { value: "a" }]}
    columns={[{ id: "value", label: "Value", value: (row) => row.value, render: (row) => row.value }]}
    initialSortId="value"
    rowKey={(row) => row.value}
  />);
  const header = screen.getByRole("columnheader");
  fireEvent.click(header);
  fireEvent.click(header);
  expect(screen.getByText("a")).toBeInTheDocument();
});

it("evaluates every ranking column accessor", () => {
  const q = { query: "q", position: 2, clicks: 3, impressions: 4, ctr: 0.5 };
  const p = { page: "https://example.com", position: 2, clicks: 3, impressions: 4, ctr: 0.5 };
  expect([queryKeywordValue(q), queryPositionValue(q), queryClicksValue(q), queryImpressionsValue(q), queryCtrValue(q)]).toEqual(["q", 2, 3, 4, 0.5]);
  expect([pageValue(p), pagePositionValue(p), pageClicksValue(p), pageImpressionsValue(p), pageCtrValue(p)]).toEqual(["https://example.com", 2, 3, 4, 0.5]);
});

it("executes every ranking query and page column accessor", async () => {
  render(<I18nProvider><RankTrackingView auditId="a1" gsc={{
    avg_position: 4.2, total_clicks: 10, total_impressions: 100, avg_ctr: 0.1, date_range_days: 7,
    comparison: null,
    queries: [{ query: "alpha", position: 4.2, clicks: 10, impressions: 100, ctr: 0.1 }],
    pages: [{ page: "https://example.com", position: 4.2, clicks: 10, impressions: 100, ctr: 0.1 }],
  }} /></I18nProvider>);
  for (const header of screen.getAllByRole("columnheader")) {
    fireEvent.click(header);
    await waitFor(() => expect(header).toHaveAttribute("aria-sort", "descending"));
    fireEvent.click(header);
    await waitFor(() => expect(header).toHaveAttribute("aria-sort", "ascending"));
  }
  for (const input of screen.getAllByRole("searchbox")) fireEvent.change(input, { target: { value: "example" } });
  await waitFor(() => expect(screen.getAllByText(/alpha|example.com/).length).toBeGreaterThan(0));
});

it("ignores late rank-audit responses after unmount", async () => {
  let resolveAudit: ((value: unknown) => void) | undefined;
  const pending = new Promise((resolve) => { resolveAudit = resolve; });
  vi.spyOn(api, "getAudit").mockReturnValue(pending as never);
  const view = render(<MemoryRouter initialEntries={["/audits/a1/rank-tracking"]}><I18nProvider><Routes><Route path="/audits/:auditId/rank-tracking" element={<RankTrackingPage />} /></Routes></I18nProvider></MemoryRouter>);
  view.unmount();
  resolveAudit?.({ domain: "late.example" });
  await Promise.resolve();
});

it("ignores late rank-audit errors after unmount", async () => {
  let rejectAudit: ((reason?: unknown) => void) | undefined;
  const pending = new Promise((_, reject) => { rejectAudit = reject; });
  vi.spyOn(api, "getAudit").mockReturnValue(pending as never);
  const view = render(<MemoryRouter initialEntries={["/audits/a1/rank-tracking"]}><I18nProvider><Routes><Route path="/audits/:auditId/rank-tracking" element={<RankTrackingPage />} /></Routes></I18nProvider></MemoryRouter>);
  view.unmount();
  rejectAudit?.(new Error("late"));
  await Promise.resolve();
});
