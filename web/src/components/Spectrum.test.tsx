import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { expect, it } from "vitest";

import type { AuditReport } from "../api/types";
import { I18nProvider } from "../i18n";
import { Spectrum } from "./Spectrum";

it("renders available pillar bars and skips missing pillars", () => {
  const report = { pillars: {
    seo: { score: 81 }, geo: { score: 42 },
  } } as unknown as AuditReport;
  render(<I18nProvider><Spectrum report={report} /></I18nProvider>);
  expect(screen.getByText("SEO")).toBeInTheDocument();
  expect(screen.getByText("81")).toBeInTheDocument();
  expect(screen.getByText("GEO")).toBeInTheDocument();
  expect(screen.queryByText("GSO")).not.toBeInTheDocument();
});
