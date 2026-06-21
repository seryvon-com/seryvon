// Seryvon — home: launch an audit (PRISM). AGPL-3.0-or-later.

import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { useI18n } from "../i18n";

export function HomePage() {
  const { t } = useI18n();
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
        err instanceof ApiError ? t.home.errorStatus(err.status, err.message) : t.home.errorBackend,
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
        <p>{t.home.tagline("SEO · GEO · GSO · AEO · ASO")}</p>
        <form className="audit-form" onSubmit={onSubmit}>
          <input
            type="text"
            placeholder={t.home.placeholder}
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            aria-label="URL"
          />
          <button className="btn" type="submit" disabled={running}>
            {running ? t.home.auditing : t.home.audit}
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
