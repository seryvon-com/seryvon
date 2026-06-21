// Seryvon — home: launch an audit (PRISM). AGPL-3.0-or-later.

import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, ApiError } from "../api/client";

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
      // POST persists but does not return the audit id; re-fetch the latest run
      // for the domain to navigate to its report.
      const history = await api.listAudits(report.domain);
      const latest = history[0];
      if (latest) navigate(`/audits/${latest.audit_id}`);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? `Échec de l'audit (${err.status}) : ${err.message}`
          : "Échec de l'audit — le backend FastAPI est-il démarré ?",
      );
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="content">
      <div className="landing">
        <span className="prism-mark mark" />
        <h2>seryvon</h2>
        <p>
          Audit web déterministe sur cinq piliers — <b>SEO · GEO · GSO · AEO · ASO</b>. Chaque score
          est traçable jusqu'à sa donnée source et reproductible (variance &lt; 2 %).
        </p>
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
        {error && (
          <div className="notice error" style={{ marginTop: 20, textAlign: "left" }}>
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
