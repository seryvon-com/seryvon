import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

import { ApiError, api } from "../api/client";
import { I18nProvider, useI18n } from "../i18n";
import { canDeleteKey, canSaveKey, ConnectorCard, KeysPage } from "./KeysPage";
import { en } from "../i18n/en";

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

it("evaluates key action guards for empty and pending states", () => {
  expect(canSaveKey("", false)).toBe(false);
  expect(canSaveKey("secret", false)).toBe(true);
  expect(canSaveKey("secret", true)).toBe(false);
  expect(canDeleteKey(false)).toBe(true);
  expect(canDeleteKey(true)).toBe(false);
});

it("shows the keys loading state while the API is pending", () => {
  vi.spyOn(api, "listKeys").mockReturnValue(new Promise(() => {}));
  render(<MemoryRouter><I18nProvider><KeysPage /></I18nProvider></MemoryRouter>);
  expect(screen.getByText(/Loading/)).toBeInTheDocument();
});

it("renders connector groups after loading", async () => {
  vi.spyOn(api, "listKeys").mockResolvedValue([]);
  render(<MemoryRouter><I18nProvider><KeysPage /></I18nProvider></MemoryRouter>);
  await waitFor(() => expect(screen.getByText(/Performance/)).toBeInTheDocument());
  expect(screen.getByText(/Authority/)).toBeInTheDocument();
});

it("falls back to the raw connector group key when untranslated", async () => {
  vi.spyOn(api, "listKeys").mockResolvedValue([]);
  const groups = en.keys.connectorGroups as Record<string, string>;
  const original = groups.performance;
  delete groups.performance;
  try {
    render(<MemoryRouter><I18nProvider><KeysPage /></I18nProvider></MemoryRouter>);
    expect(await screen.findByText("performance")).toBeInTheDocument();
  } finally {
    groups.performance = original;
  }
});

it("shows the encryption notice on a 503 response", async () => {
  vi.spyOn(api, "listKeys").mockRejectedValue(new ApiError(503, "Unavailable"));
  render(<MemoryRouter><I18nProvider><KeysPage /></I18nProvider></MemoryRouter>);
  await waitFor(() => expect(screen.getByText(/encryption/i)).toBeInTheDocument());
});

it("shows a generic load error for unexpected key service failures", async () => {
  vi.spyOn(api, "listKeys").mockRejectedValue(new ApiError(500, "Key service unavailable"));
  render(<MemoryRouter><I18nProvider><KeysPage /></I18nProvider></MemoryRouter>);
  expect(await screen.findByText("Key service unavailable")).toBeInTheDocument();
  expect(screen.queryByText(/encryption/i)).not.toBeInTheDocument();
});

it("shows the translated load error for a non-API failure", async () => {
  vi.spyOn(api, "listKeys").mockRejectedValue(new Error("offline"));
  render(<MemoryRouter><I18nProvider><KeysPage /></I18nProvider></MemoryRouter>);
  expect(await screen.findByText(/Failed to load|Échec du chargement/)).toBeInTheDocument();
});

it("saves and deletes a stored connector key", async () => {
  const list = vi.spyOn(api, "listKeys").mockResolvedValue([{ connector: "openai", masked_value: "sk-***", source: "db", created_at: null, updated_at: null }]);
  const save = vi.spyOn(api, "upsertKey").mockResolvedValue({ connector: "openai", masked_value: "sk-***", source: "db", created_at: null, updated_at: null });
  const remove = vi.spyOn(api, "deleteKey").mockResolvedValue(undefined);
  render(<MemoryRouter><I18nProvider><KeysPage /></I18nProvider></MemoryRouter>);
  await waitFor(() => expect(screen.getByText("sk-***")).toBeInTheDocument());
  const card = screen.getByText("OPENAI").closest(".key-card") as HTMLElement;
  const input = card.querySelector("input") as HTMLInputElement;
  fireEvent.change(input, { target: { value: "secret" } });
  fireEvent.keyDown(input, { key: "Enter" });
  fireEvent.click(card.querySelector("button.btn") as HTMLElement);
  await waitFor(() => expect(save).toHaveBeenCalledWith("openai", "secret"));
  fireEvent.click(screen.getByRole("button", { name: /delete/i }));
  fireEvent.click(screen.getByRole("button", { name: /delete/i }));
  await waitFor(() => expect(remove).toHaveBeenCalledWith("openai"));
  expect(list).toHaveBeenCalledTimes(4);
});

it("shows save and delete errors for a stored key", async () => {
  vi.spyOn(api, "listKeys").mockResolvedValue([{ connector: "openai", masked_value: "sk-***", source: "db", created_at: null, updated_at: null }]);
  vi.spyOn(api, "upsertKey").mockRejectedValue(new ApiError(500, "Save failed"));
  vi.spyOn(api, "deleteKey").mockRejectedValue(new Error("Delete failed"));
  render(<MemoryRouter><I18nProvider><KeysPage /></I18nProvider></MemoryRouter>);
  await waitFor(() => expect(screen.getByText("sk-***")).toBeInTheDocument());
  const card = screen.getByText("OPENAI").closest(".key-card") as HTMLElement;
  fireEvent.change(card.querySelector("input") as HTMLInputElement, { target: { value: "secret" } });
  fireEvent.click(card.querySelector("button.btn") as HTMLElement);
  expect(await screen.findByText("Save failed")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /delete/i }));
  expect(await screen.findByText(/failed to delete|delete/i)).toBeInTheDocument();
});

it("ignores an empty save and handles a non-API save failure", async () => {
  vi.spyOn(api, "listKeys").mockResolvedValue([{ connector: "openai", masked_value: "sk-***", source: "db", created_at: null, updated_at: null }]);
  const save = vi.spyOn(api, "upsertKey").mockRejectedValue(new Error("offline"));
  render(<MemoryRouter><I18nProvider><KeysPage /></I18nProvider></MemoryRouter>);
  await waitFor(() => expect(screen.getByText("sk-***")).toBeInTheDocument());
  const card = screen.getByText("OPENAI").closest(".key-card") as HTMLElement;
  const input = card.querySelector("input") as HTMLInputElement;
  fireEvent.click(card.querySelector("button.btn") as HTMLElement);
  expect(save).not.toHaveBeenCalled();
  fireEvent.change(input, { target: { value: "secret" } });
  fireEvent.click(card.querySelector("button.btn") as HTMLElement);
  await waitFor(() => expect(save).toHaveBeenCalled());
  expect(await screen.findByText("Failed to save key.")).toBeInTheDocument();
});

it("renders environment-backed keys and connector help links", async () => {
  vi.spyOn(api, "listKeys").mockResolvedValue([{ connector: "openai", masked_value: "sk-env", source: "env", created_at: null, updated_at: null }]);
  render(<MemoryRouter><I18nProvider><KeysPage /></I18nProvider></MemoryRouter>);
  await waitFor(() => expect(screen.getByText("sk-env")).toBeInTheDocument());
  const card = screen.getByText("OPENAI").closest(".key-card") as HTMLElement;
  expect(card.querySelector(".key-source-env")).toBeInTheDocument();
  expect(card.querySelector(".key-help-link")).toBeInTheDocument();
});

it("renders an unknown connector card without help metadata", async () => {
  function DirectCard() {
    const { t } = useI18n();
    return <ConnectorCard connector="custom" entry={{ connector: "custom", masked_value: "***", source: "db", created_at: null, updated_at: null }} noEncryption={false} t={t} onSaved={vi.fn()} onDeleted={vi.fn()} />;
  }
  render(<MemoryRouter><I18nProvider><DirectCard /></I18nProvider></MemoryRouter>);
  expect(screen.getByText("CUSTOM")).toBeInTheDocument();
  expect(screen.getByText("CUSTOM").closest(".key-card")?.querySelector(".key-help-link")).toBeNull();
});

it("edits a JSON connector value", () => {
  function DirectJsonCard() {
    const { t } = useI18n();
    return <ConnectorCard connector="gsc" entry={null} noEncryption={false} isJson t={t} onSaved={vi.fn()} onDeleted={vi.fn()} />;
  }
  render(<MemoryRouter><I18nProvider><DirectJsonCard /></I18nProvider></MemoryRouter>);
  fireEvent.change(screen.getByRole("textbox"), { target: { value: '{"client":"ok"}' } });
  expect(screen.getByRole("textbox")).toHaveValue('{"client":"ok"}');
});

it("renders the deprecation notice for OpenPageRank", () => {
  function DirectCard() {
    const { t } = useI18n();
    return <ConnectorCard connector="opr" entry={null} noEncryption={false} t={t} onSaved={vi.fn()} onDeleted={vi.fn()} />;
  }
  render(<MemoryRouter><I18nProvider><DirectCard /></I18nProvider></MemoryRouter>);
  expect(screen.getByText(/OpenPageRank was acquired/i)).toBeInTheDocument();
  expect(screen.getByText("OPR").closest(".key-card")?.querySelector(".key-help-link")).toBeNull();
});

it("ignores duplicate save and delete actions while pending", async () => {
  let resolveSave: ((value: unknown) => void) | undefined;
  let resolveDelete: ((value?: unknown) => void) | undefined;
  const save = vi.spyOn(api, "upsertKey").mockReturnValue(new Promise((resolve) => { resolveSave = resolve; }) as never);
  const remove = vi.spyOn(api, "deleteKey").mockReturnValue(new Promise((resolve) => { resolveDelete = resolve; }) as never);
  function DirectCard() {
    const { t } = useI18n();
    return <ConnectorCard connector="custom" entry={{ connector: "custom", masked_value: "***", source: "db", created_at: null, updated_at: null }} noEncryption={false} t={t} onSaved={vi.fn()} onDeleted={vi.fn()} />;
  }
  render(<MemoryRouter><I18nProvider><DirectCard /></I18nProvider></MemoryRouter>);
  const card = screen.getByText("CUSTOM").closest(".key-card") as HTMLElement;
  const saveButton = card.querySelector("button.btn") as HTMLButtonElement;
  fireEvent.click(saveButton);
  expect(save).not.toHaveBeenCalled();
  fireEvent.change(card.querySelector("input") as HTMLInputElement, { target: { value: "secret" } });
  fireEvent.click(card.querySelector("button.btn") as HTMLElement);
  fireEvent.click(card.querySelector("button.btn") as HTMLElement);
  expect(save).toHaveBeenCalledTimes(1);
  resolveSave?.({});
  const deleteButton = screen.getByRole("button", { name: /delete/i }) as HTMLButtonElement;
  fireEvent.click(deleteButton);
  fireEvent.click(deleteButton);
  expect(remove).toHaveBeenCalledTimes(1);
  resolveDelete?.();
});
