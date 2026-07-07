// Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
// Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
// Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
//
// TypeScript mirror of the FastAPI/Pydantic response models (src/seryvon/models/
// report.py). Kept hand-written and minimal until an OpenAPI codegen step lands.

export interface CostLine {
  connector: string;
  active: boolean;
  calls: number;
  unit_usd: number;
  total_usd: number;
  note: string;
}

export interface AuditCostEstimate {
  currency: string;
  total_usd: number;
  indicative: boolean;
  lines: CostLine[];
}

export type Pillar = "seo" | "geo" | "gso" | "aeo" | "aso";

export const PILLARS: Pillar[] = ["seo", "geo", "gso", "aeo", "aso"];

export const PILLAR_LABELS: Record<Pillar, string> = {
  seo: "SEO",
  geo: "GEO",
  gso: "GSO",
  aeo: "AEO",
  aso: "ASO",
};

export type Status =
  | "ok"
  | "warning"
  | "critical"
  | "not_measured"
  | "not_applicable";

export type CoverageLabel =
  | "complete"
  | "substantial"
  | "partial"
  | "insufficient";

export type Severity = "warning" | "critical";

export type ReadinessLevel = "none" | "basic" | "ready" | "advanced";

export interface PillarScore {
  pillar: string;
  score: number;
  measured: number;
  excluded: number;
  not_applicable: number;
  coverage: number;
  coverage_label: CoverageLabel;
}

export interface CriterionResult {
  key: string;
  pillars: string[];
  raw_value: unknown;
  score: number;
  status: Status;
  threshold: Record<string, unknown>;
  explanation: string;
  evidence: Record<string, unknown>;
  weight: number;
  evidence_tier: string;
}

export interface Issue {
  criterion_key: string;
  severity: Severity;
  impact: number;
  effort: number;
  priority_score: number;
  priority_bucket: string; // high / medium / low (legacy audits may still carry P1–P4)
  recommendation: string;
  explanation: string;
  raw_value: unknown;
  affected_pages: string[];
}

export interface AsoReadiness {
  readiness_level: ReadinessLevel;
  agent_ready: boolean;
  has_webmcp: boolean;
  has_action_schema: boolean;
  has_agent_forms: boolean;
  has_openapi: boolean;
  action_signals: number;
  ai_discovery_endpoints: number;
  has_nlweb: boolean;
  brand_coherence_score: number | null;
  blocked_agent_bots: string[];
}

export interface MeasurementProfile {
  seryvon_version: string;
  signal_schema_version: number;
  rule_catalog_digest: string;
  pillar_weights: Record<string, number>;
  thresholds: Record<string, Record<string, unknown>>;
  criteria_overrides: Record<string, Record<string, unknown>>;
  active_connectors: string[];
  digest: string;
}

export interface ArtifactRef {
  project_id: string;
  run_id: string;
  type: string;
  bucket: string;
  object_key: string;
  sha256: string;
  mime_type: string;
  size_bytes: number;
  compression: string;
  encryption: boolean;
  retention_until: string | null;
  created_at: string | null;
}

export interface AuditReport {
  domain: string;
  tool_version: string;
  schema_version: number;
  started_at: string;
  finished_at: string | null;
  score_global: number;
  coverage: number;
  pillars: Record<string, PillarScore>;
  criteria: CriterionResult[];
  issues: Issue[];
  aso_readiness: AsoReadiness | null;
  config_digest: string | null;
  measurement_profile: MeasurementProfile | null;
  artifacts: ArtifactRef[];
}

export type PromptIntent =
  | "definitional"
  | "comparative"
  | "recommendation"
  | "explanatory"
  | "listing"
  | "use_case"
  | "news";

export interface Prompt {
  text: string;
  intent: PromptIntent;
  source: string;
  quality_score: number;
}

export interface ThemeProfile {
  domain: string;
  topics: string[];
  entities: string[];
  content_type: string;
  brand: string | null;
}

export interface PromptSet {
  version: number;
  domain: string;
  generated_by: string;
  theme_profile: ThemeProfile;
  prompts: Prompt[];
  tracked_competitors: string[];
}

export interface GscQuery {
  query: string;
  position: number;
  clicks: number;
  impressions: number;
  ctr: number;
}

export interface GscPage {
  page: string;
  position: number;
  clicks: number;
  impressions: number;
  ctr: number;
}

export interface GscComparison {
  previous_clicks: number;
  previous_impressions: number;
  previous_ctr: number;
  previous_avg_position: number | null;
  clicks_delta: number;
  impressions_delta: number;
  ctr_delta: number;
  position_delta: number | null;
  period_days: number;
}

export interface GscResult {
  queries: GscQuery[];
  pages: GscPage[];
  total_clicks: number;
  total_impressions: number;
  avg_ctr: number;
  avg_position: number | null;
  date_range_days: number;
  comparison: GscComparison | null;
}

export interface PageRow {
  url: string;
  status_code: number | null;
  render_mode: string | null;
  word_count: number | null;
  images_total: number | null;
  images_missing_alt: number | null;
  svg_total: number | null;
  svg_missing_name: number | null;
  agent_usable_forms: number | null;
  forms_total: number | null;
  title: string | null;
  raw_word_count: number | null;
  rendered_word_count: number | null;
}

export interface AuditSummary {
  audit_id: string;
  domain: string;
  score_global: number | null;
  started_at: string;
  criteria_measured: number;
}

export interface DomainSummary {
  domain: string;
  audit_count: number;
  latest_audit_id: string;
  latest_score: number | null;
  latest_started_at: string;
}

export interface AuditTask {
  task_id: string;
  status_url: string;
}

export type JobStatus = "pending" | "running" | "done" | "failed";

export interface AuditTaskStatus {
  status: JobStatus;
  audit_id: string | null;
  error: string | null;
  logs: string[];
}

export interface EngineCitationMetrics {
  citation_rate: number;
  mention_rate: number;
  citation_confidence: number;
  average_position: number | null;
}

export interface CitationMetrics {
  citation_rate: number;
  mention_rate: number;
  citation_confidence: number;
  share_of_voice: number | null;
  knowledge_presence: number | null;
  average_position: number | null;
  per_engine: Record<string, EngineCitationMetrics>;
  engines: string[];
  prompt_count: number;
  repetitions: number;
  prompt_set_version: number | null;
}

export interface CitationTaskStatus {
  status: JobStatus;
  metrics: CitationMetrics | null;
  error: string | null;
}

export type KeySource = "db" | "env" | "none";

export interface KeyEntry {
  connector: string;
  masked_value: string | null;
  source: KeySource;
  created_at: string | null;
  updated_at: string | null;
}

export type Comparability = "exact" | "compatible" | "intersection" | "incompatible";
export type ComparisonMode = "strict" | "intersection" | "descriptive";

export interface PillarDelta {
  pillar: string;
  left_score: number | null;
  right_score: number | null;
  delta: number | null;
}

export interface CriterionDelta {
  key: string;
  left_score: number | null;
  right_score: number | null;
  delta: number | null;
  left_status: Status | null;
  right_status: Status | null;
}

export interface ComparisonResult {
  comparability: Comparability;
  requested_mode: ComparisonMode;
  allowed_modes: ComparisonMode[];
  profile_differences: string[];
  recomputed: boolean;
  common_criteria: string[];
  global_delta: number | null;
  left_global: number | null;
  right_global: number | null;
  pillars: PillarDelta[];
  criteria: CriterionDelta[];
}
