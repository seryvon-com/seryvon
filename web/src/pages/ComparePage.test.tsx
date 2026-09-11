import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { api, ApiError } from "../api/client";
import { I18nProvider } from "../i18n";
import { canRunComparison, ComparePage } from "./ComparePage";

it("guards comparison execution when either audit is missing", () => {
  expect(canRunComparison(undefined, "right")).toBe(false);
  expect(canRunComparison("left", null)).toBe(false);
  expect(canRunComparison("left", "right")).toBe(true);
});

it("shows the comparison loading state", () => {
  vi.spyOn(api, "getAudit").mockReturnValue(new Promise(() => {}));
  render(<MemoryRouter initialEntries={["/audits/a1/compare"]}><I18nProvider><Routes><Route path="/audits/:auditId/compare" element={<ComparePage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(screen.getByText(/Loading/)).toBeInTheDocument();
});

it("shows the comparison load error", async () => {
  vi.spyOn(api, "getAudit").mockRejectedValue(new Error("offline"));
  render(<MemoryRouter initialEntries={["/audits/a1/compare"]}><I18nProvider><Routes><Route path="/audits/:auditId/compare" element={<ComparePage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByText(/Failed to load/)).toBeInTheDocument();
});

it("shows the localized not-found error for an API response", async () => {
  vi.spyOn(api, "getAudit").mockRejectedValue(new ApiError(404, "missing"));
  render(<MemoryRouter initialEntries={["/audits/a1/compare"]}><I18nProvider><Routes><Route path="/audits/:auditId/compare" element={<ComparePage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByText(/not found/i)).toBeInTheDocument();
});

it("renders the loaded audit comparison controls", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z" } as never);
  vi.spyOn(api, "listAudits").mockResolvedValue([]);
  render(<MemoryRouter initialEntries={["/audits/a1/compare"]}><I18nProvider><Routes><Route path="/audits/:auditId/compare" element={<ComparePage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByText(/No audit found for example.com/i)).toBeInTheDocument();
});

it("renders a comparison result", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z", score_global: 70, pillars: {} } as never);
  vi.spyOn(api, "listAudits").mockResolvedValue([{ audit_id: "a2", domain: "example.com", score_global: 75, started_at: "2026-09-08T10:00:00Z", criteria_measured: 10 }]);
  vi.spyOn(api, "compareAudits").mockResolvedValue({ comparability: "exact", requested_mode: "descriptive", allowed_modes: ["descriptive"], profile_differences: ["crawler_version"], recomputed: true, common_criteria: ["meta.title"], global_delta: 5, left_global: 70, right_global: 75, pillars: [{ pillar: "seo", left_score: 60, right_score: 70, delta: 10 }, { pillar: "geo", left_score: 70, right_score: 60, delta: -10 }, { pillar: "gso", left_score: null, right_score: null, delta: null }, { pillar: "aeo", left_score: 70, right_score: 70, delta: 0 }], criteria: [{ key: "meta.title", left_score: 60, right_score: 80, delta: 20 }, { key: "meta.description", left_score: 70, right_score: 70, delta: 0 }, { key: "meta.robots", left_score: 80, right_score: 60, delta: -20 }, { key: "meta.schema", left_score: null, right_score: null, delta: null }] } as never);
  render(<MemoryRouter initialEntries={["/audits/a1/compare"]}><I18nProvider><Routes><Route path="/audits/:auditId/compare" element={<ComparePage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByRole("button", { name: /Compare/ })).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: /Compare/ }));
  expect(await screen.findByText("SEO")).toBeInTheDocument();
  expect(screen.getByText(/crawler_version/)).toBeInTheDocument();
  expect(screen.getByText(/recomputed|recalculated/i)).toBeInTheDocument();
  expect(screen.getByText("meta.title")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("checkbox"));
  expect(screen.queryByText("meta.description")).not.toBeInTheDocument();
});

it("shows an error when comparison execution fails", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z", score_global: 70, pillars: {} } as never);
  vi.spyOn(api, "listAudits").mockResolvedValue([{ audit_id: "a2", domain: "example.com", score_global: 75, started_at: "2026-09-08T10:00:00Z", criteria_measured: 10 }]);
  vi.spyOn(api, "compareAudits").mockRejectedValue(new Error("comparison failed"));
  render(<MemoryRouter initialEntries={["/audits/a1/compare"]}><I18nProvider><Routes><Route path="/audits/:auditId/compare" element={<ComparePage />} /></Routes></I18nProvider></MemoryRouter>);
  const compare = await screen.findByRole("button", { name: /Compare/ });
  fireEvent.click(compare);
  expect(await screen.findByText(/Compare failed/i)).toBeInTheDocument();
});

it("triggers a manual history reload from the domain field", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z", score_global: 70, pillars: {} } as never);
  vi.spyOn(api, "listAudits").mockResolvedValueOnce([]).mockResolvedValueOnce([{ audit_id: "a2", domain: "other.test", score_global: 80, started_at: "2026-09-08T10:00:00Z", criteria_measured: 4 }]);
  render(<MemoryRouter initialEntries={["/audits/a1/compare"]}><I18nProvider><Routes><Route path="/audits/:auditId/compare" element={<ComparePage />} /></Routes></I18nProvider></MemoryRouter>);
  const input = await screen.findByDisplayValue("example.com");
  fireEvent.change(input, { target: { value: "other.test" } });
  fireEvent.keyDown(input, { key: "Enter" });
  expect(api.listAudits).toHaveBeenCalled();
});

it("handles a failed manual history reload", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z", score_global: 70, pillars: {} } as never);
  vi.spyOn(api, "listAudits").mockResolvedValueOnce([]).mockRejectedValueOnce(new Error("offline"));
  render(<MemoryRouter initialEntries={["/audits/a1/compare"]}><I18nProvider><Routes><Route path="/audits/:auditId/compare" element={<ComparePage />} /></Routes></I18nProvider></MemoryRouter>);
  const input = await screen.findByDisplayValue("example.com");
  fireEvent.keyDown(input, { key: "Enter" });
  expect(api.listAudits).toHaveBeenCalledTimes(2);
});

it("surfaces an API error returned by comparison", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z", score_global: 70, pillars: {} } as never);
  vi.spyOn(api, "listAudits").mockResolvedValue([{ audit_id: "a2", domain: "example.com", score_global: 75, started_at: "2026-09-08T10:00:00Z", criteria_measured: 10 }]);
  vi.spyOn(api, "compareAudits").mockRejectedValue(new ApiError(409, "not comparable"));
  render(<MemoryRouter initialEntries={["/audits/a1/compare"]}><I18nProvider><Routes><Route path="/audits/:auditId/compare" element={<ComparePage />} /></Routes></I18nProvider></MemoryRouter>);
  fireEvent.click(await screen.findByRole("button", { name: /Compare/ }));
  expect(await screen.findByText(/409: not comparable/i)).toBeInTheDocument();
});

it("changes the selected comparison run", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z", score_global: 70, pillars: {} } as never);
  vi.spyOn(api, "listAudits").mockResolvedValue([{ audit_id: "a2", domain: "example.com", score_global: 75, started_at: "2026-09-08T10:00:00Z", criteria_measured: 10 }, { audit_id: "a3", domain: "example.com", score_global: 72, started_at: "2026-09-07T10:00:00Z", criteria_measured: 9 }]);
  vi.spyOn(api, "compareAudits").mockResolvedValue({ comparability: "exact", requested_mode: "descriptive", allowed_modes: ["descriptive"], profile_differences: [], recomputed: false, common_criteria: [], global_delta: 0, left_global: 70, right_global: 70, pillars: [], criteria: [] } as never);
  render(<MemoryRouter initialEntries={["/audits/a1/compare"]}><I18nProvider><Routes><Route path="/audits/:auditId/compare" element={<ComparePage />} /></Routes></I18nProvider></MemoryRouter>);
  fireEvent.click(await screen.findByRole("button", { name: /Compare/ }));
  fireEvent.click(document.querySelectorAll(".compare-run-item")[1] as HTMLElement);
  expect(document.querySelectorAll(".compare-run-item")[1]).toHaveClass("selected");
});

it("renders an alternative run without a score", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z", score_global: 70, pillars: {} } as never);
  vi.spyOn(api, "listAudits").mockResolvedValue([{ audit_id: "a2", domain: "example.com", score_global: null, started_at: "2026-09-08T10:00:00Z", criteria_measured: 10 }]);
  render(<MemoryRouter initialEntries={["/audits/a1/compare"]}><I18nProvider><Routes><Route path="/audits/:auditId/compare" element={<ComparePage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByText("—")).toBeInTheDocument();
});

it("renders neutral and unavailable comparison deltas", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z", score_global: 70, pillars: {} } as never);
  vi.spyOn(api, "listAudits").mockResolvedValue([{ audit_id: "a2", domain: "example.com", score_global: 70, started_at: "2026-09-08T10:00:00Z", criteria_measured: 10 }]);
  vi.spyOn(api, "compareAudits").mockResolvedValue({ comparability: "exact", requested_mode: "descriptive", allowed_modes: ["descriptive"], profile_differences: [], recomputed: false, common_criteria: [], global_delta: null, left_global: null, right_global: null, pillars: [{ pillar: "seo", left_score: 70, right_score: 70, delta: 0 }], criteria: [{ key: "meta.title", left_score: null, right_score: null, delta: null }, { key: "meta.description", left_score: 50, right_score: 52, delta: 2 }] } as never);
  render(<MemoryRouter initialEntries={["/audits/a1/compare"]}><I18nProvider><Routes><Route path="/audits/:auditId/compare" element={<ComparePage />} /></Routes></I18nProvider></MemoryRouter>);
  fireEvent.click(await screen.findByRole("button", { name: /Compare/ }));
  expect(await screen.findByText("meta.title")).toBeInTheDocument();
});

it("renders a negative global delta", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z", score_global: 70, pillars: {} } as never);
  vi.spyOn(api, "listAudits").mockResolvedValue([{ audit_id: "a2", domain: "example.com", score_global: 65, started_at: "2026-09-08T10:00:00Z", criteria_measured: 10 }]);
  vi.spyOn(api, "compareAudits").mockResolvedValue({ comparability: "exact", requested_mode: "descriptive", allowed_modes: ["descriptive"], profile_differences: [], recomputed: false, common_criteria: [], global_delta: -5, left_global: 70, right_global: 65, pillars: [], criteria: [] } as never);
  render(<MemoryRouter initialEntries={["/audits/a1/compare"]}><I18nProvider><Routes><Route path="/audits/:auditId/compare" element={<ComparePage />} /></Routes></I18nProvider></MemoryRouter>);
  fireEvent.click(await screen.findByRole("button", { name: /Compare/ }));
  expect(await screen.findByText("-5")).toBeInTheDocument();
});




it("handles history loading failures and empty manual domains", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z", score_global: 70, pillars: {} } as never);
  vi.spyOn(api, "listAudits").mockRejectedValue(new Error("offline"));
  render(<MemoryRouter initialEntries={["/audits/a1/compare"]}><I18nProvider><Routes><Route path="/audits/:auditId/compare" element={<ComparePage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByDisplayValue("example.com")).toBeInTheDocument();
  const input = document.querySelector(".compare-input") as HTMLInputElement;
  fireEvent.change(input, { target: { value: "   " } });
  fireEvent.keyDown(input, { key: "Enter" });
  expect(api.listAudits).toHaveBeenCalledTimes(1);
});

it("keeps comparison unavailable without an audit parameter", () => {
  render(<MemoryRouter><I18nProvider><ComparePage /></I18nProvider></MemoryRouter>);
  expect(screen.getByText(/Loading/)).toBeInTheDocument();
});

it("ignores a late comparison audit response after unmount", async () => {
  let resolveAudit: ((value: unknown) => void) | undefined;
  const pending = new Promise((resolve) => { resolveAudit = resolve; });
  vi.spyOn(api, "getAudit").mockReturnValue(pending as never);
  const view = render(<MemoryRouter initialEntries={["/audits/a1/compare"]}><I18nProvider><Routes><Route path="/audits/:auditId/compare" element={<ComparePage />} /></Routes></I18nProvider></MemoryRouter>);
  view.unmount();
  resolveAudit?.({ domain: "late.example" });
  await Promise.resolve();
});

it("ignores a late comparison audit error after unmount", async () => {
  let rejectAudit: ((reason?: unknown) => void) | undefined;
  const pending = new Promise((_, reject) => { rejectAudit = reject; });
  vi.spyOn(api, "getAudit").mockReturnValue(pending as never);
  const view = render(<MemoryRouter initialEntries={["/audits/a1/compare"]}><I18nProvider><Routes><Route path="/audits/:auditId/compare" element={<ComparePage />} /></Routes></I18nProvider></MemoryRouter>);
  view.unmount();
  rejectAudit?.(new Error("late"));
  await Promise.resolve();
});

it("ignores a late comparison history response after unmount", async () => {
  let resolveHistory: ((value: unknown) => void) | undefined;
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z" } as never);
  vi.spyOn(api, "listAudits").mockReturnValue(new Promise((resolve) => { resolveHistory = resolve; }) as never);
  const view = render(<MemoryRouter initialEntries={["/audits/a1/compare"]}><I18nProvider><Routes><Route path="/audits/:auditId/compare" element={<ComparePage />} /></Routes></I18nProvider></MemoryRouter>);
  await waitFor(() => expect(api.listAudits).toHaveBeenCalled());
  view.unmount();
  resolveHistory?.([]);
  await Promise.resolve();
});
