-- 004 (task 11.5): an optional captions file (SRT or WebVTT) per video version.
-- Folded into db/schema.sql for fresh installs.
begin;
alter table public.content_versions add column captions_path text;
commit;
