// Seryvon — per-criterion info tooltips. AGPL-3.0-or-later.

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useI18n } from "../i18n";

//: Vertical placement for a floating panel anchored to a trigger element.
//: Flips above the trigger when there isn't enough room below, and always caps
//: `maxHeight` so long content scrolls instead of being clipped by the viewport
//: with no way to reach the rest (see CriterionHint / HintPanel usage).
function placeVertically(rect: DOMRect, gap = 8, minRoom = 160): { top?: number; bottom?: number; maxHeight: number } {
  const roomBelow = window.innerHeight - rect.bottom - gap;
  if (roomBelow >= minRoom || roomBelow >= rect.top - gap) {
    return { top: rect.bottom + gap, maxHeight: Math.max(120, roomBelow - gap) };
  }
  return { bottom: window.innerHeight - rect.top + gap, maxHeight: Math.max(120, rect.top - gap * 2) };
}

// Mirrors _PLATFORM_HOSTS in src/seryvon/crawler/extract.py
const RECOGNIZED_PLATFORMS: { key: string; label: string }[] = [
  { key: "twitter",    label: "Twitter / X" },
  { key: "linkedin",   label: "LinkedIn" },
  { key: "facebook",   label: "Facebook" },
  { key: "instagram",  label: "Instagram" },
  { key: "youtube",    label: "YouTube" },
  { key: "github",     label: "GitHub" },
  { key: "tiktok",     label: "TikTok" },
  { key: "pinterest",  label: "Pinterest" },
  { key: "mastodon",   label: "Mastodon" },
  { key: "reddit",     label: "Reddit" },
  { key: "bluesky",    label: "Bluesky" },
  { key: "threads",    label: "Threads" },
  { key: "crunchbase", label: "Crunchbase" },
];

/** Hover tooltip — for visual/compact hints (e.g. platform grid). Exported for reuse in table headers etc. */
export function InfoButton({
  label,
  children,
  minWidth = 260,
}: {
  label: string;
  children: React.ReactNode;
  minWidth?: number;
}) {
  const btnRef = useRef<HTMLButtonElement>(null);
  const [rect, setRect] = useState<DOMRect | null>(null);

  function handleOpen() {
    if (btnRef.current) setRect(btnRef.current.getBoundingClientRect());
  }
  function handleClose() {
    setRect(null);
  }

  const tooltip =
    rect &&
    createPortal(
      <div
        className="cost-tooltip"
        role="tooltip"
        style={{
          position: "fixed",
          ...placeVertically(rect),
          left: Math.max(8, Math.min(window.innerWidth - minWidth - 8, rect.left + rect.width / 2 - minWidth / 2)),
          minWidth,
          overflowY: "auto",
          zIndex: 9999,
        }}
      >
        {children}
      </div>,
      document.body,
    );

  return (
    <span className="cost-info-wrap" style={{ position: "static" }}>
      <button
        ref={btnRef}
        className="cost-info-btn"
        aria-label={label}
        onMouseEnter={handleOpen}
        onMouseLeave={handleClose}
        onFocus={handleOpen}
        onBlur={handleClose}
        type="button"
      >
        ⓘ
      </button>
      {tooltip}
    </span>
  );
}

/** Click-toggle panel — for textual hints that must be selectable/copyable. */
function HintPanel({ title, body }: { title: string; body: string }) {
  const btnRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top?: number; bottom?: number; left: number; width: number; maxHeight: number } | null>(null);

  function toggle() {
    if (!open && btnRef.current) {
      const r = btnRef.current.getBoundingClientRect();
      const panelWidth = Math.min(420, window.innerWidth - 24);
      const left = Math.max(8, Math.min(window.innerWidth - panelWidth - 8, r.left + r.width / 2 - panelWidth / 2));
      setPos({ ...placeVertically(r), left, width: panelWidth });
    }
    setOpen((o) => !o);
  }

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: PointerEvent) {
      if (
        panelRef.current && !panelRef.current.contains(e.target as Node) &&
        btnRef.current && !btnRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  // Close on scroll
  useEffect(() => {
    if (!open) return;
    function onScroll() { setOpen(false); }
    window.addEventListener("scroll", onScroll, { passive: true, capture: true });
    return () => window.removeEventListener("scroll", onScroll, { capture: true });
  }, [open]);

  const panel =
    open && pos &&
    createPortal(
      <div
        ref={panelRef}
        className="hint-panel"
        role="dialog"
        aria-label={title}
        style={{
          top: pos.top,
          bottom: pos.bottom,
          left: pos.left,
          width: pos.width,
          maxHeight: pos.maxHeight,
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div className="hint-panel-header">
          <span className="hint-panel-title">{title}</span>
          <button
            className="hint-panel-close"
            onClick={() => setOpen(false)}
            aria-label="Fermer"
            type="button"
          >
            ×
          </button>
        </div>
        <div className="hint-panel-body" style={{ overflowY: "auto" }}>{body}</div>
      </div>,
      document.body,
    );

  return (
    <span className="cost-info-wrap" style={{ position: "static" }}>
      <button
        ref={btnRef}
        className={`cost-info-btn${open ? " active" : ""}`}
        aria-label={title}
        aria-expanded={open}
        onClick={toggle}
        type="button"
      >
        ⓘ
      </button>
      {panel}
    </span>
  );
}

function CrossPlatformHint({ rawValue }: { rawValue: unknown }) {
  const { t } = useI18n();
  const h = t.criterionHints;
  const detected: string[] =
    rawValue !== null &&
    typeof rawValue === "object" &&
    "platforms" in (rawValue as object) &&
    Array.isArray((rawValue as { platforms: unknown }).platforms)
      ? ((rawValue as { platforms: string[] }).platforms)
      : [];

  return (
    <InfoButton label={h.crossPlatformTitle} minWidth={280}>
      <div className="cost-tooltip-title">{h.crossPlatformTitle}</div>
      <div style={{ fontSize: "0.74rem", color: "var(--c-text-muted)", marginBottom: 8, lineHeight: 1.4 }}>
        {h.crossPlatformDetection}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 6px" }}>
        {RECOGNIZED_PLATFORMS.map(({ key, label }) => {
          const found = detected.includes(key);
          return (
            <span
              key={key}
              title={found ? h.crossPlatformDetectedLabel : h.crossPlatformMissingLabel}
              style={{
                fontSize: "0.72rem",
                borderRadius: 4,
                padding: "1px 6px",
                background: found ? "var(--c-accent-dim, #1f3a5f)" : "var(--c-border, #30363d)",
                color: found ? "var(--c-accent, #4f9cf9)" : "var(--c-text-muted, #8b949e)",
                fontWeight: found ? 600 : 400,
              }}
            >
              {found ? "✓ " : ""}{label}
            </span>
          );
        })}
      </div>
    </InfoButton>
  );
}

interface SsrRouteRow {
  path: string;
  pages: number;
  ssr: number;
  csr: number;
}

interface SsrOffenderRow {
  url: string;
  raw_words: number;
  rendered_words: number;
  delta: number;
  parity_pct: number;
}

interface SsrWordDelta {
  raw_words: number;
  rendered_words: number;
  delta: number;
  parity_pct: number;
}

/** Severity tier from a page's content-parity percentage — pure display grouping,
 * the geo.ssr score itself already uses continuous parity (not tiered). Splits
 * the flat "worst offenders" list into scannable buckets so a reader can jump to
 * "critical" pages (near-empty raw HTML) without wading through partial cases.
 */
export type SsrTier = "thin" | "partial" | "near";

export function ssrTier(parityPct: number): SsrTier {
  if (parityPct < 30) return "thin";
  if (parityPct < 70) return "partial";
  return "near";
}

export const SSR_TIER_COLOR: Record<SsrTier, string> = {
  thin: "var(--c-error, #e5484d)",
  partial: "var(--c-warn, #e8a94d)",
  near: "var(--c-ok, #3ecf8e)",
};

function SsrBreakdownHint({ rawValue }: { rawValue: unknown }) {
  const { t } = useI18n();
  const h = t.criterionHints;
  const v = rawValue !== null && typeof rawValue === "object" ? (rawValue as Record<string, unknown>) : {};
  const byRoute = Array.isArray(v.by_route) ? (v.by_route as SsrRouteRow[]) : [];
  const offenders = Array.isArray(v.top_offenders) ? (v.top_offenders as SsrOffenderRow[]) : [];
  const wordDeltas =
    v.word_deltas !== null && typeof v.word_deltas === "object"
      ? (v.word_deltas as Record<string, SsrWordDelta>)
      : {};
  const tierCounts = { thin: 0, partial: 0, near: 0 };
  for (const d of Object.values(wordDeltas)) tierCounts[ssrTier(d.parity_pct)]++;

  if (byRoute.length === 0 && offenders.length === 0) {
    return <HintPanel title={h.geoSsrTitle} body={h.geoSsrBody} />;
  }

  return (
    <InfoButton label={h.geoSsrTitle} minWidth={340}>
      <div className="cost-tooltip-title">{h.geoSsrTitle}</div>
      <div style={{ fontSize: "0.74rem", color: "var(--c-text-muted)", marginBottom: 8, lineHeight: 1.4, whiteSpace: "normal" }}>
        {h.geoSsrBody}
      </div>

      {byRoute.length > 0 && (
        <>
          <div style={{ fontSize: "0.7rem", fontWeight: 600, color: "var(--c-text-muted)", margin: "8px 0 4px" }}>
            {h.geoSsrByRouteTitle}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 2, marginBottom: 8 }}>
            {byRoute.slice(0, 8).map((r) => (
              <div key={r.path} style={{ display: "flex", justifyContent: "space-between", fontSize: "0.72rem" }}>
                <span style={{ color: "var(--c-text-primary, inherit)" }}>{r.path}</span>
                <span style={{ fontFamily: "var(--font-mono)" }}>
                  <span style={{ color: r.csr > 0 ? "var(--c-warn, #e8a94d)" : "var(--c-ok)" }}>{r.csr} JS</span>
                  {" / "}
                  <span style={{ color: "var(--c-text-faint)" }}>{r.ssr} OK</span>
                </span>
              </div>
            ))}
          </div>
        </>
      )}

      {offenders.length > 0 && (
        <>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", margin: "8px 0 4px" }}>
            <span style={{ fontSize: "0.7rem", fontWeight: 600, color: "var(--c-text-muted)" }}>
              {h.geoSsrTopOffendersTitle}
            </span>
            <span style={{ display: "flex", gap: 6, fontSize: "0.66rem", fontFamily: "var(--font-mono)" }}>
              <span style={{ color: SSR_TIER_COLOR.thin }}>{tierCounts.thin} {h.geoSsrTierThin}</span>
              <span style={{ color: SSR_TIER_COLOR.partial }}>{tierCounts.partial} {h.geoSsrTierPartial}</span>
              <span style={{ color: SSR_TIER_COLOR.near }}>{tierCounts.near} {h.geoSsrTierNear}</span>
            </span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {offenders.slice(0, 5).map((o) => (
              <div key={o.url} style={{ fontSize: "0.7rem", display: "flex", gap: 6 }}>
                <span
                  aria-hidden="true"
                  style={{
                    flexShrink: 0,
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: SSR_TIER_COLOR[ssrTier(o.parity_pct)],
                    marginTop: 5,
                  }}
                />
                <div style={{ minWidth: 0 }}>
                  <div style={{ color: "var(--c-text-primary, inherit)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={o.url}>
                    {o.url}
                  </div>
                  <div style={{ color: "var(--c-text-faint)", fontFamily: "var(--font-mono)" }}>
                    {o.parity_pct}% {h.geoSsrParityLabel} · +{o.delta} {h.geoSsrWordsLabel} ({o.raw_words} → {o.rendered_words})
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </InfoButton>
  );
}

export function CriterionHint({
  criterionKey,
  rawValue,
}: {
  criterionKey: string;
  rawValue: unknown;
}) {
  const { t } = useI18n();
  const h = t.criterionHints;

  switch (criterionKey) {
    // Visual / compound hints
    case "geo.cross_platform":
      return <CrossPlatformHint rawValue={rawValue} />;

    // AEO
    case "aeo.comparison_tables":
      return <HintPanel title={h.comparisonTablesTitle} body={h.comparisonTablesBody} />;
    case "aeo.kg_presence":
      return <HintPanel title={h.kgPresenceTitle} body={h.kgPresenceBody} />;
    case "aeo.author_credentials":
      return <HintPanel title={h.aeoAuthorCredentialsTitle} body={h.aeoAuthorCredentialsBody} />;
    case "aeo.about_page":
      return <HintPanel title={h.aeoAboutPageTitle} body={h.aeoAboutPageBody} />;
    case "aeo.defined_terms":
      return <HintPanel title={h.aeoDefinedTermsTitle} body={h.aeoDefinedTermsBody} />;
    case "aeo.dates_structured":
      return <HintPanel title={h.aeoDatesStructuredTitle} body={h.aeoDatesStructuredBody} />;
    case "aeo.answer_directness":
      return <HintPanel title={h.aeoAnswerDirectnessTitle} body={h.aeoAnswerDirectnessBody} />;
    case "aeo.llm_citation":
      return <HintPanel title={h.aeoLlmCitationTitle} body={h.aeoLlmCitationBody} />;

    // GEO
    case "geo.primary_sources":
      return <HintPanel title={h.primarySourcesTitle} body={h.primarySourcesBody} />;
    case "geo.ssr":
      return <SsrBreakdownHint rawValue={rawValue} />;
    case "geo.noise_ratio":
      return <HintPanel title={h.geoNoiseRatioTitle} body={h.geoNoiseRatioBody} />;
    case "geo.entity_density":
      return <HintPanel title={h.geoEntityDensityTitle} body={h.geoEntityDensityBody} />;
    case "geo.authors":
      return <HintPanel title={h.geoAuthorsTitle} body={h.geoAuthorsBody} />;
    case "geo.freshness":
      return <HintPanel title={h.geoFreshnessTitle} body={h.geoFreshnessBody} />;
    case "geo.citation_rate":
      return <HintPanel title={h.geoCitationRateTitle} body={h.geoCitationRateBody} />;
    case "geo.mention_rate":
      return <HintPanel title={h.geoMentionRateTitle} body={h.geoMentionRateBody} />;
    case "geo.citation_confidence":
      return <HintPanel title={h.geoCitationConfidenceTitle} body={h.geoCitationConfidenceBody} />;
    case "geo.knowledge_presence":
      return <HintPanel title={h.geoKnowledgePresenceTitle} body={h.geoKnowledgePresenceBody} />;
    case "geo.share_of_voice":
      return <HintPanel title={h.geoShareOfVoiceTitle} body={h.geoShareOfVoiceBody} />;
    case "geo.citation_position":
      return <HintPanel title={h.geoCitationPositionTitle} body={h.geoCitationPositionBody} />;

    // ASO (non-experimental)
    case "aso.mcp_readiness":
      return <HintPanel title={h.mcpReadinessTitle} body={h.mcpReadinessBody} />;
    case "aso.accessible_forms":
      return <HintPanel title={h.asoAccessibleFormsTitle} body={h.asoAccessibleFormsBody} />;
    case "aso.brand_coherence":
      return <HintPanel title={h.asoBrandCoherenceTitle} body={h.asoBrandCoherenceBody} />;
    case "aso.agent_access":
      return <HintPanel title={h.asoAgentAccessTitle} body={h.asoAgentAccessBody} />;
    case "aso.agent_ready":
      return <HintPanel title={h.asoAgentReadyTitle} body={h.asoAgentReadyBody} />;
    case "aso.action_schema":
      return <HintPanel title={h.asoActionSchemaTitle} body={h.asoActionSchemaBody} />;
    case "aso.ai_discovery":
      return <HintPanel title={h.asoAiDiscoveryTitle} body={h.asoAiDiscoveryBody} />;
    case "aso.nlweb":
      return <HintPanel title={h.asoNlwebTitle} body={h.asoNlwebBody} />;

    // GSO
    case "gso.faqpage":
      return <HintPanel title={h.gsoFaqpageTitle} body={h.gsoFaqpageBody} />;
    case "gso.howto":
      return <HintPanel title={h.gsoHowtoTitle} body={h.gsoHowtoBody} />;
    case "gso.breadcrumb":
      return <HintPanel title={h.gsoBreadcrumbTitle} body={h.gsoBreadcrumbBody} />;
    case "gso.itemlist":
      return <HintPanel title={h.gsoItemlistTitle} body={h.gsoItemlistBody} />;
    case "gso.qa_format":
      return <HintPanel title={h.gsoQaFormatTitle} body={h.gsoQaFormatBody} />;
    case "gso.cwv_eligible":
      return <HintPanel title={h.gsoCwvEligibleTitle} body={h.gsoCwvEligibleBody} />;

    // SEO – meta
    case "meta.title":
      return <HintPanel title={h.metaTitleTitle} body={h.metaTitleBody} />;
    case "meta.description":
      return <HintPanel title={h.metaDescriptionTitle} body={h.metaDescriptionBody} />;
    case "meta.canonical":
      return <HintPanel title={h.metaCanonicalTitle} body={h.metaCanonicalBody} />;
    case "meta.robots":
      return <HintPanel title={h.metaRobotsTitle} body={h.metaRobotsBody} />;
    case "meta.title_unique":
      return <HintPanel title={h.metaTitleUniqueTitle} body={h.metaTitleUniqueBody} />;
    case "og.complete":
      return <HintPanel title={h.ogCompleteTitle} body={h.ogCompleteBody} />;
    case "twitter.cards":
      return <HintPanel title={h.twitterCardsTitle} body={h.twitterCardsBody} />;

    // SEO – structure / content
    case "struct.h1":
      return <HintPanel title={h.structH1Title} body={h.structH1Body} />;
    case "struct.hierarchy":
      return <HintPanel title={h.structHierarchyTitle} body={h.structHierarchyBody} />;
    case "struct.schema":
      return <HintPanel title={h.structSchemaTitle} body={h.structSchemaBody} />;
    case "content.depth":
      return <HintPanel title={h.contentDepthTitle} body={h.contentDepthBody} />;
    case "content.text_ratio":
      return <HintPanel title={h.contentTextRatioTitle} body={h.contentTextRatioBody} />;

    // SEO – links / media / crawl / i18n
    case "links.internal":
      return <HintPanel title={h.linksInternalTitle} body={h.linksInternalBody} />;
    case "links.orphans":
      return <HintPanel title={h.linksOrphansTitle} body={h.linksOrphansBody} />;
    case "img.alt":
      return <HintPanel title={h.imgAltTitle} body={h.imgAltBody} />;
    case "crawl.indexable":
      return <HintPanel title={h.crawlIndexableTitle} body={h.crawlIndexableBody} />;
    case "crawl.sitemap":
      return <HintPanel title={h.crawlSitemapTitle} body={h.crawlSitemapBody} />;
    case "crawl.https":
      return <HintPanel title={h.crawlHttpsTitle} body={h.crawlHttpsBody} />;
    case "crawl.redirects":
      return <HintPanel title={h.crawlRedirectsTitle} body={h.crawlRedirectsBody} />;
    case "i18n.hreflang":
      return <HintPanel title={h.i18nHreflangTitle} body={h.i18nHreflangBody} />;

    // Performance
    case "perf.lcp":
      return <HintPanel title={h.perfLcpTitle} body={h.perfLcpBody} />;
    case "perf.cls":
      return <HintPanel title={h.perfClsTitle} body={h.perfClsBody} />;
    case "perf.inp":
      return <HintPanel title={h.perfInpTitle} body={h.perfInpBody} />;
    case "perf.lighthouse":
      return <HintPanel title={h.perfLighthouseTitle} body={h.perfLighthouseBody} />;

    // Authority
    case "authority.opr":
      return <HintPanel title={h.authorityOprTitle} body={h.authorityOprBody} />;
    case "authority.backlinks":
      return <HintPanel title={h.authorityBacklinksTitle} body={h.authorityBacklinksBody} />;

    // SEO GSC
    case "seo.avg_position":
      return <HintPanel title={h.seoAvgPositionTitle} body={h.seoAvgPositionBody} />;
    case "seo.click_through_rate":
      return <HintPanel title={h.seoCtrTitle} body={h.seoCtrBody} />;

    default:
      return null;
  }
}
