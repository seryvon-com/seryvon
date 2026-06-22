// Seryvon — BYOK key management page (PRISM). AGPL-3.0-or-later.

import { useEffect, useState } from "react";

import { api, ApiError } from "../api/client";
import type { KeyEntry } from "../api/types";
import { AppShell } from "../components/AppShell";
import { useI18n } from "../i18n";

const CONNECTORS = ["psi", "opr", "perplexity", "openai", "anthropic", "gemini"] as const;

const HELP_URLS: Record<string, string> = {
  psi: "https://console.cloud.google.com/apis/credentials",
  opr: "https://www.domcop.com/openpagerank/documentation",
  perplexity: "https://www.perplexity.ai/settings/api",
  openai: "https://platform.openai.com/api-keys",
  anthropic: "https://console.anthropic.com/settings/keys",
  gemini: "https://aistudio.google.com/app/apikey",
};

export function KeysPage() {
  const { t } = useI18n();
  const [keys, setKeys] = useState<KeyEntry[] | null>(null);
  const [noEncryption, setNoEncryption] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  function reload() {
    api
      .listKeys()
      .then((k) => {
        setKeys(k);
        setLoadError(null);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 503) {
          setNoEncryption(true);
          setKeys([]);
        } else {
          setLoadError(err instanceof ApiError ? err.message : t.report.loadError);
          setKeys([]);
        }
      });
  }

  useEffect(() => {
    reload();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const keyMap = new Map<string, KeyEntry>(keys?.map((k) => [k.connector, k]) ?? []);

  return (
    <AppShell active="keys" title={t.keys.title} subtitle={t.keys.subtitle}>
      {loadError && <div className="notice error">{loadError}</div>}
      {noEncryption && <div className="notice">{t.keys.noEncryption}</div>}
      {!loadError && keys === null && <div className="notice">{t.report.loading}</div>}
      {keys !== null && (
        <div className="keys-grid">
          {CONNECTORS.map((connector) => (
            <ConnectorCard
              key={connector}
              connector={connector}
              entry={keyMap.get(connector) ?? null}
              noEncryption={noEncryption}
              t={t}
              onSaved={reload}
              onDeleted={reload}
            />
          ))}
        </div>
      )}
    </AppShell>
  );
}

function ConnectorCard({
  connector,
  entry,
  noEncryption,
  t,
  onSaved,
  onDeleted,
}: {
  connector: string;
  entry: KeyEntry | null;
  noEncryption: boolean;
  t: ReturnType<typeof useI18n>["t"];
  onSaved: () => void;
  onDeleted: () => void;
}) {
  const [inputValue, setInputValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);
  const [flashType, setFlashType] = useState<"ok" | "error">("ok");

  function showFlash(msg: string, type: "ok" | "error") {
    setFlash(msg);
    setFlashType(type);
    setTimeout(() => setFlash(null), 3000);
  }

  function handleSave() {
    if (!inputValue.trim() || saving) return;
    setSaving(true);
    api
      .upsertKey(connector, inputValue.trim())
      .then(() => {
        setInputValue("");
        setSaving(false);
        showFlash(t.keys.saved, "ok");
        onSaved();
      })
      .catch(() => {
        setSaving(false);
        showFlash(t.keys.errorSave, "error");
      });
  }

  function handleDelete() {
    if (deleting) return;
    setDeleting(true);
    api
      .deleteKey(connector)
      .then(() => {
        setDeleting(false);
        showFlash(t.keys.deleted, "ok");
        onDeleted();
      })
      .catch(() => {
        setDeleting(false);
        showFlash(t.keys.errorDelete, "error");
      });
  }

  const source = entry?.source ?? "none";
  const sourceLabel = t.keys.source[source as "db" | "env" | "none"];
  const sourceCls =
    source === "db" ? "key-source-db" : source === "env" ? "key-source-env" : "key-source-none";
  const helpUrl = HELP_URLS[connector];

  return (
    <div className="card key-card">
      <div className="key-card-head">
        <div>
          <div className="key-connector">{connector.toUpperCase()}</div>
          <div className="key-desc">{t.keys.connectorDesc[connector] ?? ""}</div>
          {helpUrl && (
            <a
              className="key-help-link"
              href={helpUrl}
              target="_blank"
              rel="noopener noreferrer"
            >
              {t.keys.getKey}
            </a>
          )}
        </div>
        <span className={`key-source-badge ${sourceCls}`}>{sourceLabel}</span>
      </div>

      {entry?.masked_value && (
        <div className="key-masked">{entry.masked_value}</div>
      )}

      {!noEncryption && (
        <div className="key-input-row">
          <input
            className="compare-input"
            type="password"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSave()}
            placeholder={t.keys.placeholder}
            autoComplete="off"
          />
          <button
            className="btn"
            onClick={handleSave}
            disabled={saving || !inputValue.trim()}
            style={{ flexShrink: 0 }}
          >
            {saving ? t.keys.saving : t.keys.save}
          </button>
          {source === "db" && (
            <button
              className="btn btn-ghost"
              onClick={handleDelete}
              disabled={deleting}
              style={{ flexShrink: 0 }}
            >
              {t.keys.delete}
            </button>
          )}
        </div>
      )}

      {flash && (
        <div className={`key-flash ${flashType === "error" ? "error" : ""}`}>{flash}</div>
      )}
    </div>
  );
}
