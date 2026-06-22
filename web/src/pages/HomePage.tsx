// Seryvon — home: launch an audit (PRISM). AGPL-3.0-or-later.

import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { LanguageSelector } from "../components/LanguageSelector";
import { useI18n } from "../i18n";

export function HomePage() {
  const { t, locale } = useI18n();
  const [url, setUrl] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const navigate = useNavigate();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Poll the audit task until done or failed.
  useEffect(() => {
    if (!taskId) return;
    intervalRef.current = setInterval(() => {
      api
        .getAuditTask(taskId)
        .then((status) => {
          if (status.status === "done" && status.audit_id) {
            clearInterval(intervalRef.current!);
            intervalRef.current = null;
            setTaskId(null);
            navigate(`/audits/${status.audit_id}`);
          } else if (status.status === "failed") {
            clearInterval(intervalRef.current!);
            intervalRef.current = null;
            setTaskId(null);
            setRunning(false);
            setError(status.error ?? t.home.errorBackend);
          }
        })
        .catch(() => {
          clearInterval(intervalRef.current!);
          intervalRef.current = null;
          setTaskId(null);
          setRunning(false);
          setError(t.home.errorBackend);
        });
    }, 2000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [taskId, navigate, t.home.errorBackend]);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!url.trim() || running) return;
    setRunning(true);
    setError(null);
    try {
      let normalizedUrl = url.trim();
      if (!normalizedUrl.match(/^https?:\/\//)) {
        normalizedUrl = `https://${normalizedUrl}`;
      }
      const task = await api.createAudit(normalizedUrl, locale);
      setTaskId(task.task_id);
    } catch (err) {
      setError(
        err instanceof ApiError ? t.home.errorStatus(err.status, err.message) : t.home.errorBackend,
      );
      setRunning(false);
    }
  }

  return (
    <div className="content">
      <div className="landing-lang">
        <LanguageSelector />
      </div>
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
        {running && (
          <div className="audit-progress" role="status" aria-live="polite">
            <div className="bar">
              <span className="fill" />
            </div>
            <div className="caption">{t.home.progress}</div>
          </div>
        )}
        {error && (
          <div className="notice error" style={{ marginTop: 20, textAlign: "left" }}>
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
