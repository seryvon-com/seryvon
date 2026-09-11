import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { expect, it, vi } from "vitest";

import { I18nProvider } from "../i18n";
import { CriterionHint, InfoButton, ssrTier } from "./CriterionHint";

it("classifies SSR parity tiers", () => {
  expect(ssrTier(10)).toBe("thin");
  expect(ssrTier(30)).toBe("partial");
  expect(ssrTier(70)).toBe("near");
});

it("opens and closes an information tooltip", () => {
  render(<InfoButton label="Help"><span>Details</span></InfoButton>);
  const button = screen.getByRole("button", { name: "Help" });
  fireEvent.mouseEnter(button);
  expect(screen.getByRole("tooltip")).toHaveTextContent("Details");
  fireEvent.mouseLeave(button);
  expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
});

it("renders a criterion hint for known and unknown criteria", () => {
  const { rerender } = render(<I18nProvider><CriterionHint criterionKey="aeo.kg_presence" rawValue={null} /></I18nProvider>);
  fireEvent.click(screen.getByRole("button"));
  expect(screen.getByRole("dialog")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /fermer/i }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  rerender(<I18nProvider><CriterionHint criterionKey="unknown" rawValue={null} /></I18nProvider>);
  expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
});

it("closes an open hint on outside pointer and scroll", () => {
  render(<I18nProvider><CriterionHint criterionKey="meta.title" rawValue={null} /></I18nProvider>);
  fireEvent.click(screen.getByRole("button"));
  fireEvent.pointerDown(document.body);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button"));
  fireEvent.scroll(window);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("renders the detailed SSR route and offender breakdown", () => {
  render(<I18nProvider><CriterionHint criterionKey="geo.ssr" rawValue={{ by_route: [{ path: "/", csr: 2, ssr: 8 }], top_offenders: [{ url: "https://example.com/a", parity_pct: 20, delta: 80, raw_words: 20, rendered_words: 100 }], word_deltas: { home: { parity_pct: 20, raw_words: 20, rendered_words: 100, delta: 80 } } }} /></I18nProvider>);
  fireEvent.mouseEnter(screen.getByRole("button"));
  expect(screen.getByRole("tooltip")).toHaveTextContent("https://example.com/a");
  expect(screen.getByRole("tooltip")).toHaveTextContent("2 JS");
});

it("renders the empty SSR hint and all offender severity tiers", () => {
  const offenders = [
    { url: "https://example.com/thin", parity_pct: 10, delta: 1, raw_words: 1, rendered_words: 10 },
    { url: "https://example.com/partial", parity_pct: 40, delta: 2, raw_words: 2, rendered_words: 20 },
    { url: "https://example.com/near", parity_pct: 80, delta: 3, raw_words: 3, rendered_words: 30 },
  ];
  const { rerender } = render(<I18nProvider><CriterionHint criterionKey="geo.ssr" rawValue={null} /></I18nProvider>);
  fireEvent.click(screen.getByRole("button"));
  expect(screen.getByRole("dialog")).toBeInTheDocument();
  rerender(<I18nProvider><CriterionHint criterionKey="geo.ssr" rawValue={{ by_route: [{ path: "/", csr: 0, ssr: 1 }], top_offenders: offenders, word_deltas: {} }} /></I18nProvider>);
  fireEvent.mouseEnter(screen.getByRole("button"));
  expect(screen.getByRole("tooltip")).toHaveTextContent("0 JS");
  expect(screen.getByRole("tooltip")).toHaveTextContent("thin");
});

it("renders recognized and missing social platforms", () => {
  render(<I18nProvider><CriterionHint criterionKey="geo.cross_platform" rawValue={{ platforms: ["github", "linkedin"] }} /></I18nProvider>);
  fireEvent.mouseEnter(screen.getByRole("button"));
  const tooltip = screen.getByRole("tooltip");
  expect(tooltip).toHaveTextContent("✓ GitHub");
  expect(tooltip).toHaveTextContent("Twitter / X");
});

it("handles malformed platform data and flips tooltip above the trigger", () => {
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ top: 500, bottom: 520, left: 20, width: 20, height: 20 } as DOMRect);
  Object.defineProperty(window, "innerHeight", { value: 600, configurable: true });
  render(<I18nProvider><CriterionHint criterionKey="geo.cross_platform" rawValue={{ platforms: "invalid" }} /></I18nProvider>);
  fireEvent.mouseEnter(screen.getByRole("button"));
  expect(screen.getByRole("tooltip")).toHaveTextContent("Twitter / X");
  vi.restoreAllMocks();
});

it("renders hints across each pillar family", () => {
  const keys = ["aeo.comparison_tables", "aeo.author_credentials", "aeo.about_page", "aeo.defined_terms", "aeo.dates_structured", "aeo.answer_directness", "aeo.llm_citation", "geo.primary_sources", "geo.ssr", "geo.noise_ratio", "geo.entity_density", "geo.authors", "geo.freshness", "geo.citation_rate", "geo.mention_rate", "geo.citation_confidence", "geo.knowledge_presence", "geo.share_of_voice", "geo.citation_position", "aso.mcp_readiness", "aso.accessible_forms", "aso.brand_coherence", "aso.agent_access", "aso.agent_ready", "aso.action_schema", "aso.ai_discovery", "aso.nlweb", "gso.faqpage", "gso.howto", "gso.breadcrumb", "gso.itemlist", "gso.qa_format", "gso.cwv_eligible", "meta.title", "meta.description", "meta.canonical", "meta.robots", "meta.title_unique", "og.complete", "twitter.cards", "struct.h1", "struct.hierarchy", "struct.schema", "content.depth", "content.text_ratio", "links.internal", "links.orphans", "img.alt", "crawl.indexable", "crawl.sitemap", "crawl.https", "crawl.redirects", "i18n.hreflang", "perf.lcp", "perf.cls", "perf.inp", "perf.lighthouse", "authority.opr", "authority.backlinks", "seo.avg_position", "seo.click_through_rate"];
  for (const key of keys) {
    cleanup();
    render(<I18nProvider><CriterionHint criterionKey={key} rawValue={null} /></I18nProvider>);
    fireEvent.click(screen.getAllByRole("button")[0]);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  }
});
