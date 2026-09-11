import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { expect, it } from "vitest";

import { I18nProvider } from "../i18n";
import { IssueList } from "./IssueList";
import type { Issue } from "../api/types";

it("renders the localized empty action-plan state", () => {
  render(<I18nProvider><IssueList issues={[]} /></I18nProvider>);
  expect(screen.getByText(/No priority action/)).toBeInTheDocument();
});

it("renders a prioritized issue", () => {
  const issue = { criterion_key: "meta.title", severity: "warning", impact: 1, effort: 1, priority_score: 1, priority_bucket: "medium", recommendation: "Add a title", explanation: "Missing", raw_value: null, affected_pages: [] } as Issue;
  render(<I18nProvider><IssueList issues={[issue]} /></I18nProvider>);
  expect(screen.getByText("Add a title")).toBeInTheDocument();
});

it("wires tracking actions for a domain-scoped issue", async () => {
  const issue = { criterion_key: "meta.title", severity: "warning", impact: 1, effort: 1, priority_score: 1, priority_bucket: "medium", recommendation: "Add a title", explanation: "Missing", raw_value: null, affected_pages: [] } as Issue;
  localStorage.setItem("seryvon:tracking:domain:example.com", JSON.stringify({ "meta.title": { done: false, proofs: [{ id: "p1", type: "url", url: "https://proof.test" }] } }));
  const { container } = render(<I18nProvider><IssueList issues={[issue]} auditId="a1" domain="example.com" /></I18nProvider>);
  fireEvent.click(screen.getByRole("button", { name: /Mark as done/i }));
  await waitFor(() => expect(container.querySelector('input[type="date"]')).toBeInTheDocument());
  fireEvent.change(container.querySelector('input[type="date"]') as HTMLInputElement, { target: { value: "2026-09-09" } });
  await waitFor(() => expect(localStorage.getItem("seryvon:tracking:domain:example.com")).toContain("2026-09-09"));
  fireEvent.click(screen.getByRole("button", { name: /proof/i }));
  const url = screen.queryByRole("textbox");
  if (url) {
    fireEvent.change(url, { target: { value: "https://proof.test" } });
    fireEvent.keyDown(url, { key: "Enter" });
  }
  await waitFor(() => expect(screen.getAllByText("proof.test").length).toBeGreaterThan(0));
  fireEvent.mouseEnter(screen.getAllByText("proof.test")[0].closest(".proof-thumb") as HTMLElement);
  fireEvent.click(screen.getByRole("button", { name: "×" }));
});
