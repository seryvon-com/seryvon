// Seryvon — issue tracking hook (localStorage, per domain). AGPL-3.0-or-later.

import { useCallback, useState } from "react";

export interface ProofItem {
  id: string;
  type: "image" | "pdf" | "url";
  dataUrl?: string; // base64 data URL for files
  url?: string; // for type="url"
  name?: string; // filename or raw URL
}

export interface IssueTracking {
  done: boolean;
  doneAt?: string;        // YYYY-MM-DD
  doneInAuditId?: string; // audit in which this was marked done
  proofs: ProofItem[];
}

export type TrackingStore = Record<string, IssueTracking>;

export const MAX_FILE_BYTES = 2 * 1024 * 1024;

function storageKey(domain: string) {
  return `seryvon:tracking:domain:${domain}`;
}

function loadStore(domain: string): TrackingStore {
  try {
    const raw = localStorage.getItem(storageKey(domain));
    return raw ? (JSON.parse(raw) as TrackingStore) : {};
  } catch {
    return {};
  }
}

function saveStore(domain: string, store: TrackingStore) {
  try {
    localStorage.setItem(storageKey(domain), JSON.stringify(store));
  } catch {
    // localStorage quota exceeded — silent fail
  }
}

export function useIssueTracking(domain: string | undefined) {
  const [store, setStore] = useState<TrackingStore>(() =>
    domain ? loadStore(domain) : {}
  );

  const getTracking = useCallback(
    (key: string): IssueTracking => store[key] ?? { done: false, proofs: [] },
    [store]
  );

  const toggleDone = useCallback(
    (key: string, auditId: string) => {
      if (!domain) return;
      setStore((prev) => {
        const cur = prev[key] ?? { done: false, proofs: [] };
        const becomingDone = !cur.done;
        const next: TrackingStore = {
          ...prev,
          [key]: {
            ...cur,
            done: becomingDone,
            doneAt: becomingDone
              ? new Date().toISOString().slice(0, 10)
              : cur.doneAt,
            doneInAuditId: becomingDone ? auditId : cur.doneInAuditId,
          },
        };
        saveStore(domain, next);
        return next;
      });
    },
    [domain]
  );

  const setDoneAt = useCallback(
    (key: string, date: string) => {
      if (!domain) return;
      setStore((prev) => {
        const cur = prev[key] ?? { done: false, proofs: [] };
        const next: TrackingStore = { ...prev, [key]: { ...cur, doneAt: date } };
        saveStore(domain, next);
        return next;
      });
    },
    [domain]
  );

  const addProof = useCallback(
    (key: string, proof: ProofItem) => {
      if (!domain) return;
      setStore((prev) => {
        const cur = prev[key] ?? { done: false, proofs: [] };
        const next: TrackingStore = {
          ...prev,
          [key]: { ...cur, proofs: [...cur.proofs, proof] },
        };
        saveStore(domain, next);
        return next;
      });
    },
    [domain]
  );

  const removeProof = useCallback(
    (key: string, proofId: string) => {
      if (!domain) return;
      setStore((prev) => {
        const cur = prev[key] ?? { done: false, proofs: [] };
        const next: TrackingStore = {
          ...prev,
          [key]: { ...cur, proofs: cur.proofs.filter((p) => p.id !== proofId) },
        };
        saveStore(domain, next);
        return next;
      });
    },
    [domain]
  );

  return { getTracking, toggleDone, setDoneAt, addProof, removeProof };
}
