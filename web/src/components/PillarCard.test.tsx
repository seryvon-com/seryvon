import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { expect, it } from "vitest";

import type { PillarScore } from "../api/types";
import { I18nProvider } from "../i18n";
import { PillarCard } from "./PillarCard";

const pillar: PillarScore = {
  pillar: "seo",
  score: 72.5,
  measured: 20,
  excluded: 2,
  not_applicable: 0,
  coverage: 0.75,
  coverage_label: "partial",
};

it("renders pillar score, coverage and counts", () => {
  render(<I18nProvider><PillarCard pillar={pillar} /></I18nProvider>);
  expect(screen.getByText("SEO")).toBeInTheDocument();
  expect(screen.getByText("73")).toBeInTheDocument();
  expect(screen.getByText("75%")).toBeInTheDocument();
  expect(screen.getByText(/20/)).toBeInTheDocument();
});

it("renders full coverage and unknown pillar fallbacks", () => {
  render(<I18nProvider><PillarCard pillar={{ ...pillar, pillar: "custom", score: 120, coverage: 1, coverage_label: "full" } as unknown as PillarScore} /></I18nProvider>);
  expect(screen.getByText("CUSTOM")).toBeInTheDocument();
  expect(screen.getByText("100")).toBeInTheDocument();
  expect(screen.queryByText("100%" )).not.toBeInTheDocument();
});
