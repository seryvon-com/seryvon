import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { expect, it, vi } from "vitest";

import { api } from "../api/client";
import type { PageRow } from "../api/types";
import { CrawledPages, csvRow, nextSortDirection, renderBadge, sortValue, statusColor } from "./CrawledPages";

const pages = [
  { url: "https://example.com/a", status_code: 200, render_mode: "ssr", word_count: 100, raw_word_count: 90, rendered_word_count: 100, images_missing_alt: 1, images_total: 2, forms_total: 1, agent_usable_forms: 1 },
  { url: "https://example.com/b", status_code: 404, render_mode: "csr", word_count: null, raw_word_count: null, rendered_word_count: null, images_missing_alt: 0, images_total: 0, forms_total: 0, agent_usable_forms: 0 },
] as PageRow[];

it("renders, filters, sorts and exports crawled pages", async () => {
  vi.spyOn(api, "getAuditPages").mockResolvedValue(pages);
  const createUrl = vi.fn(() => "blob:test");
  Object.defineProperty(URL, "createObjectURL", { value: createUrl, configurable: true });
  Object.defineProperty(URL, "revokeObjectURL", { value: vi.fn(), configurable: true });
  render(<CrawledPages auditId="a1" />);
  expect(screen.queryByText("Pages crawlées")).not.toBeInTheDocument();
  await waitFor(() => expect(screen.getByText("Pages crawlées")).toBeInTheDocument());
  expect(screen.getByText("https://example.com/a")).toBeInTheDocument();
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "/b" } });
  expect(screen.queryByText("https://example.com/a")).not.toBeInTheDocument();
  fireEvent.click(screen.getByTitle(/Exporter/));
  expect(createUrl).toHaveBeenCalled();
});

it("sorts numeric columns and renders null metrics safely", async () => {
  vi.spyOn(api, "getAuditPages").mockResolvedValue([{ ...pages[0], url: "https://example.com/null", status_code: null, images_missing_alt: null, images_total: null, forms_total: 0, raw_word_count: 100, rendered_word_count: 80 }, { ...pages[0], url: "https://example.com/high", word_count: 500, images_missing_alt: 0, images_total: 0, forms_total: 2, agent_usable_forms: 1 }]);
  render(<CrawledPages auditId="a1" />);
  await waitFor(() => expect(screen.getByText("https://example.com/null")).toBeInTheDocument());
  const headers = document.querySelectorAll(".crawled-pages-table th");
  fireEvent.click(headers[3] as HTMLElement);
  fireEvent.click(headers[3] as HTMLElement);
  expect(screen.getAllByText("—").length).toBeGreaterThan(0);
});

it("expands a result set larger than fifty pages", async () => {
  vi.spyOn(api, "getAuditPages").mockResolvedValue(Array.from({ length: 51 }, (_, i) => ({ ...pages[0], url: `https://example.com/${i}` })));
  render(<CrawledPages auditId="a1" />);
  const more = await screen.findByRole("button", { name: /Voir les 1 autres/i });
  fireEvent.click(more);
  expect(screen.getByText("https://example.com/50")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Réduire/i })).toBeInTheDocument();
});

it("covers status, render badges, metric deltas and column help", async () => {
  vi.spyOn(api, "getAuditPages").mockResolvedValue([
    { ...pages[0], url: "https://example.com/redirect", status_code: 301, render_mode: "hydrated", raw_word_count: 100, rendered_word_count: 90, svg_missing_name: 1, svg_total: 2, forms_total: 2, agent_usable_forms: 1 },
    { ...pages[0], url: "https://example.com/server-error", status_code: 500, render_mode: null, raw_word_count: null, rendered_word_count: null, svg_missing_name: null, svg_total: null, forms_total: 1, agent_usable_forms: 1 },
    { ...pages[0], url: "https://example.com/forms-unknown", forms_total: 2, agent_usable_forms: null },
    { ...pages[0], url: "https://example.com/forms-null-total", forms_total: null, agent_usable_forms: 1 },
  ] as PageRow[]);
  render(<CrawledPages auditId="a1" />);
  await waitFor(() => expect(screen.getByText("https://example.com/redirect")).toBeInTheDocument());
  expect(screen.getByText("HYDRATED")).toBeInTheDocument();
  expect(screen.getByText("-10")).toBeInTheDocument();
  expect(screen.getAllByText("1/2").length).toBeGreaterThan(0);
  const help = screen.getByRole("button", { name: /HTTP — aide/i });
  fireEvent.mouseEnter(help);
  expect(screen.getByText(/Code de statut HTTP/)).toBeInTheDocument();
  fireEvent.click(help);
});

it("sorts every supported column", async () => {
  vi.spyOn(api, "getAuditPages").mockResolvedValue([{ ...pages[0], url: "https://example.com/sort", render_mode: "ssr", svg_missing_name: 0, svg_total: 1, forms_total: 0, agent_usable_forms: 0 } as PageRow, { ...pages[0], url: "https://example.com/sort2", render_mode: "ssr", svg_missing_name: 0, svg_total: 1, forms_total: 0, agent_usable_forms: 0 } as PageRow]);
  render(<CrawledPages auditId="a1" />);
  await waitFor(() => expect(screen.getByText("https://example.com/sort")).toBeInTheDocument());
  const headers = document.querySelectorAll(".crawled-pages-table th");
  for (let i = 0; i < headers.length; i += 1) {
    fireEvent.click(headers[i] as HTMLElement);
    fireEvent.click(headers[i] as HTMLElement);
  }
});

it("orders distinct values in both directions", async () => {
  vi.spyOn(api, "getAuditPages").mockResolvedValue([
    { ...pages[0], url: "https://example.com/z", status_code: 500, render_mode: "csr", word_count: 300, raw_word_count: 100, rendered_word_count: 300, images_missing_alt: 2, images_total: 3, svg_missing_name: 2, svg_total: 3, forms_total: 3, agent_usable_forms: 1 },
    { ...pages[0], url: "https://example.com/a", status_code: 200, render_mode: "ssr", word_count: 100, raw_word_count: 100, rendered_word_count: 50, images_missing_alt: 0, images_total: 1, svg_missing_name: 0, svg_total: 1, forms_total: 1, agent_usable_forms: 1 },
  ] as PageRow[]);
  render(<CrawledPages auditId="a1" />);
  await waitFor(() => expect(screen.getByText("https://example.com/z")).toBeInTheDocument());
  const headers = document.querySelectorAll(".crawled-pages-table th");
  for (let i = 0; i < headers.length; i += 1) {
    fireEvent.click(headers[i] as HTMLElement);
    fireEvent.click(headers[i] as HTMLElement);
  }
});

it("computes deterministic values for every sort key", () => {
  const row = { ...pages[0], render_mode: null, raw_word_count: null, rendered_word_count: null, forms_total: 3, agent_usable_forms: 2 } as PageRow;
  expect(sortValue(row, "url")).toBe(row.url);
  expect(sortValue({ ...row, status_code: null }, "status_code")).toBe(-1);
  expect(sortValue(row, "render_mode")).toBe("");
  expect(sortValue({ ...row, word_count: null }, "word_count")).toBe(-1);
  expect(sortValue(row, "js_delta")).toBe(-1);
  expect(sortValue({ ...row, images_missing_alt: null }, "images_missing_alt")).toBe(-1);
  expect(sortValue({ ...row, svg_missing_name: null }, "svg_missing_name")).toBe(-1);
  expect(sortValue(row, "agent_usable_forms")).toBe(1);
  expect(sortValue({ ...row, agent_usable_forms: null }, "agent_usable_forms")).toBe(3);
  expect(sortValue({ ...row, forms_total: null }, "agent_usable_forms")).toBe(-1);
});

it("formats HTTP colors and render badges", () => {
  expect(statusColor(null)).toContain("faint");
  expect(statusColor(200)).toContain("ok");
  expect(statusColor(404)).toContain("error");
  expect(statusColor(302)).toContain("warn");
  expect(statusColor(700)).toContain("faint");
  expect(renderBadge(null)).toBeNull();
  expect(renderBadge("csr")).toBeTruthy();
  expect(renderBadge("ssr")).toBeTruthy();
  expect(renderBadge("custom")).toBeTruthy();
});

it("flips crawl sort direction deterministically", () => {
  expect(nextSortDirection("asc")).toBe("desc");
  expect(nextSortDirection("desc")).toBe("asc");
});

it("serializes nullable page metrics for CSV", () => {
  const row = csvRow({ ...pages[0], status_code: null, render_mode: null, word_count: null, raw_word_count: null, rendered_word_count: null, images_missing_alt: null, images_total: null, svg_missing_name: null, svg_total: null, forms_total: null, agent_usable_forms: null } as PageRow);
  expect(row).toHaveLength(11);
  expect(row.slice(1).every((value) => value === "")).toBe(true);
});

it("serializes populated page metrics for CSV", () => {
  const row = csvRow({ ...pages[0], svg_missing_name: 1, svg_total: 2 } as PageRow);
  expect(row.slice(1)).toEqual(["200", "ssr", "100", "10", "1", "2", "1", "2", "1", "1"]);
});

it("keeps the crawler section empty when the pages endpoint fails", async () => {
  vi.spyOn(api, "getAuditPages").mockRejectedValue(new Error("offline"));
  render(<CrawledPages auditId="a1" />);
  await waitFor(() => expect(screen.queryByText("Pages crawlées")).not.toBeInTheDocument());
});
