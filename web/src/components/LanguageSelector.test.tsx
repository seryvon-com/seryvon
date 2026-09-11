import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { expect, it, vi } from "vitest";

import { LanguageSelector } from "./LanguageSelector";
import { I18nProvider, useI18n } from "../i18n";

function I18nProbe() {
  const { locale, formatDate } = useI18n();
  return <output>{locale}|{formatDate(null)}|{formatDate("2026-01-02T15:04:00Z")}</output>;
}

it("switches the locale and persists the selection", () => {
  localStorage.clear();
  render(
    <I18nProvider>
      <LanguageSelector />
    </I18nProvider>,
  );
  const select = screen.getByRole("combobox");
  expect(select).toHaveValue("en");
  fireEvent.change(select, { target: { value: "fr" } });
  expect(select).toHaveValue("fr");
  expect(localStorage.getItem("seryvon.locale")).toBe("fr");
});

it("restores French and formats dates in the active locale", () => {
  localStorage.setItem("seryvon.locale", "fr");
  render(
    <I18nProvider>
      <I18nProbe />
    </I18nProvider>,
  );
  expect(screen.getByRole("status")).toHaveTextContent(/^fr\|—\|/);
});

it("falls back to English for an unsupported stored locale", () => {
  localStorage.setItem("seryvon.locale", "de");
  render(<I18nProvider><I18nProbe /></I18nProvider>);
  expect(screen.getByRole("status")).toHaveTextContent(/^en\|—\|/);
});

it("keeps the selected locale when localStorage cannot be written", () => {
  const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("private mode"); });
  render(<I18nProvider><LanguageSelector /></I18nProvider>);
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "fr" } });
  expect(screen.getByRole("combobox")).toHaveValue("fr");
  expect(setItem).toHaveBeenCalled();
  setItem.mockRestore();
});
