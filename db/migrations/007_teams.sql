-- 007: role-based teams.
-- * A user picks one role at sign-up (profiles.role) and can belong to several brands
--   (brand_members). profiles.brand_id becomes the user's ACTIVE brand (nullable until an
--   admin adds them to a team); the API re-checks it against brand_members on every request.
-- * Content is no longer tied to the creator's single brand by a foreign key; it is
--   assigned to a manager (who must be on the brand's team) when it is submitted.
-- Folded into db/schema.sql and db/policies.sql for fresh installs.
begin;

create table public.brand_members (
  brand_id    uuid not null references public.brands (id) on delete cascade,
  user_id     uuid not null references public.profiles (id) on delete cascade,
  role        text not null check (role in ('admin', 'creator', 'manager')),
  added_by    uuid references public.profiles (id) on delete set null,
  created_at  timestamptz not null default now(),
  primary key (brand_id, user_id)
);
create index brand_members_user_idx on public.brand_members (user_id);

-- Everyone who exists today is a member of their current brand.
insert into public.brand_members (brand_id, user_id, role)
select brand_id, id, role from public.profiles
on conflict do nothing;

-- The active brand may be empty (a new creator or manager not yet on any team), and
-- deleting a brand must not delete its people.
alter table public.profiles alter column brand_id drop not null;
alter table public.profiles drop constraint profiles_brand_id_fkey;
alter table public.profiles add constraint profiles_brand_id_fkey
  foreign key (brand_id) references public.brands (id) on delete set null;

-- A creator can work for several brands, so content only requires a real creator.
alter table public.contents drop constraint contents_creator_id_brand_id_fkey;
alter table public.contents add constraint contents_creator_id_fkey
  foreign key (creator_id) references public.profiles (id);

-- The manager the creator submitted to.
alter table public.contents
  add column assigned_manager_id uuid references public.profiles (id) on delete set null;
create index contents_manager_idx on public.contents (assigned_manager_id);

-- Brands know who created them.
alter table public.brands add column owner_id uuid references public.profiles (id) on delete set null;
update public.brands b set owner_id = (
  select m.user_id from public.brand_members m
  where m.brand_id = b.id and m.role = 'admin' order by m.created_at limit 1
);

-- Row-level security now follows team membership.
create or replace function private.is_brand_member(b uuid) returns boolean
language sql stable security definer set search_path = ''
as $$
  select exists (
    select 1 from public.brand_members m where m.user_id = (select auth.uid()) and m.brand_id = b
  );
$$;

create or replace function private.has_brand_role(b uuid, roles text[]) returns boolean
language sql stable security definer set search_path = ''
as $$
  select exists (
    select 1 from public.brand_members m
    where m.user_id = (select auth.uid()) and m.brand_id = b and m.role = any (roles)
  );
$$;

create or replace function private.can_see_content(c uuid) returns boolean
language sql stable security definer set search_path = ''
as $$
  select exists (
    select 1
    from public.contents ct
    join public.brand_members m on m.user_id = (select auth.uid()) and m.brand_id = ct.brand_id
    where ct.id = c and (ct.creator_id = m.user_id or m.role in ('admin', 'manager'))
  );
$$;

alter table public.brand_members enable row level security;
create policy brand_members_select on public.brand_members
  for select to authenticated using (private.is_brand_member(brand_id));

commit;
