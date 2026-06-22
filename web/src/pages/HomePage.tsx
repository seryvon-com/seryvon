// Seryvon — home: launch an audit inside the AppShell dashboard. AGPL-3.0-or-later.

import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { AppShell } from "../components/AppShell";
import { useI18n } from "../i18n";

export function HomePage() {
  const { t, locale } = useI18n();
  const [url, setUrl] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const navigate = useNavigate();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollStartRef = useRef<number>(0);
  const POLL_TIMEOUT_MS = 5 * 60 * 1000;

  function stopPolling(errMsg?: string) {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setTaskId(null);
    setRunning(false);
    if (errMsg) setError(errMsg);
  }

  useEffect(() => {
    if (!taskId) return;
    pollStartRef.current = Date.now();
    intervalRef.current = setInterval(() => {
      if (Date.now() - pollStartRef.current > POLL_TIMEOUT_MS) {
        stopPolling(t.home.errorBackend);
        return;
      }
      api
        .getAuditTask(taskId)
        .then((status) => {
          if (status.status === "done" && status.audit_id) {
            if (intervalRef.current) clearInterval(intervalRef.current);
            intervalRef.current = null;
            setTaskId(null);
            navigate(`/audits/${status.audit_id}`);
          } else if (status.status === "failed") {
            stopPolling(status.error ?? t.home.errorBackend);
          }
        })
        .catch(() => stopPolling(t.home.errorBackend));
    }, 2000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
        err instanceof ApiError
          ? t.home.errorStatus(err.status, err.message)
          : t.home.errorBackend,
      );
      setRunning(false);
    }
  }

  return (
    <AppShell
      active="home"
      title={t.home.newAudit}
      subtitle={t.topbar.overviewSubtitle}
    >
      <div className="card home-audit-card">
        <form className="home-audit-form" onSubmit={onSubmit}>
          <input
            type="text"
            className="home-audit-input"
            placeholder={t.home.placeholder}
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            aria-label="URL"
            autoFocus
          />
          <button className="btn home-audit-btn" type="submit" disabled={running}>
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
          <div className="notice error" style={{ marginTop: 16 }}>
            {error}
          </div>
        )}
      </div>
    </AppShell>
  );
}
