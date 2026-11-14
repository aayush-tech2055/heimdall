/**
 * The flag contract (frozen on day one).
 * Must stay identical to backend/app/models/flag.py.
 */

export const SOURCE_TYPES = ["rule", "fact", "policy"] as const;
export const CATEGORIES = [
  "tone",
  "terminology",
  "messaging",
  "claims",
  "visuals",
  "accessibility",
  "legal",
  "other",
] as const;
export const SEVERITIES = ["low", "medium", "high"] as const;
export const LAYERS = ["rules", "guidelines", "claims", "visuals"] as const;

export type SourceType = (typeof SOURCE_TYPES)[number];
export type Category = (typeof CATEGORIES)[number];
export type Severity = (typeof SEVERITIES)[number];
export type Layer = (typeof LAYERS)[number];

/** A box as [x0, y0, x1, y1] in page or image coordinates. */
export type BBox = [number, number, number, number];

/** Text content: paragraph number and character spans within the full text. */
export interface TextLocation {
  paragraph: number;
  char_start: number;
  char_end: number;
  evidence_start: number;
  evidence_end: number;
}

/** PDF content: 1-based page number and a bounding box on that page. */
export interface PdfLocation {
  page: number;
  bbox: BBox;
}

/** Video content: start and end in seconds. */
export interface VideoLocation {
  start: number;
  end: number;
}

/** Image content: which image, and an optional region on it. */
export interface ImageLocation {
  image_id: string;
  region?: BBox | null;
}

export type FlagLocation =
  TextLocation | PdfLocation | VideoLocation | ImageLocation;

/** One issue found in one review unit, citing exactly one source. */
export interface Flag {
  unit_id: string;
  source_type: SourceType;
  /** Rule code (R-012), fact code or SYS-… policy id. */
  source_id: string;
  category: Category;
  severity: Severity;
  /** Exact quote from the content; "" for a missing required phrase. */
  evidence: string;
  explanation: string;
  suggested_fix: string | null;
  /** 0.0 to 1.0 */
  confidence: number;
  location: FlagLocation;
  layer: Layer;
}

export const isTextLocation = (l: FlagLocation): l is TextLocation =>
  "paragraph" in l;
export const isPdfLocation = (l: FlagLocation): l is PdfLocation => "page" in l;
export const isVideoLocation = (l: FlagLocation): l is VideoLocation =>
  "start" in l;
export const isImageLocation = (l: FlagLocation): l is ImageLocation =>
  "image_id" in l;
