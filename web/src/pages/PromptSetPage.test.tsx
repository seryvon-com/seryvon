import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { api, ApiError } from "../api/client";
import { I18nProvider } from "../i18n";
import { PromptSetPage } from "./PromptSetPage";

it("shows the prompt set loading state", () => {
  vi.spyOn(api, "getPromptSet").mockReturnValue(new Promise(() => {}));
  render(<MemoryRouter initialEntries={["/audits/a1/prompts"]}><I18nProvider><Routes><Route path="/audits/:auditId/prompts" element={<PromptSetPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(screen.getByText(/Loading/)).toBeInTheDocument();
});

it("shows the prompt set load error", async () => {
  vi.spyOn(api, "getPromptSet").mockRejectedValue(new Error("offline"));
  render(<MemoryRouter initialEntries={["/audits/a1/prompts"]}><I18nProvider><Routes><Route path="/audits/:auditId/prompts" element={<PromptSetPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByText(/Failed to load/)).toBeInTheDocument();
});

it("renders generated prompts and theme profile", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z" } as never);
  vi.spyOn(api, "getPromptSet").mockResolvedValue({ version: 1, domain: "example.com", generated_by: "test", theme_profile: { domain: "example.com", topics: ["SEO"], entities: ["Seryvon"], content_type: "unknown", brand: null }, prompts: [{ text: "What is Seryvon?", intent: "definitional", source: "theme", quality_score: 0.9 }, { text: "Low", intent: "comparative", source: "theme", quality_score: 0.3 }, { text: "Mid", intent: "recommendation", source: "theme", quality_score: 0.6 }, { text: "Fallback", intent: "unknown" as never, source: "theme", quality_score: 0.6 }], tracked_competitors: [] });
  render(<MemoryRouter initialEntries={["/audits/a1/prompts"]}><I18nProvider><Routes><Route path="/audits/:auditId/prompts" element={<PromptSetPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByText("What is Seryvon?")).toBeInTheDocument();
  expect(screen.getByText(/90%/)).toBeInTheDocument();
});

it("renders empty topic/entity states and the 404 empty-data message", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", started_at: "2026-09-09T10:00:00Z" } as never);
  vi.spyOn(api, "getPromptSet").mockResolvedValue({ version: 1, domain: "example.com", generated_by: "test", theme_profile: { domain: "example.com", topics: [], entities: [], content_type: "", brand: "" }, prompts: [], tracked_competitors: [] });
  render(<MemoryRouter initialEntries={["/audits/a1/prompts"]}><I18nProvider><Routes><Route path="/audits/:auditId/prompts" element={<PromptSetPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect((await screen.findAllByText("—")).length).toBeGreaterThan(0);
  vi.spyOn(api, "getPromptSet").mockRejectedValueOnce(new ApiError(404, "missing"));
  render(<MemoryRouter initialEntries={["/audits/a2/prompts"]}><I18nProvider><Routes><Route path="/audits/:auditId/prompts" element={<PromptSetPage />} /></Routes></I18nProvider></MemoryRouter>);
  expect(await screen.findByText(/No prompt set|Aucun jeu/i)).toBeInTheDocument();
});

it("keeps the prompt set page loading without an audit parameter", () => {
  render(<MemoryRouter><I18nProvider><PromptSetPage /></I18nProvider></MemoryRouter>);
  expect(screen.getByText(/Loading/)).toBeInTheDocument();
});

it("ignores a late prompt-set response after unmount", async () => {
  let resolveSet: ((value: unknown) => void) | undefined;
  const pending = new Promise((resolve) => { resolveSet = resolve; });
  vi.spyOn(api, "getAudit").mockReturnValue(new Promise(() => {}) as never);
  vi.spyOn(api, "getPromptSet").mockReturnValue(pending as never);
  const view = render(<MemoryRouter initialEntries={["/audits/a1/prompts"]}><I18nProvider><Routes><Route path="/audits/:auditId/prompts" element={<PromptSetPage />} /></Routes></I18nProvider></MemoryRouter>);
  view.unmount();
  resolveSet?.({ version: 1, theme_profile: { topics: [], entities: [] }, prompts: [] });
  await Promise.resolve();
});

it("ignores a late prompt-set error after unmount", async () => {
  let rejectSet: ((reason?: unknown) => void) | undefined;
  const pending = new Promise((_, reject) => { rejectSet = reject; });
  vi.spyOn(api, "getAudit").mockReturnValue(new Promise(() => {}) as never);
  vi.spyOn(api, "getPromptSet").mockReturnValue(pending as never);
  const view = render(<MemoryRouter initialEntries={["/audits/a1/prompts"]}><I18nProvider><Routes><Route path="/audits/:auditId/prompts" element={<PromptSetPage />} /></Routes></I18nProvider></MemoryRouter>);
  view.unmount();
  rejectSet?.(new Error("late"));
  await Promise.resolve();
});
