-- Heimdall database schema (task 2.1).
--
-- Runs on a fresh Supabase project (Postgres 15+, `vector` extension available):
--     psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/schema.sql
-- Then apply the row-level security policies in db/policies.sql.
--
-- Conventions
-- * Every table carries `brand_id`. Child tables reference their parent with a composite
--   foreign key (id, brand_id), so a row can never point at a parent from another brand.
-- * Enumerations are `text` + CHECK constraints (easier to extend than Postgres enums).
--   The allowed values mirror TASKS.md Part 1 and backend/app/models/flag.py.
-- * Row-level security is enabled on every table here, so nothing is readable through the
--   Supabase API until db/policies.sql grants it. The FastAPI backend connects with the
--   database owner role and is not subject to RLS.

begin;

create extension if not exists vector with schema extensions;

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------

create function public.set_updated_at() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- Brands, people, settings
-- ---------------------------------------------------------------------------

create table public.brands (
  id          uuid primary key default gen_random_uuid(),
  name        text not null check (btrim(name) <> ''),
  slug        text not null unique check (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  created_at  timestamptz not null default now()
);

-- One row per signed-in user: their role and the brand they work on.
create table public.profiles (
  id            uuid primary key references auth.users (id) on delete cascade,
  brand_id      uuid not null references public.brands (id) on delete cascade,
  role          text not null check (role in ('admin', 'creator', 'manager')),
  display_name  text,
  created_at    timestamptz not null default now(),
  unique (id, brand_id)
);
create index profiles_brand_idx on public.profiles (brand_id, role);

create table public.brand_settings (
  brand_id              uuid primary key references public.brands (id) on delete cascade,
  confidential_terms    text[] not null default '{}',   -- redacted before any AI call (decision 16)
  claim_policy_enabled  boolean not null default true,  -- SYS-CLAIM-001 on/off (decision 11)
  readability_target    real,                           -- target readability score (task 8.3)
  updated_at            timestamptz not null default now()
);
create trigger brand_settings_updated_at before update on public.brand_settings
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Knowledge base: rules, facts, assets, exceptions
-- ---------------------------------------------------------------------------

-- One rule = one record = one retrieval unit (decision 5).
create table public.rules (
  id             uuid primary key default gen_random_uuid(),
  brand_id       uuid not null references public.brands (id) on delete cascade,
  rule_code      text not null check (rule_code ~ '^R-[0-9]{3,}$'),
  category       text not null check (category in
                   ('tone', 'terminology', 'messaging', 'claims', 'visuals',
                    'accessibility', 'legal', 'other')),
  text           text not null check (btrim(text) <> ''),
  source_doc     text,
  source_page    integer check (source_page >= 1),
  check_type     text not null default 'semantic'
                   check (check_type in ('deterministic', 'semantic')),
  det_kind       text check (det_kind in ('banned_terms', 'required_phrase')),
  terms          text[] not null default '{}',
  examples_bad   text[] not null default '{}',
  examples_good  text[] not null default '{}',
  always_on      boolean not null default false,
  status         text not null default 'pending'
                   check (status in ('pending', 'approved', 'rejected')),
  embedding      extensions.vector(768),
  tsv            tsvector generated always as (to_tsvector('english'::regconfig, text)) stored,
  approved_by    uuid references auth.users (id) on delete set null,
  approved_at    timestamptz,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  unique (brand_id, rule_code),
  -- Decision 7: a deterministic rule needs a kind and at least one term; semantic rules have no kind.
  constraint rules_deterministic_shape check (
    (check_type = 'deterministic' and det_kind is not null and cardinality(terms) > 0)
    or (check_type = 'semantic' and det_kind is null)
  )
);
create index rules_lookup_idx on public.rules (brand_id, status, check_type);
create index rules_embedding_idx on public.rules
  using hnsw (embedding extensions.vector_cosine_ops);
create index rules_tsv_idx on public.rules using gin (tsv);
create trigger rules_updated_at before update on public.rules
  for each row execute function public.set_updated_at();

-- Facts are structured rows; `statement` is what gets embedded (decision 9).
create table public.facts (
  id           uuid primary key default gen_random_uuid(),
  brand_id     uuid not null references public.brands (id) on delete cascade,
  fact_code    text not null check (fact_code ~ '^F-[0-9]{3,}$'),
  entity       text not null check (btrim(entity) <> ''),
  attribute    text not null check (btrim(attribute) <> ''),
  value        text not null,
  unit         text,
  statement    text not null check (btrim(statement) <> ''),
  source       text,
  valid_until  date,           -- expiry is checked in code, never by the LLM (decision 10)
  status       text not null default 'pending'
                 check (status in ('pending', 'approved', 'rejected')),
  embedding    extensions.vector(768),
  tsv          tsvector generated always as
                 (to_tsvector('english'::regconfig, entity || ' ' || statement)) stored,
  approved_by  uuid references auth.users (id) on delete set null,
  approved_at  timestamptz,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  unique (brand_id, fact_code)
);
create index facts_lookup_idx on public.facts (brand_id, status);
create index facts_entity_idx on public.facts (brand_id, lower(entity));  -- exact entity match first (decision 14)
create index facts_embedding_idx on public.facts
  using hnsw (embedding extensions.vector_cosine_ops);
create index facts_tsv_idx on public.facts using gin (tsv);
create trigger facts_updated_at before update on public.facts
  for each row execute function public.set_updated_at();

-- Round 3: logos, disclaimers, product descriptions and templates (task 12.4).
create table public.assets (
  id            uuid primary key default gen_random_uuid(),
  brand_id      uuid not null references public.brands (id) on delete cascade,
  kind          text not null check (kind in
                  ('logo', 'disclaimer', 'product_description', 'template', 'other')),
  name          text not null check (btrim(name) <> ''),
  description   text not null default '',
  storage_path  text,          -- file in Supabase Storage, if any
  text_content  text,          -- approved text (e.g. a disclaimer) used by fixes
  created_by    uuid references auth.users (id) on delete set null,
  created_at    timestamptz not null default now()
);
create index assets_brand_idx on public.assets (brand_id, kind);

-- The latest guideline verification reports (task 4.4).
create table public.guideline_reports (
  id          uuid primary key default gen_random_uuid(),
  brand_id    uuid not null references public.brands (id) on delete cascade,
  source_doc  text,
  report      jsonb not null,   -- VerificationReport: duplicates, contradictions, vague, missing_categories
  created_by  uuid references auth.users (id) on delete set null,
  created_at  timestamptz not null default now()
);
create index guideline_reports_brand_idx on public.guideline_reports (brand_id, created_at desc);

-- Fact changes found on the brand's website (task 12.3).
create table public.fact_changes (
  id          uuid primary key default gen_random_uuid(),
  brand_id    uuid not null references public.brands (id) on delete cascade,
  kind        text not null check (kind in ('new', 'changed')),
  fact_code   text,             -- the approved fact that changed (kind = changed)
  entity      text not null,
  attribute   text not null,
  old_value   text,
  new_value   text not null,
  unit        text,
  statement   text not null,
  source_url  text not null,
  status      text not null default 'pending' check (status in ('pending', 'accepted', 'rejected')),
  created_by  uuid references auth.users (id) on delete set null,
  decided_by  uuid references auth.users (id) on delete set null,
  decided_at  timestamptz,
  created_at  timestamptz not null default now()
);
create index fact_changes_brand_idx on public.fact_changes (brand_id, status, created_at desc);
-- ---------------------------------------------------------------------------
-- Content, versions, review units
-- ---------------------------------------------------------------------------

create table public.contents (
  id          uuid primary key default gen_random_uuid(),
  brand_id    uuid not null references public.brands (id) on delete cascade,
  title       text not null check (btrim(title) <> ''),
  format      text not null check (format in ('text', 'pdf', 'image', 'video')),
  status      text not null default 'draft' check (status in
                ('draft', 'checking', 'creator_review', 'manager_review',
                 'changes_requested', 'approved')),
  creator_id  uuid not null,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  unique (id, brand_id),
  -- The creator must belong to the same brand as the content.
  foreign key (creator_id, brand_id) references public.profiles (id, brand_id)
);
create index contents_brand_status_idx on public.contents (brand_id, status);
create index contents_creator_idx on public.contents (creator_id);
create trigger contents_updated_at before update on public.contents
  for each row execute function public.set_updated_at();

-- Each upload or edit creates a new version; flags belong to a version.
create table public.content_versions (
  id              uuid primary key default gen_random_uuid(),
  content_id      uuid not null,
  brand_id        uuid not null,
  version_number  integer not null check (version_number >= 1),
  storage_path    text,          -- original upload in Supabase Storage (PDF, image, video)
  mime_type       text,          -- type of the uploaded file
  alt_text        text,          -- for images: the creator's alt text
  captions_path   text,          -- for videos: an SRT or WebVTT captions file
  extracted_text  text,          -- full text the review ran on (before redaction)
  review_started_at  timestamptz,
  review_finished_at timestamptz,
  review_error       text,       -- why the last review failed, if it did
  created_by      uuid references auth.users (id) on delete set null,
  created_at      timestamptz not null default now(),
  unique (content_id, version_number),
  unique (id, brand_id),
  foreign key (content_id, brand_id) references public.contents (id, brand_id) on delete cascade
);
create index content_versions_content_idx on public.content_versions (content_id, version_number desc);

-- The units a version was split into for review (decision 15).
create table public.review_units (
  id          uuid primary key default gen_random_uuid(),
  version_id  uuid not null,
  brand_id    uuid not null,
  unit_id     text not null check (btrim(unit_id) <> ''),   -- e.g. 'u3', unique per version
  position    integer not null check (position >= 0),       -- reading order
  text        text not null,
  location    jsonb not null,   -- {paragraph, char_start, char_end} | {page, bbox} | {start, end} | {image_id, region}
  retrieved_rules text[] not null default '{}',  -- rule codes given to the judge (evaluation)
  created_at  timestamptz not null default now(),
  unique (version_id, unit_id),
  foreign key (version_id, brand_id)
    references public.content_versions (id, brand_id) on delete cascade
);

-- ---------------------------------------------------------------------------
-- Flags and their resolution
-- ---------------------------------------------------------------------------

-- The flag contract (TASKS.md Part 1) plus status and resolution.
create table public.flags (
  id               uuid primary key default gen_random_uuid(),
  version_id       uuid not null,
  brand_id         uuid not null,
  unit_id          text not null,
  source_type      text not null check (source_type in ('rule', 'fact', 'policy')),
  source_id        text not null check (btrim(source_id) <> ''),  -- 'R-012', 'F-004', 'SYS-CLAIM-001'
  category         text not null check (category in
                     ('tone', 'terminology', 'messaging', 'claims', 'visuals',
                      'accessibility', 'legal', 'other')),
  severity         text not null check (severity in ('low', 'medium', 'high')),
  evidence         text not null,          -- '' for a missing required phrase
  explanation      text not null check (btrim(explanation) <> ''),
  suggested_fix    text,
  confidence       real not null check (confidence between 0 and 1),
  location         jsonb not null,
  layer            text not null check (layer in ('rules', 'guidelines', 'claims', 'visuals')),
  status           text not null default 'open' check (status in
                     ('open', 'accepted', 'edited', 'dismissed', 'excepted')),
  resolution_note  text,
  resolved_by      uuid references auth.users (id) on delete set null,
  resolved_at      timestamptz,
  created_at       timestamptz not null default now(),
  unique (id, brand_id),
  foreign key (version_id, brand_id)
    references public.content_versions (id, brand_id) on delete cascade,
  -- Decision 20: a flag's unit must exist in its version.
  foreign key (version_id, unit_id)
    references public.review_units (version_id, unit_id) on delete cascade,
  -- Decision 2: dismissals and exceptions are stored with a reason.
  constraint flags_reason_required check (
    status not in ('dismissed', 'excepted') or btrim(coalesce(resolution_note, '')) <> ''
  )
);
create index flags_version_idx on public.flags (version_id, status);
create index flags_brand_source_idx on public.flags (brand_id, source_id, status);

-- AI findings removed by citation validation, kept with the reason (decision 20).
create table public.dropped_flags (
  id          uuid primary key default gen_random_uuid(),
  version_id  uuid not null,
  brand_id    uuid not null,
  payload     jsonb not null,     -- the flag as the model returned it
  reason      text not null check (btrim(reason) <> ''),  -- e.g. 'evidence_not_found'
  created_at  timestamptz not null default now(),
  foreign key (version_id, brand_id)
    references public.content_versions (id, brand_id) on delete cascade
);
create index dropped_flags_version_idx on public.dropped_flags (version_id);

-- Manager-approved exceptions: a flag with the same source and overlapping evidence is
-- dropped by citation validation (decision 20, task 7.3).
create table public.approved_exceptions (
  id           uuid primary key default gen_random_uuid(),
  brand_id     uuid not null references public.brands (id) on delete cascade,
  source_id    text not null check (btrim(source_id) <> ''),
  evidence     text not null check (btrim(evidence) <> ''),
  reason       text not null check (btrim(reason) <> ''),
  flag_id      uuid,            -- the flag the exception was approved from
  approved_by  uuid references auth.users (id) on delete set null,
  created_at   timestamptz not null default now(),
  foreign key (flag_id, brand_id) references public.flags (id, brand_id) on delete set null (flag_id)
);
create index approved_exceptions_lookup_idx on public.approved_exceptions (brand_id, source_id);

-- ---------------------------------------------------------------------------
-- Collaboration, audit, AI disclosure
-- ---------------------------------------------------------------------------

create table public.comments (
  id          uuid primary key default gen_random_uuid(),
  version_id  uuid not null,
  brand_id    uuid not null,
  author_id   uuid not null references auth.users (id) on delete cascade,
  body        text not null check (btrim(body) <> ''),
  flag_id     uuid,             -- optional: the flag this comment is about
  created_at  timestamptz not null default now(),
  foreign key (version_id, brand_id)
    references public.content_versions (id, brand_id) on delete cascade,
  foreign key (flag_id, brand_id) references public.flags (id, brand_id) on delete set null (flag_id)
);
create index comments_version_idx on public.comments (version_id, created_at);

-- Every workflow transition and admin change (task 7.1).
create table public.audit_log (
  id           bigint generated always as identity primary key,
  brand_id     uuid not null references public.brands (id) on delete cascade,
  actor_id     uuid references auth.users (id) on delete set null,  -- null = system
  action       text not null check (btrim(action) <> ''),           -- e.g. 'content.submit'
  entity_type  text not null check (btrim(entity_type) <> ''),      -- e.g. 'content', 'rule', 'flag'
  entity_id    text not null,
  before       jsonb,
  after        jsonb,
  created_at   timestamptz not null default now()
);
create index audit_log_entity_idx on public.audit_log (entity_type, entity_id, created_at);
create index audit_log_brand_idx on public.audit_log (brand_id, created_at desc);

-- Every model call (decision 25); drives the "AI used" labels.
create table public.ai_calls (
  id                  bigint generated always as identity primary key,
  brand_id            uuid references public.brands (id) on delete cascade,
  provider            text not null,       -- 'gemini' | 'groq' | 'openrouter'
  model               text not null,
  purpose             text not null,       -- e.g. 'judge', 'claim_extraction', 'embedding'
  content_version_id  uuid references public.content_versions (id) on delete set null,
  ok                  boolean not null,
  cached              boolean not null default false,
  latency_ms          integer check (latency_ms >= 0),
  error               text,
  created_at          timestamptz not null default now()
);
create index ai_calls_version_idx on public.ai_calls (content_version_id);
create index ai_calls_brand_idx on public.ai_calls (brand_id, created_at desc);

-- ---------------------------------------------------------------------------
-- Row-level security: on for every table (deny by default; see db/policies.sql)
-- ---------------------------------------------------------------------------

alter table public.brands              enable row level security;
alter table public.profiles            enable row level security;
alter table public.brand_settings      enable row level security;
alter table public.rules               enable row level security;
alter table public.facts               enable row level security;
alter table public.assets              enable row level security;
alter table public.contents            enable row level security;
alter table public.content_versions    enable row level security;
alter table public.review_units        enable row level security;
alter table public.flags               enable row level security;
alter table public.dropped_flags       enable row level security;
alter table public.approved_exceptions enable row level security;
alter table public.comments            enable row level security;
alter table public.audit_log           enable row level security;
alter table public.ai_calls            enable row level security;
alter table public.guideline_reports   enable row level security;
alter table public.fact_changes        enable row level security;

commit;
