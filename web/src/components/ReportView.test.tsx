import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { expect, it } from "vitest";

import type { AuditReport } from "../api/types";
import { I18nProvider } from "../i18n";
import { formatReportDuration, ReportView } from "./ReportView";
import { durationParts } from "../lib/format";

const report = {
  domain: "example.com",
  tool_version: "test",
  schema_version: 1,
  started_at: "2026-01-01T00:00:00Z",
  finished_at: "2026-01-01T00:01:05Z",
  score_global: 72,
  coverage: 0.8,
  pillars: {},
  criteria: [
    { key: "geo.primary_sources", status: "ok", raw_value: { pages: 3 } },
    { key: "x", status: "not_measured", raw_value: null },
  ],
  issues: [],
  aso_readiness: null,
} as unknown as AuditReport;

it("renders report summary and measured page count", () => {
  render(<I18nProvider><ReportView report={report} /></I18nProvider>);
  expect(screen.getByText("72")).toBeInTheDocument();
  expect(screen.getByText("3")).toBeInTheDocument();
  expect(screen.getByText(/65|1.*05/)).toBeInTheDocument();
});

it("formats every report duration shape", () => {
  const seconds = (value: number) => `s${value}`;
  const minutes = (m: number, s: number) => `m${m}:${s}`;
  expect(formatReportDuration(durationParts("2026-01-01T00:00:00Z", "2026-01-01T00:00:02Z"), seconds, minutes)).toBe("s2");
  expect(formatReportDuration(durationParts("2026-01-01T00:00:00Z", "2026-01-01T00:01:02Z"), seconds, minutes)).toBe("m1:2");
  expect(formatReportDuration(durationParts("2026-01-01T00:00:00Z", null), seconds, minutes)).toBe("—");
});

it("renders an incomplete report without optional sections", () => {
  const incomplete = { ...report, finished_at: null, criteria: [], score_global: 0, coverage: 0 } as unknown as AuditReport;
  render(<I18nProvider><ReportView report={incomplete} /></I18nProvider>);
  expect(screen.getAllByText("0").length).toBeGreaterThan(0);
  expect(screen.getByText("—")).toBeInTheDocument();
});

it("renders ASO readiness in the report summary", () => {
  const withAso = { ...report, aso_readiness: { readiness_level: "ready", has_webmcp: true, ai_discovery_endpoints: 1 }, pillars: {} } as unknown as AuditReport;
  render(<I18nProvider><ReportView report={withAso} /></I18nProvider>);
  expect(document.querySelector(".aso-band")).toBeInTheDocument();
});

it("passes the ASO pillar score into the readiness band", () => {
  const withScore = { ...report, aso_readiness: { readiness_level: "ready", has_webmcp: true, ai_discovery_endpoints: 1 }, pillars: { aso: { pillar: "aso", score: 81, coverage: 1, coverage_label: "full" } } } as unknown as AuditReport;
  render(<I18nProvider><ReportView report={withScore} /></I18nProvider>);
  expect(document.querySelector(".aso-band")).toBeInTheDocument();
  expect(screen.getAllByText("81").length).toBeGreaterThan(0);
});

it("formats minute durations and omits unavailable crawl totals", () => {
  const longer = { ...report, started_at: "2026-01-01T00:00:00Z", finished_at: "2026-01-01T00:02:05Z", criteria: [{ key: "geo.primary_sources", status: "ok", raw_value: {} }] } as unknown as AuditReport;
  render(<I18nProvider><ReportView report={longer} /></I18nProvider>);
  expect(screen.getByText(/2.*05|2 min/i)).toBeInTheDocument();
});

it("shows an em dash for an invalid duration", () => {
  const invalid = { ...report, finished_at: "not-a-date" } as unknown as AuditReport;
  render(<I18nProvider><ReportView report={invalid} /></I18nProvider>);
  expect(screen.getByText("—")).toBeInTheDocument();
});
