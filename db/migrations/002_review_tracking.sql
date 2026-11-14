-- 002 (task 6.7): review timing and errors per version, and the rules retrieved per unit
-- (for the evaluation's retrieval recall). Folded into db/schema.sql for fresh installs.
begin;

alter table public.content_versions
  add column review_started_at  timestamptz,
  add column review_finished_at timestamptz,
  add column review_error       text;

alter table public.review_units
  add column retrieved_rules text[] not null default '{}';

commit;
