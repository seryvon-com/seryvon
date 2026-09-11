import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { expect, it, vi } from "vitest";

import type { Issue } from "../api/types";
import { I18nProvider } from "../i18n";
import { TrackableIssue } from "./TrackableIssue";

const issue = {
  criterion_key: "meta.title",
  severity: "warning",
  impact: 2,
  effort: 1,
  priority_score: 2,
  priority_bucket: "high",
  recommendation: "Add a unique title",
  explanation: "Missing on one page",
  raw_value: null,
  affected_pages: ["https://example.com/page"],
} as Issue;

it("renders an issue, tracks completion, exports and adds a proof URL", () => {
  const onAddProof = vi.fn();
  const onToggle = vi.fn();
  const onSetDate = vi.fn();
  const createUrl = vi.fn(() => "blob:test");
  Object.defineProperty(URL, "createObjectURL", { value: createUrl, configurable: true });
  Object.defineProperty(URL, "revokeObjectURL", { value: vi.fn(), configurable: true });
  render(
    <I18nProvider>
      <TrackableIssue
        issue={issue}
        tracking={{ done: false, proofs: [] }}
        onToggle={onToggle}
        onSetDate={onSetDate}
        onAddProof={onAddProof}
        onRemoveProof={vi.fn()}
      />
    </I18nProvider>,
  );
  expect(screen.getByText("Add a unique title")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Mark as done" }));
  expect(onToggle).toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: /export as csv/i }));
  expect(createUrl).toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: /proof/i }));
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "example.org/fix" } });
  fireEvent.click(screen.getByTitle("Add URL"));
  expect(onAddProof).toHaveBeenCalledWith(expect.objectContaining({ type: "url", url: "https://example.org/fix" }));
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "http://example.org/secure" } });
  fireEvent.click(screen.getByTitle("Add URL"));
  expect(onAddProof).toHaveBeenLastCalledWith(expect.objectContaining({ url: "http://example.org/secure" }));
});

it("renders a completed issue with its date and proof", () => {
  const completed = { ...issue, affected_pages: ["https://example.com/1", "https://example.com/2", "https://example.com/3", "https://example.com/4", "https://example.com/5", "https://example.com/6"] } as Issue;
  render(<I18nProvider><TrackableIssue issue={completed} tracking={{ done: true, doneAt: "2026-09-09", proofs: [{ id: "p1", type: "url", url: "https://proof.example" }] }} onToggle={vi.fn()} onSetDate={vi.fn()} onAddProof={vi.fn()} onRemoveProof={vi.fn()} /></I18nProvider>);
  expect(screen.getByRole("button", { name: /mark as not done/i })).toBeInTheDocument();
  expect(screen.getByDisplayValue("2026-09-09")).toBeInTheDocument();
  expect(screen.getByText("proof.example")).toBeInTheDocument();
});

it("renders and removes a PDF proof on a regressed issue", () => {
  const onRemoveProof = vi.fn();
  render(<I18nProvider><TrackableIssue issue={{ ...issue, affected_pages: [] } as Issue} currentAuditId="a2" tracking={{ done: true, doneAt: "2026-09-08", doneInAuditId: "a1", proofs: [{ id: "pdf", type: "pdf", name: "report.pdf" }] }} onToggle={vi.fn()} onSetDate={vi.fn()} onAddProof={vi.fn()} onRemoveProof={onRemoveProof} /></I18nProvider>);
  expect(screen.getByText(/regressed/i)).toBeInTheDocument();
  const thumb = screen.getByText("report.pdf").closest(".proof-thumb") as HTMLElement;
  fireEvent.mouseEnter(thumb);
  fireEvent.click(screen.getByRole("button", { name: "×" }));
  fireEvent.mouseLeave(thumb);
  expect(onRemoveProof).toHaveBeenCalledWith("pdf");
});

it("handles an invalid proof URL and opens an image proof", () => {
  const opened = vi.fn(() => ({ document: { write: vi.fn() } }));
  vi.stubGlobal("open", opened);
  render(<I18nProvider><TrackableIssue issue={issue} tracking={{ done: false, proofs: [{ id: "bad", type: "url", url: "not a url", name: "fallback" }, { id: "bare", type: "url", url: "bad" }, { id: "empty", type: "url" }, { id: "img", type: "image", dataUrl: "data:image/png;base64,x", name: "image.png" }] }} onToggle={vi.fn()} onSetDate={vi.fn()} onAddProof={vi.fn()} onRemoveProof={vi.fn()} /></I18nProvider>);
  expect(screen.getByText("fallback")).toBeInTheDocument();
  fireEvent.click(screen.getByAltText("image.png"));
  expect(opened).toHaveBeenCalled();
  vi.unstubAllGlobals();
});

it("adds an image proof from a local file", () => {
  const onAddProof = vi.fn();
  class MockReader {
    result = "data:image/png;base64,abc";
    onload: (() => void) | null = null;
    readAsDataURL() { this.onload?.(); }
  }
  vi.stubGlobal("FileReader", MockReader);
  const { container } = render(<I18nProvider><TrackableIssue issue={issue} tracking={{ done: false, proofs: [] }} onToggle={vi.fn()} onSetDate={vi.fn()} onAddProof={onAddProof} onRemoveProof={vi.fn()} /></I18nProvider>);
  fireEvent.click(screen.getByRole("button", { name: /proof/i }));
  fireEvent.click(screen.getByTitle(/attach file/i));
  const input = container.querySelector('input[type="file"]') as HTMLInputElement;
  fireEvent.change(input, { target: { files: [new File(["image"], "proof.png", { type: "image/png" })] } });
  expect(onAddProof).toHaveBeenCalledWith(expect.objectContaining({ type: "image", name: "proof.png", dataUrl: "data:image/png;base64,abc" }));
  fireEvent.change(input, { target: { files: [new File(["pdf"], "report.pdf", { type: "application/pdf" })] } });
  expect(onAddProof).toHaveBeenCalledWith(expect.objectContaining({ type: "pdf", name: "report.pdf" }));
  vi.unstubAllGlobals();
});

it("rejects an oversized local proof", () => {
  const onAddProof = vi.fn();
  const alertMock = vi.fn();
  vi.stubGlobal("alert", alertMock);
  const { container } = render(<I18nProvider><TrackableIssue issue={issue} tracking={{ done: false, proofs: [] }} onToggle={vi.fn()} onSetDate={vi.fn()} onAddProof={onAddProof} onRemoveProof={vi.fn()} /></I18nProvider>);
  fireEvent.click(screen.getByRole("button", { name: /proof/i }));
  const oversized = new File([new Uint8Array(11 * 1024 * 1024)], "large.pdf", { type: "application/pdf" });
  fireEvent.change(container.querySelector('input[type="file"]') as HTMLInputElement, { target: { files: [oversized] } });
  expect(alertMock).toHaveBeenCalled();
  expect(onAddProof).not.toHaveBeenCalled();
  vi.unstubAllGlobals();
});

it("exports SSR word deltas and renders architectural page metadata", () => {
  const createUrl = vi.fn(() => "blob:ssr");
  Object.defineProperty(URL, "createObjectURL", { value: createUrl, configurable: true });
  Object.defineProperty(URL, "revokeObjectURL", { value: vi.fn(), configurable: true });
  const first = "https://example.com/ssr";
  const view = render(<I18nProvider><TrackableIssue issue={{ ...issue, criterion_key: "geo.ssr", affected_pages: [first, "https://example.com/other"], raw_value: { word_deltas: { [first]: { raw_words: 100, rendered_words: 90, delta: -10, parity_pct: 90 } } } } as Issue} tracking={{ done: false, proofs: [] }} onToggle={vi.fn()} onSetDate={vi.fn()} onAddProof={vi.fn()} onRemoveProof={vi.fn()} /></I18nProvider>);
  expect(screen.getByTitle(/90% parity/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /export as csv/i }));
  expect(createUrl).toHaveBeenCalled();
  view.rerender(<I18nProvider><TrackableIssue issue={{ ...issue, criterion_key: "geo.ssr", affected_pages: [first], raw_value: null } as Issue} tracking={{ done: false, proofs: [] }} onToggle={vi.fn()} onSetDate={vi.fn()} onAddProof={vi.fn()} onRemoveProof={vi.fn()} /></I18nProvider>);
  fireEvent.click(screen.getByRole("button", { name: /export as csv/i }));
});

it("covers optional issue fields and proof edge cases", () => {
  const opened = vi.fn(() => null);
  vi.stubGlobal("open", opened);
  const { container } = render(<I18nProvider><TrackableIssue issue={{ ...issue, recommendation: "", explanation: "", affected_pages: [] } as Issue} tracking={{ done: false, proofs: [{ id: "pdf", type: "pdf" }, { id: "img", type: "image", dataUrl: "data:image/png;base64,x" }, { id: "url", type: "url", url: "https://valid.test" }] }} onToggle={vi.fn()} onSetDate={vi.fn()} onAddProof={vi.fn()} onRemoveProof={vi.fn()} /></I18nProvider>);
  expect(screen.getByText("document.pdf")).toBeInTheDocument();
  fireEvent.click(screen.getByAltText("proof"));
  fireEvent.click(screen.getByText("valid.test"));
  expect(opened).toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: /proof/i }));
  fireEvent.click(screen.getByTitle("Add URL"));
  const input = container.querySelector('input[type="file"]') as HTMLInputElement;
  fireEvent.change(input, { target: { files: [] } });
  const noName = screen.getByText("document.pdf");
  expect(noName).toBeInTheDocument();
  vi.unstubAllGlobals();
});

it("supports date changes, page expansion, CSV fallback and proof removal", () => {
  const onSetDate = vi.fn();
  const onRemoveProof = vi.fn();
  const pages = Array.from({ length: 7 }, (_, i) => `https://example.com/${i}`);
  const { container } = render(<I18nProvider><TrackableIssue issue={{ ...issue, affected_pages: pages, raw_value: { word_deltas: { [pages[0]]: { raw_words: 10, rendered_words: 8, delta: -2, parity_pct: 80 } } } } as Issue} tracking={{ done: true, doneAt: "2026-09-09", proofs: [{ id: "u", type: "url", url: "https://proof.test" }] }} onToggle={vi.fn()} onSetDate={onSetDate} onAddProof={vi.fn()} onRemoveProof={onRemoveProof} /></I18nProvider>);
  fireEvent.change(screen.getByDisplayValue("2026-09-09"), { target: { value: "2026-09-10" } });
  expect(onSetDate).toHaveBeenCalledWith("2026-09-10");
  fireEvent.click(screen.getByTitle("Show all pages"));
  expect(screen.getByText("https://example.com/6")).toBeInTheDocument();
  fireEvent.click(screen.getByText("▲"));
  fireEvent.mouseEnter(container.querySelector(".proof-thumb") as HTMLElement);
  fireEvent.click(screen.getByRole("button", { name: "×" }));
  expect(onRemoveProof).toHaveBeenCalledWith("u");
});

it("renders a completed issue without a completion date", () => {
  render(<I18nProvider><TrackableIssue issue={{ ...issue, affected_pages: [] } as Issue} tracking={{ done: true, proofs: [] }} onToggle={vi.fn()} onSetDate={vi.fn()} onAddProof={vi.fn()} onRemoveProof={vi.fn()} /></I18nProvider>);
  expect(screen.getByRole("button", { name: /mark as not done/i })).toBeInTheDocument();
  expect(screen.getByDisplayValue("")).toBeInTheDocument();
});

it("handles a null SSR word-delta map", () => {
  Object.defineProperty(URL, "createObjectURL", { value: vi.fn(() => "blob:null"), configurable: true });
  render(<I18nProvider><TrackableIssue issue={{ ...issue, criterion_key: "geo.ssr", recommendation: "", affected_pages: ["https://example.com/page"], raw_value: { word_deltas: null } } as Issue} tracking={{ done: false, proofs: [] }} onToggle={vi.fn()} onSetDate={vi.fn()} onAddProof={vi.fn()} onRemoveProof={vi.fn()} /></I18nProvider>);
  expect(screen.getByText("https://example.com/page")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /export as csv/i }));
});
