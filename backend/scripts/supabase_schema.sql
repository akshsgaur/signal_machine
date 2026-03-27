create extension if not exists pgcrypto;

create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create table if not exists user_integrations (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  integration_type text not null,
  oauth_token text,
  credentials_json jsonb,
  connected_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, integration_type)
);

create index if not exists user_integrations_user_id_idx
  on user_integrations (user_id);

create trigger user_integrations_set_updated_at
before update on user_integrations
for each row execute function set_updated_at();

create table if not exists workspace_integrations (
  id uuid primary key default gen_random_uuid(),
  workspace_id text not null,
  integration_type text not null,
  oauth_token text,
  credentials_json jsonb,
  connected_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, integration_type)
);

create index if not exists workspace_integrations_workspace_id_idx
  on workspace_integrations (workspace_id);

create trigger workspace_integrations_set_updated_at
before update on workspace_integrations
for each row execute function set_updated_at();

create table if not exists macroscope_runs (
  id uuid primary key default gen_random_uuid(),
  workspace_id text not null,
  user_id text not null,
  pipeline_run_id uuid,
  chat_session_id uuid,
  mode text not null check (mode in ('chat', 'pipeline')),
  query text not null,
  workflow_id text unique,
  status text not null check (status in ('queued', 'running', 'complete', 'failed', 'timeout')),
  response text,
  error text,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create index if not exists macroscope_runs_workspace_id_idx
  on macroscope_runs (workspace_id);

create index if not exists macroscope_runs_pipeline_run_id_idx
  on macroscope_runs (pipeline_run_id);

create index if not exists macroscope_runs_chat_session_id_idx
  on macroscope_runs (chat_session_id);

create index if not exists macroscope_runs_status_idx
  on macroscope_runs (status);

create table if not exists pipeline_runs (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  hypothesis text not null,
  product_area text not null,
  status text not null check (status in ('running','complete','failed','timeout')),
  brief text,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create index if not exists pipeline_runs_user_id_idx
  on pipeline_runs (user_id);
create index if not exists pipeline_runs_status_idx
  on pipeline_runs (status);

create table if not exists chat_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  title text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists chat_sessions_user_id_idx
  on chat_sessions (user_id);

create trigger chat_sessions_set_updated_at
before update on chat_sessions
for each row execute function set_updated_at();

create table if not exists chat_messages (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references chat_sessions(id) on delete cascade,
  role text not null check (role in ('user','assistant')),
  content text not null,
  sources_used text[] default '{}'::text[],
  created_at timestamptz not null default now()
);

create index if not exists chat_messages_session_id_idx
  on chat_messages (session_id);

create table if not exists slack_messages (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  team_id text not null,
  channel_id text not null,
  slack_user_id text not null,
  text text not null,
  ts text not null,
  thread_ts text,
  is_dm boolean not null default false,
  raw jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists slack_messages_user_id_idx
  on slack_messages (user_id);

create index if not exists slack_messages_team_id_idx
  on slack_messages (team_id);

create index if not exists slack_messages_created_at_idx
  on slack_messages (created_at desc);

create table if not exists insights_folders (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  name text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, name)
);

create index if not exists insights_folders_user_id_idx
  on insights_folders (user_id);

create trigger insights_folders_set_updated_at
before update on insights_folders
for each row execute function set_updated_at();
