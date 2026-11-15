-- 005 (task 12.3): fact changes found on the brand's website, waiting for an admin.
-- Folded into db/schema.sql and db/policies.sql for fresh installs.
begin;

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
alter table public.fact_changes enable row level security;
create policy fact_changes_select on public.fact_changes
  for select to authenticated using (private.has_brand_role(brand_id, '{admin}'));

commit;
