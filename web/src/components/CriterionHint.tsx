// Seryvon — per-criterion info tooltips. AGPL-3.0-or-later.

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useI18n } from "../i18n";

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

/** Hover tooltip — for visual/compact hints (e.g. platform grid). */
function InfoButton({
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
          top: rect.bottom + 8,
          left: Math.max(8, Math.min(window.innerWidth - minWidth - 8, rect.left + rect.width / 2 - minWidth / 2)),
          minWidth,
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
  const [pos, setPos] = useState<{ top: number; left: number; width: number } | null>(null);

  function toggle() {
    if (!open && btnRef.current) {
      const r = btnRef.current.getBoundingClientRect();
      const panelWidth = Math.min(420, window.innerWidth - 24);
      const left = Math.max(8, Math.min(window.innerWidth - panelWidth - 8, r.left + r.width / 2 - panelWidth / 2));
      setPos({ top: r.bottom + 8, left, width: panelWidth });
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
        style={{ top: pos.top, left: pos.left, width: pos.width }}
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
        <div className="hint-panel-body">{body}</div>
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
      return <HintPanel title={h.geoSsrTitle} body={h.geoSsrBody} />;
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
