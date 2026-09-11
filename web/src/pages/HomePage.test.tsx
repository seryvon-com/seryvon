import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter, useLocation } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { ApiError, api } from "../api/client";
import { I18nProvider } from "../i18n";
import { HomePage, isDemoMode } from "./HomePage";

it("detects demo mode from the URL", () => {
  const original = window.location.href;
  window.history.pushState({}, "", "/?demo=1");
  expect(isDemoMode()).toBe(true);
  window.history.pushState({}, "", original);
  expect(isDemoMode()).toBe(false);
});

it("renders the new-audit form while initial data is pending", () => {
  vi.spyOn(api, "getAuditCostEstimate").mockReturnValue(new Promise(() => {}));
  vi.spyOn(api, "listDomains").mockReturnValue(new Promise(() => {}));
  render(<MemoryRouter><I18nProvider><HomePage /></I18nProvider></MemoryRouter>);
  expect(screen.getByRole("textbox", { name: "URL" })).toBeInTheDocument();
  expect(document.querySelector(".home-audit-btn")).toBeInTheDocument();
});

it("renders the built-in demo domains", async () => {
  vi.spyOn(api, "getAuditCostEstimate").mockResolvedValue({ currency: "USD", total_usd: 0, indicative: false, lines: [] });
  const list = vi.spyOn(api, "listDomains");
  const original = window.location.href;
  window.history.pushState({}, "", "/?demo=1");
  render(<MemoryRouter><I18nProvider><HomePage /></I18nProvider></MemoryRouter>);
  expect(await screen.findByText("northstar-logistics.example")).toBeInTheDocument();
  expect(list).not.toHaveBeenCalled();
  window.history.pushState({}, "", original);
});

it("does not start an audit for an empty URL", () => {
  vi.spyOn(api, "getAuditCostEstimate").mockResolvedValue({ currency: "USD", total_usd: 0, indicative: false, lines: [] });
  vi.spyOn(api, "listDomains").mockResolvedValue([]);
  const createAudit = vi.spyOn(api, "createAudit");
  render(<MemoryRouter><I18nProvider><HomePage /></I18nProvider></MemoryRouter>);
  fireEvent.click(document.querySelector(".home-audit-btn") as HTMLElement);
  expect(createAudit).not.toHaveBeenCalled();
});

it("shows the backend error when audit creation fails", async () => {
  vi.spyOn(api, "getAuditCostEstimate").mockResolvedValue({ currency: "USD", total_usd: 0, indicative: false, lines: [] });
  vi.spyOn(api, "listDomains").mockResolvedValue([]);
  vi.spyOn(api, "createAudit").mockRejectedValue(new Error("offline"));
  render(<MemoryRouter><I18nProvider><HomePage /></I18nProvider></MemoryRouter>);
  fireEvent.change(screen.getByRole("textbox", { name: "URL" }), { target: { value: "example.com" } });
  fireEvent.click(document.querySelector(".home-audit-btn") as HTMLElement);
  await waitFor(() => expect(screen.getByText(/backend|server/i)).toBeInTheDocument());
  expect(document.querySelector(".home-audit-btn")).not.toBeDisabled();
});

it("formats an API creation error with its status", async () => {
  vi.spyOn(api, "getAuditCostEstimate").mockResolvedValue({ currency: "USD", total_usd: 0, indicative: false, lines: [] });
  vi.spyOn(api, "listDomains").mockResolvedValue([]);
  vi.spyOn(api, "createAudit").mockRejectedValue(new ApiError(422, "Invalid URL"));
  render(<MemoryRouter><I18nProvider><HomePage /></I18nProvider></MemoryRouter>);
  fireEvent.change(screen.getByRole("textbox", { name: "URL" }), { target: { value: "example.com" } });
  fireEvent.click(document.querySelector(".home-audit-btn") as HTMLElement);
  await waitFor(() => expect(screen.getByText(/422.*Invalid URL/i)).toBeInTheDocument());
});

it("renders the cost badge and recent domains", async () => {
  vi.spyOn(api, "getAuditCostEstimate").mockResolvedValue({ currency: "USD", total_usd: 0, indicative: false, lines: [] });
  vi.spyOn(api, "listDomains").mockResolvedValue([{ domain: "example.com", audit_count: 2, latest_audit_id: "a1", latest_score: 80, latest_started_at: "2026-09-09T10:00:00Z" }]);
  render(<MemoryRouter><I18nProvider><HomePage /></I18nProvider></MemoryRouter>);
  expect(await screen.findByText(/Estimated cost: free/i)).toBeInTheDocument();
  expect(screen.getByText("example.com")).toBeInTheDocument();
});

it("opens the cost breakdown with active and inactive connectors", async () => {
  vi.spyOn(api, "getAuditCostEstimate").mockResolvedValue({
    currency: "USD",
    total_usd: 0.125,
    indicative: true,
    lines: [
      { connector: "openai", active: true, calls: 2, unit_usd: 0.01, total_usd: 0.02, note: "" },
      { connector: "psi", active: false, calls: 0, unit_usd: 0, total_usd: 0, note: "not configured" },
    ],
  });
  vi.spyOn(api, "listDomains").mockResolvedValue([]);
  render(<MemoryRouter><I18nProvider><HomePage /></I18nProvider></MemoryRouter>);
  expect(await screen.findByText(/Estimated cost/i)).toBeInTheDocument();
  fireEvent.mouseEnter(screen.getByRole("button", { name: "Cost breakdown" }));
  expect(await screen.findByRole("tooltip")).toHaveTextContent("OPENAI");
  expect(screen.getByRole("tooltip")).toHaveTextContent(/not configured/i);
  fireEvent.mouseLeave(screen.getByRole("button", { name: "Cost breakdown" }));
  await waitFor(() => expect(screen.queryByRole("tooltip")).not.toBeInTheDocument());
});

it("navigates to the latest audit from a recent domain", async () => {
  vi.spyOn(api, "getAuditCostEstimate").mockResolvedValue({ currency: "USD", total_usd: 0, indicative: false, lines: [] });
  vi.spyOn(api, "listDomains").mockResolvedValue([{ domain: "example.com", audit_count: 1, latest_audit_id: "audit-42", latest_score: null, latest_started_at: "2026-09-09T10:00:00Z" }]);
  function Probe() { return <span data-testid="location">{useLocation().pathname}</span>; }
  const { container } = render(<MemoryRouter><I18nProvider><HomePage /><Probe /></I18nProvider></MemoryRouter>);
  const domain = await screen.findByText("example.com");
  fireEvent.keyDown(domain, { key: "Enter" });
  expect(container.querySelector("[data-testid=location]")).toHaveTextContent("/audits/audit-42");
  fireEvent.click(domain);
  expect(container.querySelector("[data-testid=location]")).toHaveTextContent("/audits/audit-42");
});

it("handles recent-domain loading failure and keyboard navigation", async () => {
  vi.spyOn(api, "getAuditCostEstimate").mockResolvedValue({ currency: "USD", total_usd: 0, indicative: false, lines: [] });
  vi.spyOn(api, "listDomains").mockRejectedValue(new Error("offline"));
  function Probe() { return <span data-testid="location-keyboard">{useLocation().pathname}</span>; }
  render(<MemoryRouter><I18nProvider><HomePage /><Probe /></I18nProvider></MemoryRouter>);
  await waitFor(() => expect(screen.queryByText(/recent/i)).not.toBeInTheDocument());
});

it("reruns an audit from a recent domain", async () => {
  vi.spyOn(api, "getAuditCostEstimate").mockResolvedValue({ currency: "USD", total_usd: 0, indicative: false, lines: [] });
  vi.spyOn(api, "listDomains").mockResolvedValue([{ domain: "example.com", audit_count: 1, latest_audit_id: "audit-42", latest_score: 80, latest_started_at: "2026-09-09T10:00:00Z" }]);
  const createAudit = vi.spyOn(api, "createAudit").mockResolvedValue({ task_id: "task-1", status_url: "/tasks/task-1" });
  render(<MemoryRouter><I18nProvider><HomePage /></I18nProvider></MemoryRouter>);
  await screen.findByText("example.com");
  const rerun = document.querySelector(".recent-domain-rerun") as HTMLButtonElement;
  fireEvent.click(rerun);
  await waitFor(() => expect(createAudit).toHaveBeenCalledWith("https://example.com", "en"));
  expect(rerun).toBeDisabled();
});

it("navigates when the audit worker completes", async () => {
  let poll: (() => void) | undefined;
  vi.spyOn(globalThis, "setInterval").mockImplementation((cb) => { poll = cb as () => void; return 1 as never; });
  vi.spyOn(globalThis, "clearInterval").mockImplementation(() => undefined);
  vi.spyOn(api, "getAuditCostEstimate").mockResolvedValue({ currency: "USD", total_usd: 0, indicative: false, lines: [] });
  vi.spyOn(api, "listDomains").mockResolvedValue([]);
  vi.spyOn(api, "createAudit").mockResolvedValue({ task_id: "task-1", status_url: "/tasks/task-1" });
  vi.spyOn(api, "getAuditTask").mockResolvedValue({ status: "done", audit_id: "audit-99", logs: ["done"] } as never);
  render(<MemoryRouter><I18nProvider><HomePage /></I18nProvider></MemoryRouter>);
  fireEvent.change(screen.getByRole("textbox", { name: "URL" }), { target: { value: "example.com" } });
  fireEvent.click(document.querySelector(".home-audit-btn") as HTMLElement);
  await waitFor(() => expect(poll).toBeDefined());
  await act(async () => { poll?.(); });
  await waitFor(() => expect(window.location.pathname).toBe("/"));
});

it("shows the worker error when an audit fails", async () => {
  let poll: (() => void) | undefined;
  vi.spyOn(globalThis, "setInterval").mockImplementation((cb) => { poll = cb as () => void; return 1 as never; });
  vi.spyOn(globalThis, "clearInterval").mockImplementation(() => undefined);
  vi.spyOn(api, "getAuditCostEstimate").mockResolvedValue({ currency: "USD", total_usd: 0, indicative: false, lines: [] });
  vi.spyOn(api, "listDomains").mockResolvedValue([]);
  vi.spyOn(api, "createAudit").mockResolvedValue({ task_id: "task-1", status_url: "/tasks/task-1" });
  vi.spyOn(api, "getAuditTask").mockResolvedValue({ status: "failed", error: "Crawler failed" } as never);
  render(<MemoryRouter><I18nProvider><HomePage /></I18nProvider></MemoryRouter>);
  fireEvent.change(screen.getByRole("textbox", { name: "URL" }), { target: { value: "example.com" } });
  fireEvent.click(document.querySelector(".home-audit-btn") as HTMLElement);
  await waitFor(() => expect(poll).toBeDefined());
  await act(async () => { poll?.(); });
  expect(await screen.findByText("Crawler failed")).toBeInTheDocument();
});

it("uses the fallback worker error when the task has no message", async () => {
  let poll: (() => void) | undefined;
  vi.spyOn(globalThis, "setInterval").mockImplementation((cb) => { poll = cb as () => void; return 1 as never; });
  vi.spyOn(globalThis, "clearInterval").mockImplementation(() => undefined);
  vi.spyOn(api, "getAuditCostEstimate").mockResolvedValue({ currency: "USD", total_usd: 0, indicative: false, lines: [] });
  vi.spyOn(api, "listDomains").mockResolvedValue([]);
  vi.spyOn(api, "createAudit").mockResolvedValue({ task_id: "task-no-message", status_url: "/tasks/task-no-message" });
  vi.spyOn(api, "getAuditTask").mockResolvedValue({ status: "failed" } as never);
  render(<MemoryRouter><I18nProvider><HomePage /></I18nProvider></MemoryRouter>);
  fireEvent.change(screen.getByRole("textbox", { name: "URL" }), { target: { value: "example.com" } });
  fireEvent.click(document.querySelector(".home-audit-btn") as HTMLElement);
  await waitFor(() => expect(poll).toBeDefined());
  await act(async () => { poll?.(); });
  expect(await screen.findByText(/backend|server/i)).toBeInTheDocument();
});

it("shows the backend connection state while a worker is running without logs", async () => {
  let poll: (() => void) | undefined;
  vi.spyOn(globalThis, "setInterval").mockImplementation((cb) => { poll = cb as () => void; return 1 as never; });
  vi.spyOn(globalThis, "clearInterval").mockImplementation(() => undefined);
  vi.spyOn(api, "getAuditCostEstimate").mockResolvedValue({ currency: "USD", total_usd: 0, indicative: false, lines: [] });
  vi.spyOn(api, "listDomains").mockResolvedValue([]);
  vi.spyOn(api, "createAudit").mockResolvedValue({ task_id: "task-running", status_url: "/tasks/task-running" });
  vi.spyOn(api, "getAuditTask").mockResolvedValue({ status: "running", logs: [] } as never);
  render(<MemoryRouter><I18nProvider><HomePage /></I18nProvider></MemoryRouter>);
  fireEvent.change(screen.getByRole("textbox", { name: "URL" }), { target: { value: "example.com" } });
  fireEvent.click(document.querySelector(".home-audit-btn") as HTMLElement);
  await waitFor(() => expect(poll).toBeDefined());
  await act(async () => { poll?.(); });
  expect(await screen.findByText(/Connecting to backend/)).toBeInTheDocument();
});

it("stops polling when the audit worker exceeds the timeout", async () => {
  let poll: (() => void) | undefined;
  vi.spyOn(globalThis, "setInterval").mockImplementation((cb) => { poll = cb as () => void; return 1 as never; });
  vi.spyOn(globalThis, "clearInterval").mockImplementation(() => undefined);
  const future = Date.now() + 6 * 60 * 1000;
  vi.spyOn(api, "getAuditCostEstimate").mockResolvedValue({ currency: "USD", total_usd: 0, indicative: false, lines: [] });
  vi.spyOn(api, "listDomains").mockResolvedValue([]);
  vi.spyOn(api, "createAudit").mockResolvedValue({ task_id: "task-1", status_url: "/tasks/task-1" });
  render(<MemoryRouter><I18nProvider><HomePage /></I18nProvider></MemoryRouter>);
  fireEvent.change(screen.getByRole("textbox", { name: "URL" }), { target: { value: "example.com" } });
  fireEvent.click(document.querySelector(".home-audit-btn") as HTMLElement);
  await waitFor(() => expect(poll).toBeDefined());
  vi.spyOn(Date, "now").mockReturnValue(future);
  await act(async () => { poll?.(); });
  expect(globalThis.clearInterval).toHaveBeenCalled();
});
