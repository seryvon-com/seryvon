import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { expect, it } from "vitest";

import type { AuditReport } from "../api/types";
import { I18nProvider } from "../i18n";
import { CriteriaTable } from "./CriteriaTable";

const report = {
  criteria: [
    { key: "meta.title", pillars: ["seo"], status: "ok", score: 90, weight: 1, explanation: "Good", raw_value: "Title", threshold: { min: 1 }, evidence: {}, evidence_tier: "standard" },
    { key: "struct.schema", pillars: ["seo"], status: "not_measured", score: 0, weight: 1, explanation: "Unavailable", raw_value: null, threshold: {}, evidence: {}, evidence_tier: "standard" },
  ],
} as unknown as AuditReport;

it("renders criteria and toggles a status filter", () => {
  render(<I18nProvider><CriteriaTable report={report} /></I18nProvider>);
  expect(screen.getByText("meta.title")).toBeInTheDocument();
  expect(screen.getByText("Unavailable")).toBeInTheDocument();
  fireEvent.click(screen.getAllByRole("button", { name: /OK/i })[0]);
  expect(screen.queryByText("meta.title")).not.toBeInTheDocument();
  const statusButtons = document.querySelectorAll(".filter-chips.status button");
  fireEvent.click(statusButtons[1] as HTMLElement);
  fireEvent.click(statusButtons[2] as HTMLElement);
  expect(screen.getByText("struct.schema")).toBeInTheDocument();
});

it("filters by pillar and expands criterion traceability", () => {
  render(<I18nProvider><CriteriaTable report={report} /></I18nProvider>);
  fireEvent.click(document.querySelector(".filter-chips button") as HTMLElement);
  fireEvent.click(document.querySelector(".crit-summary") as HTMLElement);
  expect(screen.getByText("Good")).toBeInTheDocument();
});

it("renders rich traceability values, experimental tier and empty state", () => {
  const rich = {
    criteria: [
      { key: "custom.unknown", pillars: ["seo", "custom"], status: "warning", score: 72.3456, weight: 1.25, explanation: "Needs work", raw_value: ["one", 2], threshold: { min: 10, max: 20 }, evidence: { source: { url: "https://example.test" } }, evidence_tier: "experimental" },
    ],
  } as unknown as AuditReport;
  render(<I18nProvider><CriteriaTable report={rich} /></I18nProvider>);
  expect(screen.getAllByText("CUSTOM").length).toBeGreaterThan(0);
  expect(screen.getByText(/experimental/i)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /custom\.unknown/i }));
  expect(screen.getByText("one, 2")).toBeInTheDocument();
  expect(screen.getByText("min: 10")).toBeInTheDocument();
  expect(screen.getByText(/example\.test/)).toBeInTheDocument();

  fireEvent.click(document.querySelector(".filter-chips:not(.status) button:nth-child(2)") as HTMLElement);
  expect(document.querySelector(".crit-key")?.textContent).toBe("custom.unknown");

});

it("renders the empty criteria state", () => {
  render(<I18nProvider><CriteriaTable report={{ criteria: [] } as unknown as AuditReport} /></I18nProvider>);
  expect(screen.getByText(/No criterion|Aucun critère/i)).toBeInTheDocument();
});

it("covers every criterion status and optional traceability field", () => {
  const report = { criteria: [
    { key: "critical.item", pillars: ["seo"], status: "critical", score: 0, weight: 1, explanation: "", raw_value: "", threshold: { min: 0 }, evidence: { note: "x" }, evidence_tier: "standard" },
    { key: "na.item", pillars: ["geo"], status: "not_applicable", score: 0, weight: 1, explanation: "N/A", raw_value: {}, threshold: {}, evidence: {}, evidence_tier: "standard" },
    { key: "orphan.item", pillars: [], status: "ok", score: 101, weight: 0, explanation: "", raw_value: [], threshold: {}, evidence: {}, evidence_tier: "standard" },
  ] } as unknown as AuditReport;
  render(<I18nProvider><CriteriaTable report={report} /></I18nProvider>);
  expect(screen.getByRole("button", { name: /critical\.item/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /orphan\.item/ })).toBeInTheDocument();
  fireEvent.click(document.querySelector(".crit-summary") as HTMLElement);
  expect(screen.getByText(/No explanation|Aucune explication/i)).toBeInTheDocument();
  document.querySelectorAll(".filter-chips.status button").forEach((button) => fireEvent.click(button));
  expect(screen.getByText(/No criterion|Aucun critère/i)).toBeInTheDocument();
});

it("formats empty arrays, objects, numbers and custom pillar groups", () => {
  const report = { criteria: [
    { key: "custom.array", pillars: ["seo"], status: "warning", score: 12.3456, weight: 1, explanation: "x", raw_value: [], threshold: { max: 2.5 }, evidence: { count: 3.14159 }, evidence_tier: "standard" },
    { key: "custom.object", pillars: ["seo"], status: "ok", score: 10, weight: 1, explanation: "y", raw_value: { enabled: true }, threshold: {}, evidence: {}, evidence_tier: "standard" },
    { key: "custom.pillar", pillars: ["custom"], status: "ok", score: 10, weight: 1, explanation: "z", raw_value: "v", threshold: {}, evidence: {}, evidence_tier: "standard" },
    { key: "custom.null-trace", pillars: ["seo"], status: "ok", score: 10, weight: 1, explanation: "n", raw_value: "v", threshold: null, evidence: null, evidence_tier: "standard" },
  ] } as unknown as AuditReport;
  render(<I18nProvider><CriteriaTable report={report} /></I18nProvider>);
  expect(screen.getAllByText("SEO").length).toBeGreaterThan(0);
  expect(screen.getAllByText("CUSTOM").length).toBeGreaterThan(0);
  fireEvent.click(screen.getByRole("button", { name: /custom\.array/ }));
  expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  fireEvent.click(screen.getByRole("button", { name: /custom\.object/ }));
  expect(screen.getByText(/enabled/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /custom\.null-trace/ }));
});

it("excludes criteria from another pillar and toggles filters and rows back", () => {
  const mixed = { criteria: [
    { key: "seo.item", pillars: ["seo"], status: "ok", score: 80, weight: 1, explanation: "seo", raw_value: "x", threshold: {}, evidence: {} },
    { key: "geo.item", pillars: ["geo"], status: "warning", score: 60, weight: 1, explanation: "geo", raw_value: "y", threshold: {}, evidence: {} },
  ] } as unknown as AuditReport;
  render(<I18nProvider><CriteriaTable report={mixed} /></I18nProvider>);
  const toolbar = document.querySelector(".filter-chips:not(.status)") as HTMLElement;
  fireEvent.click(toolbar.querySelector("button:nth-child(2)") as HTMLElement);
  expect(screen.getAllByText("seo.item").length).toBeGreaterThan(0);
  expect(screen.queryAllByText("geo.item")).toHaveLength(0);
  const row = screen.getByRole("button", { name: /seo\.item/ });
  fireEvent.click(row);
  fireEvent.click(row);
  const status = document.querySelector(".filter-chips.status button") as HTMLElement;
  fireEvent.click(status);
  fireEvent.click(status);
  expect(screen.getAllByText("seo.item").length).toBeGreaterThan(0);
});
