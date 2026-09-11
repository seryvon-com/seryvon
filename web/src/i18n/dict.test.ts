import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { describe, expect, it, vi } from "vitest";
import React from "react";
import { en } from "./en";
import { fr } from "./fr";
import { I18nProvider, useI18n } from "./index";

describe("localized dynamic labels", () => {
  it("keeps every dynamic label callable in both locales", () => {
    const visit = (value: unknown) => {
      if (typeof value === "function") {
        const source = String(value);
        const args = Array.from({ length: value.length }, (_, index) =>
          /toFixed|padStart|[<>]/.test(source) ? (index === 0 ? 0 : 2) : "example",
        );
        expect(value(...args)).toBeDefined();
        return;
      }
      if (value && typeof value === "object") Object.values(value).forEach(visit);
    };
    visit(en);
    visit(fr);
  });

  it("formats dynamic summaries and readiness explanations", () => {
    expect(en.home.tagline("SEO, GEO")).toContain("SEO, GEO");
    expect(fr.home.tagline("SEO, GEO")).toContain("SEO, GEO");
    expect(fr.report.summary(4, 6, 2)).toContain("4 critères");
    expect(fr.asoDetail.agentReadyExplainer(2)).toContain("2 sur 2");
    expect(en.home.costCalls(1, 0.01)).toContain("call");
    expect(en.home.costCalls(2, 0.01)).toContain("calls");
    expect(en.home.recentAuditCount(1)).toContain("audit");
    expect(en.home.recentAuditCount(2)).toContain("audits");
    expect(en.issue.bucket("unknown")).toBe("unknown");
    expect(fr.home.costCalls(2, 0.01)).toContain("appels");
    expect(fr.home.recentAuditCount(2)).toContain("audits");
  });

  it("persists locale, formats both date states and tolerates storage failure", () => {
    function Probe() {
      const { locale, setLocale, formatDate } = useI18n();
      return React.createElement(React.Fragment, null,
        React.createElement("span", null, locale),
        React.createElement("button", { onClick: () => setLocale("fr") }, "FR"),
        React.createElement("span", null, formatDate(null)),
        React.createElement("span", null, formatDate("2026-09-09T10:00:00Z")),
      );
    }
    localStorage.setItem("seryvon.locale", "fr");
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("private"); });
    render(React.createElement(I18nProvider, null, React.createElement(Probe)));
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.getByText(/fr/)).toBeInTheDocument();
    expect(screen.getAllByText(/2026/).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "FR" }));
    expect(screen.getByText("fr")).toBeInTheDocument();
    expect(setItem).toHaveBeenCalled();
    setItem.mockRestore();
  });

  it("falls back safely when localStorage is unavailable", () => {
    const descriptor = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
    Object.defineProperty(globalThis, "localStorage", { value: undefined, configurable: true });
    function Probe() {
      const { locale, setLocale } = useI18n();
      return React.createElement("button", { onClick: () => setLocale("fr") }, locale);
    }
    render(React.createElement(I18nProvider, null, React.createElement(Probe)));
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("fr")).toBeInTheDocument();
    if (descriptor) Object.defineProperty(globalThis, "localStorage", descriptor);
  });

  it("rejects use outside the provider", () => {
    function Outside() { useI18n(); return null; }
    expect(() => render(React.createElement(Outside))).toThrow("useI18n must be used within an I18nProvider");
  });
});
