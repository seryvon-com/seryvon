// Seryvon — home: launch an audit. AGPL-3.0-or-later.

import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { TopBar } from "../components/TopBar";

export function HomePage() {
  const [url, setUrl] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!url.trim() || running) return;
    setRunning(true);
    setError(null);
    try {
      const report = await api.createAudit(url.trim());
      // The POST persists; reload by navigating to the report route. The audit id
      // is not in the body, so we re-fetch the latest for the domain.
      const history = await api.listAudits(report.domain);
      const latest = history[0];
      if (latest) navigate(`/audits/${latest.audit_id}`);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? `Échec de l'audit (${err.status}) : ${err.message}`
          : "Échec de l'audit — le backend est-il démarré ?",
      );
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="app">
      <TopBar />
      <form className="audit-form" onSubmit={onSubmit}>
        <input
          type="text"
          placeholder="https://exemple.com"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          aria-label="URL à auditer"
        />
        <button className="btn" type="submit" disabled={running}>
          {running ? "Audit en cours…" : "Auditer"}
        </button>
      </form>
      {error && <div className="notice error">{error}</div>}
      {!error && (
        <div className="notice">
          Saisis une URL pour lancer un audit déterministe sur les cinq piliers. Le résultat est
          traçable et reproductible (variance &lt; 2 %).
        </div>
      )}
    </div>
  );
}
