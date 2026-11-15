-- 006: guideline uploads run in the background; one row per upload (one or more files).
-- Folded into db/schema.sql and db/policies.sql for fresh installs.
begin;

create table public.guideline_jobs (
  id           uuid primary key default gen_random_uuid(),
  brand_id     uuid not null references public.brands (id) on delete cascade,
  status       text not null default 'queued'
                 check (status in ('queued', 'running', 'done', 'failed')),
  files        jsonb not null,            -- [{"name": "guide.pdf", "pages": 6}, ...]
  files_done   integer not null default 0 check (files_done >= 0),
  rules_added  integer not null default 0 check (rules_added >= 0),
  error        text,
  created_by   uuid references auth.users (id) on delete set null,
  created_at   timestamptz not null default now(),
  finished_at  timestamptz
);
create index guideline_jobs_brand_idx on public.guideline_jobs (brand_id, created_at desc);
alter table public.guideline_jobs enable row level security;
create policy guideline_jobs_select on public.guideline_jobs
  for select to authenticated using (private.has_brand_role(brand_id, '{admin,manager}'));

commit;
