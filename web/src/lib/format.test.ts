import { describe, expect, it } from "vitest";

import {
  durationParts,
  isPillar,
  pillarColor,
  readinessReached,
  scoreBucket,
  scoreColor,
  statusSeverity,
} from "./format";

describe("report formatting helpers", () => {
  it("maps score boundaries to the correct bucket", () => {
    expect(scoreBucket(49.9)).toBe("critical");
    expect(scoreBucket(50)).toBe("warning");
    expect(scoreBucket(80)).toBe("ok");
    expect(pillarColor("seo")).toBe("var(--c-pillar-seo)");
    expect(pillarColor("unknown")).toBe("var(--accent)");
    expect(scoreColor(80)).toBe("var(--c-ok)");
    expect(statusSeverity("critical")).toBe("critical");
    expect(statusSeverity("warning")).toBe("warning");
  });

  it("splits durations and handles missing or invalid timestamps", () => {
    expect(durationParts("2026-01-01T00:00:00Z", null)).toEqual({ kind: "none" });
    expect(durationParts("2026-01-01T00:00:00Z", "2026-01-01T00:00:12Z")).toEqual({ kind: "s", s: 12 });
    expect(durationParts("2026-01-01T00:00:00Z", "2026-01-01T00:02:05Z")).toEqual({ kind: "m", m: 2, s: 5 });
    expect(durationParts("invalid", "2026-01-01T00:00:00Z")).toEqual({ kind: "none" });
  });

  it("validates pillars and readiness levels", () => {
    expect(isPillar("seo")).toBe(true);
    expect(isPillar("unknown")).toBe(false);
    expect(readinessReached("none")).toBe(0);
    expect(readinessReached("basic")).toBe(2);
    expect(readinessReached("advanced")).toBe(4);
  });
});
