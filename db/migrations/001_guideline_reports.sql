-- 001 (task 4.4): keep each guideline verification report so the admin screen can show the
-- latest one. Already folded into db/schema.sql and db/policies.sql for fresh installs.
begin;

create table public.guideline_reports (
  id          uuid primary key default gen_random_uuid(),
  brand_id    uuid not null references public.brands (id) on delete cascade,
  source_doc  text,
  report      jsonb not null,   -- VerificationReport: duplicates, contradictions, vague, missing_categories
  created_by  uuid references auth.users (id) on delete set null,
  created_at  timestamptz not null default now()
);
create index guideline_reports_brand_idx on public.guideline_reports (brand_id, created_at desc);
alter table public.guideline_reports enable row level security;

create policy guideline_reports_select on public.guideline_reports
  for select to authenticated using (private.has_brand_role(brand_id, '{admin,manager}'));

commit;
