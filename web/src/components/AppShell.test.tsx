import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter } from "react-router-dom";
import { expect, it } from "vitest";

import { I18nProvider } from "../i18n";
import { AppShell } from "./AppShell";

it("navigates from analysis and configuration navigation actions", () => {
  render(<MemoryRouter initialEntries={["/audits/a1"]}><I18nProvider><AppShell active="home" auditId="a1" title="Test"><div>content</div></AppShell></I18nProvider></MemoryRouter>);
  fireEvent.click(screen.getByRole("button", { name: /audit report/i }));
  fireEvent.click(screen.getByRole("button", { name: /prompt set/i }));
});

it("offers a run-audit action away from the home page", () => {
  render(<MemoryRouter initialEntries={["/audits/a1/report"]}><I18nProvider><AppShell active="report" title="Test"><div>content</div></AppShell></I18nProvider></MemoryRouter>);
  expect(screen.getByRole("button", { name: /analysis/i })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /analysis/i }));
});
