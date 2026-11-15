-- 003 (task 8.1): the uploaded file's type and, for images, its alt text.
-- Folded into db/schema.sql for fresh installs.
begin;

alter table public.content_versions
  add column mime_type text,
  add column alt_text  text;

commit;
