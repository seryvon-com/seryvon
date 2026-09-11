import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { beforeEach, expect, it, vi } from "vitest";
import { I18nProvider } from "../i18n";
import { useIssueTracking } from "./useIssueTracking";

beforeEach(() => localStorage.clear());

function Probe({ domain }: { domain?: string }) {
  const tracking = useIssueTracking(domain);
  const current = tracking.getTracking("issue");
  return <div>
    <span data-testid="state">{String(current.done)}:{current.proofs.length}:{current.doneAt ?? "none"}</span>
    <button onClick={() => tracking.toggleDone("issue", "audit-1")}>toggle</button>
    <button onClick={() => tracking.setDoneAt("issue", "2026-09-09")}>date</button>
    <button onClick={() => tracking.addProof("issue", { id: "p1", type: "url", url: "https://proof.test" })}>add</button>
    <button onClick={() => tracking.removeProof("issue", "p1")}>remove</button>
    <button onClick={() => tracking.setDoneAt("other", "2026-09-10")}>date-other</button>
    <button onClick={() => tracking.addProof("other", { id: "p2", type: "url" })}>add-other</button>
    <button onClick={() => tracking.addProof("missing-add", { id: "p4", type: "url" })}>add-missing</button>
    <button onClick={() => tracking.removeProof("other", "p2")}>remove-other</button>
    <button onClick={() => tracking.removeProof("missing", "p3")}>remove-missing</button>
  </div>;
}

it("provides defaults without a domain and persists tracking changes", () => {
  const { rerender } = render(<I18nProvider><Probe /></I18nProvider>);
  expect(screen.getByTestId("state")).toHaveTextContent("false:0:none");
  fireEvent.click(screen.getByText("toggle"));
  fireEvent.click(screen.getByText("date"));
  fireEvent.click(screen.getByText("add"));
  fireEvent.click(screen.getByText("remove"));
  expect(screen.getByTestId("state")).toHaveTextContent("false:0:none");
  rerender(<I18nProvider><Probe domain="example.com" /></I18nProvider>);
  fireEvent.click(screen.getByText("date-other"));
  fireEvent.click(screen.getByText("add-other"));
  fireEvent.click(screen.getByText("remove-other"));
  fireEvent.click(screen.getByText("remove-missing"));
  fireEvent.click(screen.getByText("add-missing"));
  fireEvent.click(screen.getByText("toggle"));
  fireEvent.click(screen.getByText("date"));
  fireEvent.click(screen.getByText("add"));
  expect(screen.getByTestId("state")).toHaveTextContent("true:1:2026-09-09");
  fireEvent.click(screen.getByText("remove"));
  expect(screen.getByTestId("state")).toHaveTextContent("true:0:2026-09-09");
});

it("recovers from malformed persisted tracking JSON", () => {
  localStorage.setItem("seryvon:tracking:domain:example.com", "{");
  render(<I18nProvider><Probe domain="example.com" /></I18nProvider>);
  expect(screen.getByTestId("state")).toHaveTextContent("false:0:none");
});

it("loads existing tracking and tolerates storage quota failures", () => {
  localStorage.setItem("seryvon:tracking:domain:example.com", JSON.stringify({ issue: { done: true, doneAt: "2026-09-01", proofs: [] } }));
  const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("quota"); });
  render(<I18nProvider><Probe domain="example.com" /></I18nProvider>);
  expect(screen.getByTestId("state")).toHaveTextContent("true:0:2026-09-01");
  fireEvent.click(screen.getByText("toggle"));
  fireEvent.click(screen.getByText("date"));
  fireEvent.click(screen.getByText("add"));
  fireEvent.click(screen.getByText("remove"));
  expect(setItem).toHaveBeenCalled();
  setItem.mockRestore();
});
