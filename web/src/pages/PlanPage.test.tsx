import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { ApiError, api } from "../api/client";
import { I18nProvider } from "../i18n";
import { PlanPage } from "./PlanPage";

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/audits/a1/plan"]}>
      <I18nProvider><Routes><Route path="/audits/:auditId/plan" element={<PlanPage />} /></Routes></I18nProvider>
    </MemoryRouter>,
  );
}

it("shows the plan loading state", () => {
  vi.spyOn(api, "getAudit").mockReturnValue(new Promise(() => {}));
  renderPage();
  expect(screen.getByText(/Loading/)).toBeInTheDocument();
});

it("renders an empty action plan after loading", async () => {
  vi.spyOn(api, "getAudit").mockResolvedValue({ domain: "example.com", issues: [] } as never);
  renderPage();
  await waitFor(() => expect(screen.getByText(/No priority action/)).toBeInTheDocument());
});

it("renders the localized not-found error", async () => {
  vi.spyOn(api, "getAudit").mockRejectedValue(new ApiError(404, "Not found"));
  renderPage();
  await waitFor(() => expect(screen.getByText(/not found/i)).toBeInTheDocument());
});

it("shows the generic error for an unexpected plan failure", async () => {
  vi.spyOn(api, "getAudit").mockRejectedValue(new Error("offline"));
  renderPage();
  await waitFor(() => expect(screen.getByText(/Failed to load|Échec du chargement/)).toBeInTheDocument());
});

it("keeps the shell in loading state without an audit parameter", () => {
  render(<MemoryRouter><I18nProvider><PlanPage /></I18nProvider></MemoryRouter>);
  expect(screen.getByText(/Loading|Chargement/)).toBeInTheDocument();
});

it("ignores a late plan response and error after unmount", async () => {
  let resolveAudit: ((value: unknown) => void) | undefined;
  const pending = new Promise((resolve) => { resolveAudit = resolve; });
  vi.spyOn(api, "getAudit").mockReturnValue(pending as never);
  const view = renderPage();
  view.unmount();
  resolveAudit?.({ domain: "late.example", issues: [] });
  await Promise.resolve();
});

it("ignores a late plan load failure after unmount", async () => {
  let rejectAudit: ((reason?: unknown) => void) | undefined;
  const pending = new Promise((_, reject) => { rejectAudit = reject; });
  vi.spyOn(api, "getAudit").mockReturnValue(pending as never);
  const view = renderPage();
  view.unmount();
  rejectAudit?.(new Error("late"));
  await Promise.resolve();
});
