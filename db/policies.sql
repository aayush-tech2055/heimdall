-- Heimdall row-level security policies (task 2.2). Apply after db/schema.sql:
--     psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/policies.sql
--
-- Who can do what through the Supabase API (signed-in users, role `authenticated`):
-- * Everyone sees their own brand, its people, settings, rules, facts, assets and exceptions.
-- * Only admins write rules, facts, assets and brand settings.
-- * Creators see only their own content (and its versions, units, flags and comments);
--   managers and admins see all content of their brand.
-- * Managers and admins record approved exceptions and read the audit log and dropped flags.
-- * Content, versions, units, flags, comments, audit log and AI-call rows are read-only here:
--   they are written by the FastAPI backend, which enforces the workflow state machine
--   (task 7.1) and connects as the database owner (not subject to RLS).
-- * Anonymous users (role `anon`) get no policies, so they see nothing.
-- Nobody can change their own role or brand: profiles are written only by the backend/seed.

begin;

-- ---------------------------------------------------------------------------
-- Helper functions. SECURITY DEFINER so they can read profiles/contents without
-- re-entering RLS; kept in a schema the Supabase API does not expose.
-- ---------------------------------------------------------------------------

create schema if not exists private;
grant usage on schema private to authenticated;

-- Is the signed-in user a member of brand `b` (any role)?
create function private.is_brand_member(b uuid) returns boolean
language sql stable security definer set search_path = ''
as $$
  select exists (
    select 1 from public.profiles p where p.id = (select auth.uid()) and p.brand_id = b
  );
$$;

-- Does the signed-in user have one of `roles` in brand `b`?
create function private.has_brand_role(b uuid, roles text[]) returns boolean
language sql stable security definer set search_path = ''
as $$
  select exists (
    select 1 from public.profiles p
    where p.id = (select auth.uid()) and p.brand_id = b and p.role = any (roles)
  );
$$;

-- Can the signed-in user see content `c`? Its creator, or a manager/admin of its brand.
create function private.can_see_content(c uuid) returns boolean
language sql stable security definer set search_path = ''
as $$
  select exists (
    select 1
    from public.contents ct
    join public.profiles p on p.id = (select auth.uid()) and p.brand_id = ct.brand_id
    where ct.id = c and (ct.creator_id = p.id or p.role in ('admin', 'manager'))
  );
$$;

-- Can the signed-in user see content version `v`? Same rule as its content.
create function private.can_see_version(v uuid) returns boolean
language sql stable security definer set search_path = ''
as $$
  select exists (
    select 1 from public.content_versions cv
    where cv.id = v and private.can_see_content(cv.content_id)
  );
$$;

revoke all on function private.is_brand_member(uuid) from public;
revoke all on function private.has_brand_role(uuid, text[]) from public;
revoke all on function private.can_see_content(uuid) from public;
revoke all on function private.can_see_version(uuid) from public;
grant execute on function private.is_brand_member(uuid) to authenticated;
grant execute on function private.has_brand_role(uuid, text[]) to authenticated;
grant execute on function private.can_see_content(uuid) to authenticated;
grant execute on function private.can_see_version(uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- Brand, people, settings
-- ---------------------------------------------------------------------------

create policy brands_select on public.brands
  for select to authenticated using (private.is_brand_member(id));

create policy profiles_select on public.profiles
  for select to authenticated using (private.is_brand_member(brand_id));

create policy brand_settings_select on public.brand_settings
  for select to authenticated using (private.is_brand_member(brand_id));
create policy brand_settings_admin_insert on public.brand_settings
  for insert to authenticated with check (private.has_brand_role(brand_id, '{admin}'));
create policy brand_settings_admin_update on public.brand_settings
  for update to authenticated
  using (private.has_brand_role(brand_id, '{admin}'))
  with check (private.has_brand_role(brand_id, '{admin}'));

-- ---------------------------------------------------------------------------
-- Knowledge base: everyone in the brand reads; only admins write
-- ---------------------------------------------------------------------------

create policy rules_select on public.rules
  for select to authenticated using (private.is_brand_member(brand_id));
create policy rules_admin_insert on public.rules
  for insert to authenticated with check (private.has_brand_role(brand_id, '{admin}'));
create policy rules_admin_update on public.rules
  for update to authenticated
  using (private.has_brand_role(brand_id, '{admin}'))
  with check (private.has_brand_role(brand_id, '{admin}'));
create policy rules_admin_delete on public.rules
  for delete to authenticated using (private.has_brand_role(brand_id, '{admin}'));

create policy facts_select on public.facts
  for select to authenticated using (private.is_brand_member(brand_id));
create policy facts_admin_insert on public.facts
  for insert to authenticated with check (private.has_brand_role(brand_id, '{admin}'));
create policy facts_admin_update on public.facts
  for update to authenticated
  using (private.has_brand_role(brand_id, '{admin}'))
  with check (private.has_brand_role(brand_id, '{admin}'));
create policy facts_admin_delete on public.facts
  for delete to authenticated using (private.has_brand_role(brand_id, '{admin}'));

create policy assets_select on public.assets
  for select to authenticated using (private.is_brand_member(brand_id));
create policy assets_admin_insert on public.assets
  for insert to authenticated with check (private.has_brand_role(brand_id, '{admin}'));
create policy assets_admin_update on public.assets
  for update to authenticated
  using (private.has_brand_role(brand_id, '{admin}'))
  with check (private.has_brand_role(brand_id, '{admin}'));
create policy assets_admin_delete on public.assets
  for delete to authenticated using (private.has_brand_role(brand_id, '{admin}'));

-- Exceptions are approved by managers (task 7.3); everyone in the brand can read them.
create policy approved_exceptions_select on public.approved_exceptions
  for select to authenticated using (private.is_brand_member(brand_id));
create policy approved_exceptions_manager_insert on public.approved_exceptions
  for insert to authenticated
  with check (private.has_brand_role(brand_id, '{admin,manager}'));
create policy approved_exceptions_manager_delete on public.approved_exceptions
  for delete to authenticated using (private.has_brand_role(brand_id, '{admin,manager}'));

create policy guideline_reports_select on public.guideline_reports
  for select to authenticated using (private.has_brand_role(brand_id, '{admin,manager}'));

-- ---------------------------------------------------------------------------
-- Content and review results: creators see their own, managers/admins their brand
-- ---------------------------------------------------------------------------

create policy contents_select on public.contents
  for select to authenticated
  using (
    creator_id = (select auth.uid())
    or private.has_brand_role(brand_id, '{admin,manager}')
  );

create policy content_versions_select on public.content_versions
  for select to authenticated using (private.can_see_content(content_id));

create policy review_units_select on public.review_units
  for select to authenticated using (private.can_see_version(version_id));

create policy flags_select on public.flags
  for select to authenticated using (private.can_see_version(version_id));

create policy comments_select on public.comments
  for select to authenticated using (private.can_see_version(version_id));

create policy dropped_flags_select on public.dropped_flags
  for select to authenticated using (private.has_brand_role(brand_id, '{admin,manager}'));

-- ---------------------------------------------------------------------------
-- Audit and AI disclosure
-- ---------------------------------------------------------------------------

create policy audit_log_select on public.audit_log
  for select to authenticated using (private.has_brand_role(brand_id, '{admin,manager}'));

-- Managers/admins see all AI calls of their brand; a creator sees those for content they can see.
create policy ai_calls_select on public.ai_calls
  for select to authenticated
  using (
    private.has_brand_role(brand_id, '{admin,manager}')
    or (content_version_id is not null and private.can_see_version(content_version_id))
  );

commit;
