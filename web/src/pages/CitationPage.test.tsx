import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { I18nProvider } from "../i18n";
import { api, ApiError } from "../api/client";
import { CitationPage } from "./CitationPage";

it("renders the citation tracking form", () => {
  const { container } = render(<MemoryRouter><I18nProvider><CitationPage /></I18nProvider></MemoryRouter>);
  expect(screen.getByRole("heading", { name: /citation/i })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /run|start|launch/i })).toBeInTheDocument();
  fireEvent.submit(container.querySelector("form") as HTMLFormElement);
});

it("reports missing keys when a citation run is rejected", async () => {
  vi.spyOn(api, "runCitations").mockRejectedValue({ status: 400, message: "No keys" });
  render(<MemoryRouter><I18nProvider><CitationPage /></I18nProvider></MemoryRouter>);
  fireEvent.change(screen.getAllByRole("textbox")[0], { target: { value: "example.com" } });
  fireEvent.click(screen.getByRole("button", { name: /run|start|launch/i }));
  expect(await screen.findByText(/Citation tracking failed/i)).toBeInTheDocument();
});

it("normalizes competitors before starting a citation run", async () => {
  const run = vi.spyOn(api, "runCitations").mockRejectedValue(new ApiError(422, "missing keys"));
  render(<MemoryRouter><I18nProvider><CitationPage /></I18nProvider></MemoryRouter>);
  const fields = screen.getAllByRole("textbox");
  fireEvent.change(fields[0], { target: { value: "example.com" } });
  fireEvent.change(fields[1], { target: { value: "Example Brand" } });
  fireEvent.change(fields[2], { target: { value: " one.com, two.com " } });
  fireEvent.click(screen.getByRole("button", { name: /run|start|launch/i }));
  expect(await screen.findByText(/keys|configured/i)).toBeInTheDocument();
  expect(run).toHaveBeenCalledWith("example.com", "Example Brand", ["one.com", "two.com"]);
});

it("pre-fills the domain from the selected audit", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "audit.example", criteria: [] } as never);
  render(<MemoryRouter initialEntries={["/audits/a1/citation"]}><I18nProvider><Routes><Route path="/audits/:auditId/citation" element={<CitationPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByDisplayValue("audit.example")).toBeInTheDocument();
});

it("keeps the citation form usable when audit prefill fails", async () => {
  vi.spyOn(api, "getAudit").mockRejectedValue(new Error("missing audit"));
  render(<MemoryRouter initialEntries={["/audits/a1/citation"]}><I18nProvider><Routes><Route path="/audits/:auditId/citation" element={<CitationPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(screen.getAllByRole("textbox")[0]).toHaveValue("");
  expect(screen.getByRole("button", { name: /run|start|launch/i })).toBeDisabled();
});

it("renders completed citation metrics after polling", async () => {
  let poll: (() => void) | undefined;
  vi.spyOn(globalThis, "setInterval").mockImplementation((cb) => { poll = cb as () => void; return 1 as never; });
  vi.spyOn(globalThis, "clearInterval").mockImplementation(() => undefined);
  vi.spyOn(api, "runCitations").mockResolvedValue({ task_id: "task-1", status_url: "/tasks/task-1" });
  vi.spyOn(api, "getCitationTask").mockResolvedValue({ status: "done", metrics: { citation_rate: 0.5, mention_rate: 0.25, citation_confidence: 0.75, share_of_voice: null, engines: ["openai"], prompt_count: 2, repetitions: 1, per_engine: { openai: { citation_rate: 0.5, mention_rate: 0.25, average_position: 2.345 }, gemini: { citation_rate: 0, mention_rate: 0, average_position: null } } } } as never);
  render(<MemoryRouter><I18nProvider><CitationPage /></I18nProvider></MemoryRouter>);
  fireEvent.change(screen.getAllByRole("textbox")[0], { target: { value: "example.com" } });
  fireEvent.click(screen.getByRole("button", { name: /run|start|launch/i }));
  await waitFor(() => expect(poll).toBeDefined());
  await act(async () => { poll?.(); });
  expect((await screen.findAllByText("50 %")).length).toBeGreaterThan(0);
  expect((await screen.findAllByText("openai", { exact: false })).length).toBeGreaterThan(0);
});

it("renders share of voice and reports polling failure", async () => {
  let poll: (() => void) | undefined;
  vi.spyOn(globalThis, "setInterval").mockImplementation((cb) => { poll = cb as () => void; return 1 as never; });
  vi.spyOn(globalThis, "clearInterval").mockImplementation(() => undefined);
  vi.spyOn(api, "runCitations").mockResolvedValue({ task_id: "task-2", status_url: "/tasks/task-2" });
  vi.spyOn(api, "getCitationTask").mockResolvedValue({ status: "done", metrics: { citation_rate: 0, mention_rate: 0, citation_confidence: 0, share_of_voice: 0.4, engines: [], prompt_count: 0, repetitions: 0, per_engine: {} } } as never);
  render(<MemoryRouter><I18nProvider><CitationPage /></I18nProvider></MemoryRouter>);
  fireEvent.change(screen.getAllByRole("textbox")[0], { target: { value: "example.com" } });
  fireEvent.click(screen.getByRole("button", { name: /run|start|launch/i }));
  await waitFor(() => expect(poll).toBeDefined());
  await act(async () => { poll?.(); });
  expect(await screen.findByText(/share of voice/i)).toBeInTheDocument();
});

it("reports a citation polling network failure", async () => {
  let poll: (() => void) | undefined;
  vi.spyOn(globalThis, "setInterval").mockImplementation((cb) => { poll = cb as () => void; return 1 as never; });
  vi.spyOn(globalThis, "clearInterval").mockImplementation(() => undefined);
  vi.spyOn(api, "runCitations").mockResolvedValue({ task_id: "task-3", status_url: "/tasks/task-3" });
  vi.spyOn(api, "getCitationTask").mockRejectedValue(new Error("offline"));
  render(<MemoryRouter><I18nProvider><CitationPage /></I18nProvider></MemoryRouter>);
  fireEvent.change(screen.getAllByRole("textbox")[0], { target: { value: "example.com" } });
  fireEvent.click(screen.getByRole("button", { name: /run|start|launch/i }));
  await waitFor(() => expect(poll).toBeDefined());
  await act(async () => { poll?.(); });
  expect(await screen.findByText(/Failed to load/i)).toBeInTheDocument();
});

it("reports a failed citation worker with its error", async () => {
  let poll: (() => void) | undefined;
  vi.spyOn(globalThis, "setInterval").mockImplementation((cb) => { poll = cb as () => void; return 1 as never; });
  vi.spyOn(globalThis, "clearInterval").mockImplementation(() => undefined);
  vi.spyOn(api, "runCitations").mockResolvedValue({ task_id: "task-4", status_url: "/tasks/task-4" });
  vi.spyOn(api, "getCitationTask").mockResolvedValue({ status: "failed", error: "Provider unavailable" } as never);
  render(<MemoryRouter><I18nProvider><CitationPage /></I18nProvider></MemoryRouter>);
  fireEvent.change(screen.getAllByRole("textbox")[0], { target: { value: "example.com" } });
  fireEvent.click(screen.getByRole("button", { name: /run|start|launch/i }));
  await waitFor(() => expect(poll).toBeDefined());
  await act(async () => { poll?.(); });
  expect(await screen.findByText("Provider unavailable")).toBeInTheDocument();
});

it("uses the translated fallback for an unnamed citation failure", async () => {
  let poll: (() => void) | undefined;
  vi.spyOn(globalThis, "setInterval").mockImplementation((cb) => { poll = cb as () => void; return 1 as never; });
  vi.spyOn(globalThis, "clearInterval").mockImplementation(() => undefined);
  vi.spyOn(api, "runCitations").mockResolvedValue({ task_id: "task-5", status_url: "/tasks/task-5" });
  vi.spyOn(api, "getCitationTask").mockResolvedValue({ status: "failed" } as never);
  render(<MemoryRouter><I18nProvider><CitationPage /></I18nProvider></MemoryRouter>);
  fireEvent.change(screen.getAllByRole("textbox")[0], { target: { value: "example.com" } });
  fireEvent.click(screen.getByRole("button", { name: /run|start|launch/i }));
  await waitFor(() => expect(poll).toBeDefined());
  await act(async () => { poll?.(); });
  expect(await screen.findByText(/Citation tracking failed/i)).toBeInTheDocument();
});

it("shows an API error message when citation start fails for another reason", async () => {
  vi.spyOn(api, "runCitations").mockRejectedValue(new ApiError(500, "provider down"));
  render(<MemoryRouter><I18nProvider><CitationPage /></I18nProvider></MemoryRouter>);
  fireEvent.change(screen.getAllByRole("textbox")[0], { target: { value: "example.com" } });
  fireEvent.click(screen.getByRole("button", { name: /run|start|launch/i }));
  expect(await screen.findByText("provider down")).toBeInTheDocument();
});

it("cleans up citation polling on unmount", async () => {
  let poll: (() => void) | undefined;
  const clear = vi.spyOn(globalThis, "clearInterval").mockImplementation(() => undefined);
  vi.spyOn(globalThis, "setInterval").mockImplementation((cb) => { poll = cb as () => void; return 1 as never; });
  vi.spyOn(api, "runCitations").mockResolvedValue({ task_id: "task-unmount", status_url: "/tasks/task-unmount" });
  vi.spyOn(api, "getCitationTask").mockReturnValue(new Promise(() => {}));
  const view = render(<MemoryRouter><I18nProvider><CitationPage /></I18nProvider></MemoryRouter>);
  fireEvent.change(screen.getAllByRole("textbox")[0], { target: { value: "example.com" } });
  fireEvent.click(screen.getByRole("button", { name: /run|start|launch/i }));
  await waitFor(() => expect(poll).toBeDefined());
  view.unmount();
  expect(clear).toHaveBeenCalled();
});
