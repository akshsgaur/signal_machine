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
  integration_type text not null check (integration_type in ('amplitude','zendesk','productboard','linear')),
  oauth_token text not null,
  connected_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, integration_type)
);

create index if not exists user_integrations_user_id_idx
  on user_integrations (user_id);

create trigger user_integrations_set_updated_at
before update on user_integrations
for each row execute function set_updated_at();

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

alter table user_integrations enable row level security;
alter table pipeline_runs enable row level security;
alter table chat_sessions enable row level security;
alter table chat_messages enable row level security;

create policy "select own integrations"
on user_integrations for select
using (user_id = auth.jwt() ->> 'sub');

create policy "insert own integrations"
on user_integrations for insert
with check (user_id = auth.jwt() ->> 'sub');

create policy "update own integrations"
on user_integrations for update
using (user_id = auth.jwt() ->> 'sub');

create policy "select own runs"
on pipeline_runs for select
using (user_id = auth.jwt() ->> 'sub');

create policy "insert own runs"
on pipeline_runs for insert
with check (user_id = auth.jwt() ->> 'sub');

create policy "update own runs"
on pipeline_runs for update
using (user_id = auth.jwt() ->> 'sub');

create policy "select own sessions"
on chat_sessions for select
using (user_id = auth.jwt() ->> 'sub');

create policy "insert own sessions"
on chat_sessions for insert

with check (user_id = auth.jwt() ->> 'sub');

create policy "update own sessions"
on chat_sessions for update
using (user_id = auth.jwt() ->> 'sub');

create policy "select own messages"
on chat_messages for select
using (
  exists (
    select 1 from chat_sessions s
    where s.id = chat_messages.session_id
      and s.user_id = auth.jwt() ->> 'sub'
  )
);

create policy "insert own messages"
on chat_messages for insert
with check (
  exists (
    select 1 from chat_sessions s
    where s.id = chat_messages.session_id
      and s.user_id = auth.jwt() ->> 'sub'
  )
);
