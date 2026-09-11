import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api } from "./client";

afterEach(() => vi.unstubAllGlobals());

function response(body: unknown, status = 200): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    statusText: status === 200 ? "OK" : "Bad Request",
    headers: { "Content-Type": "application/json" },
  });
}

describe("typed API client", () => {
  it("calls health and encodes audit domains", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({ status: "ok", version: "1" }))
      .mockResolvedValueOnce(response([]));
    vi.stubGlobal("fetch", fetchMock);
    await expect(api.health()).resolves.toEqual({ status: "ok", version: "1" });
    await expect(api.listAudits("a b.example")).resolves.toEqual([]);
    expect(fetchMock.mock.calls[1][0]).toBe("/api/audits?domain=a%20b.example");
  });

  it("sends typed POST and DELETE requests", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({ task_id: "t1" }))
      .mockResolvedValueOnce(response({}, 204));
    vi.stubGlobal("fetch", fetchMock);
    await api.createAudit("https://example.com", "en");
    await api.deleteKey("gsc");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "POST" });
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ method: "DELETE" });
  });

  it("raises ApiError with server detail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ detail: "Denied" }, 403)));
    await expect(api.health()).rejects.toEqual(new ApiError(403, "Denied"));
  });

  it("keeps status text when an error body is not JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("bad gateway", { status: 502, statusText: "Bad Gateway" }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(api.health()).rejects.toEqual(new ApiError(502, "Bad Gateway"));
  });

  it("covers the remaining report and configuration endpoints", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() => response({})));
    await api.getAuditCostEstimate();
    await api.getAuditTask("task");
    await api.getAudit("audit");
    await api.listDomains();
    await api.compareAudits("left", "right");
    await api.runCitations("example.com");
    await api.getCitationTask("citation");
    await api.getPromptSet("audit");
    await api.getAuditPages("audit");
    await api.getRankTracking("audit", 30);
    await api.listKeys();
    await api.upsertKey("gsc", "value");
    expect(vi.mocked(fetch).mock.calls).toHaveLength(12);
  });
});
