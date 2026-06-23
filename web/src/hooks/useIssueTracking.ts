// Seryvon — issue tracking hook (localStorage, per audit). AGPL-3.0-or-later.

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
  doneAt?: string; // YYYY-MM-DD, auto-set on first toggle
  proofs: ProofItem[];
}

export type TrackingStore = Record<string, IssueTracking>;

export const MAX_FILE_BYTES = 2 * 1024 * 1024;

function storageKey(auditId: string) {
  return `seryvon:tracking:${auditId}`;
}

function loadStore(auditId: string): TrackingStore {
  try {
    const raw = localStorage.getItem(storageKey(auditId));
    return raw ? (JSON.parse(raw) as TrackingStore) : {};
  } catch {
    return {};
  }
}

function saveStore(auditId: string, store: TrackingStore) {
  try {
    localStorage.setItem(storageKey(auditId), JSON.stringify(store));
  } catch {
    // localStorage quota exceeded — silent fail
  }
}

export function useIssueTracking(auditId: string | undefined) {
  const [store, setStore] = useState<TrackingStore>(() =>
    auditId ? loadStore(auditId) : {}
  );

  const getTracking = useCallback(
    (key: string): IssueTracking => store[key] ?? { done: false, proofs: [] },
    [store]
  );

  const toggleDone = useCallback(
    (key: string) => {
      if (!auditId) return;
      setStore((prev) => {
        const cur = prev[key] ?? { done: false, proofs: [] };
        const next: TrackingStore = {
          ...prev,
          [key]: {
            ...cur,
            done: !cur.done,
            doneAt: !cur.done
              ? new Date().toISOString().slice(0, 10)
              : cur.doneAt,
          },
        };
        saveStore(auditId, next);
        return next;
      });
    },
    [auditId]
  );

  const setDoneAt = useCallback(
    (key: string, date: string) => {
      if (!auditId) return;
      setStore((prev) => {
        const cur = prev[key] ?? { done: false, proofs: [] };
        const next: TrackingStore = { ...prev, [key]: { ...cur, doneAt: date } };
        saveStore(auditId, next);
        return next;
      });
    },
    [auditId]
  );

  const addProof = useCallback(
    (key: string, proof: ProofItem) => {
      if (!auditId) return;
      setStore((prev) => {
        const cur = prev[key] ?? { done: false, proofs: [] };
        const next: TrackingStore = {
          ...prev,
          [key]: { ...cur, proofs: [...cur.proofs, proof] },
        };
        saveStore(auditId, next);
        return next;
      });
    },
    [auditId]
  );

  const removeProof = useCallback(
    (key: string, proofId: string) => {
      if (!auditId) return;
      setStore((prev) => {
        const cur = prev[key] ?? { done: false, proofs: [] };
        const next: TrackingStore = {
          ...prev,
          [key]: { ...cur, proofs: cur.proofs.filter((p) => p.id !== proofId) },
        };
        saveStore(auditId, next);
        return next;
      });
    },
    [auditId]
  );

  return { getTracking, toggleDone, setDoneAt, addProof, removeProof };
}
