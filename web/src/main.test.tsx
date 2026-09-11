import "@testing-library/jest-dom/vitest";
import { beforeEach, expect, it, vi } from "vitest";

const render = vi.fn();
vi.mock("react-dom/client", () => ({ createRoot: vi.fn(() => ({ render })) }));
vi.mock("react-router-dom", () => ({
  createBrowserRouter: vi.fn(() => ({})),
  RouterProvider: () => null,
}));
vi.mock("./i18n", () => ({ I18nProvider: ({ children }: { children: unknown }) => children }));
beforeEach(() => {
  document.body.innerHTML = '<div id="root"></div>';
  render.mockClear();
});

it("mounts the application into the root element", async () => {
  await import("./main");
  expect(render).toHaveBeenCalledTimes(1);
  expect(document.getElementById("root")).toBeInTheDocument();
});

it("fails fast when the root element is missing", async () => {
  document.body.innerHTML = "";
  vi.resetModules();
  await expect(import("./main")).rejects.toThrow("#root introuvable");
});
