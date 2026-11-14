/** API shapes (mirror backend/app/models). The Flag contract lives in ./flag.ts. */

import type { Category } from "@/types/flag";

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
