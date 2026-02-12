-- Enable pgvector extension for knowledge base
create extension if not exists vector;

-- PROFILES (Users)
-- Links to Supabase Auth.users
create table public.profiles (
  id uuid references auth.users not null primary key,
  username text unique,
  avatar_url text,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- CAMPAIGNS
create table public.campaigns (
  id uuid default gen_random_uuid() primary key,
  name text not null,
  description text,
  gm_id uuid references public.profiles(id) not null,
  status text check (status in ('active', 'paused', 'completed')) default 'active',
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  api_key text,
  model text,
  system_prompt text,
  template_id text
);

-- GAME STATES
-- Stores the snapshot of the game at any point
create table public.game_states (
  id uuid default gen_random_uuid() primary key,
  campaign_id uuid references public.campaigns(id) not null,
  turn_index integer default 0,
  phase text default 'exploration',

  -- The core state blob (Using JSONB for flexibility as per architecture)
  state_data jsonb not null default '{}'::jsonb,

  updated_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- CHAT LOGS
-- Persistent chat history for context injection
create table public.chat_messages (
  id uuid default gen_random_uuid() primary key,
  campaign_id uuid references public.campaigns(id) not null,
  sender_id text not null, -- Could be a profile UUID or an AI Agent ID (string)
  sender_name text not null,
  content text not null,
  is_tool_output boolean default false,

  created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- KNOWLEDGE BASE (Vector Store)
create table public.lore_documents (
  id uuid default gen_random_uuid() primary key,
  campaign_id uuid references public.campaigns(id), -- Optional: null = global rules
  content text not null,
  embedding vector(1536), -- OpenAI / standard dimension
  metadata jsonb default '{}'::jsonb
);

-- RLS POLICIES (Simple start)
alter table public.profiles enable row level security;
alter table public.campaigns enable row level security;
alter table public.game_states enable row level security;
alter table public.chat_messages enable row level security;

create policy "Public profiles are viewable by everyone."
  on profiles for select
  using ( true );

create policy "Users can insert their own profile."
  on profiles for insert
  with check ( auth.uid() = id );

create policy "Campaigns are viewable by participants."
  on campaigns for select
  using ( auth.uid() = gm_id ); -- simplified for now


-- DEBUG LOGS
create table public.debug_logs (
  id uuid default gen_random_uuid() primary key,
  campaign_id uuid references public.campaigns(id) not null,
  type text not null,
  content text,
  full_content jsonb,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

create policy "Debug logs are viewable by participants."
  on debug_logs for select
  using ( auth.uid() = (select gm_id from campaigns where id = campaign_id) ); -- Only GM? Or all? Let's say all for now or strict GM.
