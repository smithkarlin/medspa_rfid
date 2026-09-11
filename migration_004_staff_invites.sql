-- ============================================================
-- Migration 004: staff invites
--
-- Lets a clinic admin invite teammates by email instead of every new
-- signup creating its own brand-new clinic. An invited person signs up
-- normally; on first login the app checks for a pending invite matching
-- their email and, if found, joins them to that clinic (with the role
-- the admin picked) instead of showing the "create a clinic" form.
--
-- Run this in the Supabase SQL Editor against an existing database that
-- already has schema.sql applied. (schema.sql itself has also been
-- updated with all of this, for fresh installs.)
-- ============================================================

-- ---- profiles: add an email column, backfilled from auth.users ----
-- Convenient for an admin's staff roster (full_name is often blank) and
-- needed so accept_pending_invite() can match an invite by email.
alter table profiles add column if not exists email text;

update profiles p
set email = u.email
from auth.users u
where u.id = p.id and p.email is null;

-- ---- invites ----
create table if not exists invites (
    id uuid primary key default gen_random_uuid(),
    clinic_id uuid not null references clinics(id) on delete cascade,
    email text not null,
    role text not null default 'staff' check (role in ('admin', 'staff')),
    invited_by uuid references profiles(id) on delete set null,
    status text not null default 'pending' check (status in ('pending', 'accepted', 'revoked')),
    created_at timestamptz default now(),
    accepted_at timestamptz
);

-- Only one *pending* invite per clinic+email at a time; an accepted or
-- revoked invite doesn't block re-inviting the same address later.
create unique index if not exists invites_pending_email_idx
    on invites (clinic_id, lower(email))
    where status = 'pending';

alter table invites enable row level security;

-- ---- auth_is_admin(): the calling user's role on their own clinic ----
create or replace function auth_is_admin() returns boolean
language sql stable
as $$
  select coalesce((select role = 'admin' from profiles where id = auth.uid()), false)
$$;

-- Admins manage invites for their own clinic only.
drop policy if exists "invites: admins manage their clinic's invites" on invites;
create policy "invites: admins manage their clinic's invites" on invites
    for all
    using (clinic_id = auth_clinic_id() and auth_is_admin())
    with check (clinic_id = auth_clinic_id() and auth_is_admin());

-- Admins can also see every profile in their own clinic (a staff roster),
-- not just their own row. The original "read own row" policy stays, so a
-- non-admin can still see their own profile.
drop policy if exists "profiles: admins read clinic roster" on profiles;
create policy "profiles: admins read clinic roster" on profiles
    for select using (clinic_id = auth_clinic_id() and auth_is_admin());

-- ---- create_clinic_and_profile: also stash the user's email ----
create or replace function create_clinic_and_profile(clinic_name text, full_name text)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  new_clinic_id uuid;
  user_email text;
begin
  if auth.uid() is null then
    raise exception 'Not authenticated';
  end if;

  select email into user_email from auth.users where id = auth.uid();

  insert into clinics (name) values (clinic_name) returning id into new_clinic_id;

  insert into profiles (id, clinic_id, full_name, role, email)
  values (auth.uid(), new_clinic_id, full_name, 'admin', user_email);

  return new_clinic_id;
end;
$$;

grant execute on function create_clinic_and_profile(text, text) to authenticated;

-- ---- get_my_pending_invite(): read-only lookup, no profile required ----
-- A brand-new user has no profile row yet, so the RLS policy above (which
-- requires being an admin of the invite's clinic) can't let them see their
-- own pending invite directly. This SECURITY DEFINER function runs as the
-- table owner so it can look the invite up by the caller's own auth email,
-- without exposing any other clinic's invites.
create or replace function get_my_pending_invite()
returns table(invite_id uuid, clinic_id uuid, clinic_name text, role text)
language plpgsql
security definer
set search_path = public
as $$
declare
  user_email text;
begin
  if auth.uid() is null then
    return;
  end if;

  select email into user_email from auth.users where id = auth.uid();
  if user_email is null then
    return;
  end if;

  return query
    select i.id, i.clinic_id, c.name, i.role
    from invites i
    join clinics c on c.id = i.clinic_id
    where lower(i.email) = lower(user_email) and i.status = 'pending'
    order by i.created_at asc
    limit 1;
end;
$$;

grant execute on function get_my_pending_invite() to authenticated;

-- ---- accept_pending_invite(): joins the caller to the inviting clinic ----
-- Same chicken-and-egg reasoning as create_clinic_and_profile: the caller
-- has no profile yet, so a plain insert would be invisible to them under
-- RLS. Runs as the table owner, but only ever acts using the caller's own
-- auth.uid() and auth email -- it can't be pointed at anyone else's invite.
create or replace function accept_pending_invite(full_name text)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  invite_row invites%rowtype;
  user_email text;
begin
  if auth.uid() is null then
    raise exception 'Not authenticated';
  end if;

  -- Already has a profile (e.g. double-submit) -- nothing to do.
  if exists (select 1 from profiles where id = auth.uid()) then
    return (select clinic_id from profiles where id = auth.uid());
  end if;

  select email into user_email from auth.users where id = auth.uid();
  if user_email is null then
    return null;
  end if;

  select * into invite_row
    from invites
    where lower(email) = lower(user_email) and status = 'pending'
    order by created_at asc
    limit 1;

  if invite_row.id is null then
    return null;
  end if;

  insert into profiles (id, clinic_id, full_name, role, email)
  values (auth.uid(), invite_row.clinic_id, full_name, invite_row.role, user_email);

  update invites set status = 'accepted', accepted_at = now() where id = invite_row.id;

  return invite_row.clinic_id;
end;
$$;

grant execute on function accept_pending_invite(text) to authenticated;
