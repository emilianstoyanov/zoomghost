-- How these tables were created in Supabase

-- 1. Table: users (linked to auth.users)
create table public.users (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null unique,
  slack_user_id text unique,
  zoom_user_id text unique,
  gcal_user_id text unique,
  preferences jsonb default '{}'::jsonb,
  created_at timestamp default now()
);

-- 2. Table: oauth_tokens
create table public.oauth_tokens (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.users(id) on delete cascade,
  provider text check (provider in ('zoom', 'slack', 'google')),
  access_token text not null,
  refresh_token text,
  expires_at timestamp,
  created_at timestamp default now()
);

-- 3. Table: meetings
create table public.meetings (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.users(id) on delete cascade,
  zoom_meeting_id text,
  title text,
  start_time timestamp,
  duration_minutes int,
  transcript text,
  summary text,
  language text default 'en',
  status text default 'pending',
  created_at timestamp default now()
);

-- 4. Table: notifications
create table public.notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.users(id) on delete cascade,
  meeting_id uuid references public.meetings(id) on delete cascade,
  sent_to_slack boolean default false,
  sent_to_email boolean default false,
  sent_at timestamp
);

-- 5. Indexes for faster lookups
create index idx_users_email on public.users(email);
create index idx_tokens_user on public.oauth_tokens(user_id);
create index idx_meetings_user on public.meetings(user_id);
create index idx_notifications_meeting on public.notifications(meeting_id);
