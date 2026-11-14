/** API shapes (mirror backend/app/models). The Flag contract lives in ./flag.ts. */

import type { Category, Flag } from "@/types/flag";

export type Role = "admin" | "creator" | "manager";

export interface Me {
  id: string;
  email: string | null;
  display_name: string | null;
  role: Role;
  brand_id: string;
  brand_name: string;
}

export type RuleStatus = "pending" | "approved" | "rejected";

export interface Rule {
  rule_code: string;
  category: Category;
  text: string;
  source_doc: string | null;
  source_page: number | null;
  check_type: "deterministic" | "semantic";
  det_kind: "banned_terms" | "required_phrase" | null;
  terms: string[];
  examples_bad: string[];
  examples_good: string[];
  always_on: boolean;
  status: RuleStatus;
  updated_at: string;
}

export interface PairIssue {
  rule_a: string;
  rule_b: string;
  similarity: number;
  explanation: string;
}

export interface VagueIssue {
  rule_code: string;
  reason: string;
  suggested_rewrite: string | null;
}

export interface VerificationReport {
  duplicates: PairIssue[];
  contradictions: PairIssue[];
  vague: VagueIssue[];
  missing_categories: string[];
  pairs_checked: number;
  rules_checked: number;
}

export interface GuidelineUploadResult {
  source_doc: string;
  pages: number;
  rules: Rule[];
  report: VerificationReport;
}

export type FactStatus = "pending" | "approved" | "rejected";
export type Expiry = "valid" | "expiring" | "expired" | "no_expiry";

export interface Fact {
  fact_code: string;
  entity: string;
  attribute: string;
  value: string;
  unit: string | null;
  statement: string;
  source: string | null;
  valid_until: string | null;
  status: FactStatus;
  expiry: Expiry;
  updated_at: string;
}

export type FactInput = Omit<
  Fact,
  "fact_code" | "status" | "expiry" | "updated_at"
>;

export type ContentStatus =
  | "draft"
  | "checking"
  | "creator_review"
  | "manager_review"
  | "changes_requested"
  | "approved";
export type FlagStatus =
  "open" | "accepted" | "edited" | "dismissed" | "excepted";

export interface FlagCounts {
  open: number;
  open_high: number;
  resolved: number;
}

export interface ContentSummary {
  id: string;
  title: string;
  format: string;
  status: ContentStatus;
  creator_id: string;
  creator_name: string | null;
  created_at: string;
  updated_at: string;
  latest_version_id: string | null;
  latest_version_number: number | null;
  counts: FlagCounts;
}

export interface VersionInfo {
  id: string;
  version_number: number;
  created_at: string;
  review_started_at: string | null;
  review_finished_at: string | null;
  review_error: string | null;
  counts: FlagCounts;
}

export interface ContentDetail extends ContentSummary {
  versions: VersionInfo[];
  text: string | null;
  review_error: string | null;
}

export interface ReviewUnit {
  unit_id: string;
  position: number;
  text: string;
  location: Record<string, unknown>;
}

export interface StoredFlag extends Flag {
  id: string;
  status: FlagStatus;
  resolution_note: string | null;
  resolved_at: string | null;
  source_text: string | null;
}

export interface VersionFlags {
  version_id: string;
  content_id: string;
  version_number: number;
  text: string;
  units: ReviewUnit[];
  flags: StoredFlag[];
  ai_usage: AIUsage[];
}

export interface Comment {
  id: string;
  version_id: string;
  author_id: string;
  author_name: string | null;
  author_role: string | null;
  body: string;
  flag_id: string | null;
  created_at: string;
}

export interface AIUsage {
  purpose: string;
  provider: string;
  model: string;
  calls: number;
  cached: number;
}

export interface BrandSettings {
  confidential_terms: string[];
  claim_policy_enabled: boolean;
  readability_target: number | null;
  claim_policy_id: string;
  claim_policy_text: string;
  presidio_available: boolean;
}

export interface Disclosure {
  services: {
    name: string;
    role: string;
    models: string[];
    data_sent: string;
    configured: boolean;
  }[];
  provider_order: string[];
  redaction: string[];
  presidio_active: boolean;
  usage_last_30_days: {
    provider: string;
    model: string;
    purpose: string;
    calls: number;
    cached: number;
    failed: number;
  }[];
}
