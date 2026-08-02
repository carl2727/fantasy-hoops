-- Fantasy NBA v2 — Supabase schema (v1)
-- Siehe docs/schema.md für die Begründung einzelner Entscheidungen.
-- Ausführen im Supabase SQL Editor (oder via `supabase db push`, sobald die Supabase CLI genutzt wird).

-- =========================================================================
-- Pipeline-Tabellen (geschrieben von pipeline/, taeglich per GitHub Action)
-- =========================================================================

create table players (
  player_id         bigint primary key,               -- NBA PERSON_ID
  name              text not null,                     -- DISPLAY_FIRST_LAST
  team_id           bigint,                            -- NBA TEAM_ID
  team_abbr         text,                              -- z. B. 'LAL'
  fantasy_positions text[] not null default '{}',       -- z. B. {PG,SG}, siehe product-spec.md 2.6
  updated_at        timestamptz not null default now()
);

create index players_fantasy_positions_gin_idx on players using gin (fantasy_positions);

create table ratings (
  player_id               bigint primary key references players (player_id) on delete cascade,
  season                  text not null default '2025-26',
  -- 9 Kategorie-Ratings, 0-100 skaliert (product-spec.md 2.2). TOV bereits invertiert.
  pts_rt                  numeric not null,
  reb_rt                  numeric not null,
  ast_rt                  numeric not null,
  fgn_rt                  numeric not null,
  ftn_rt                  numeric not null,
  fg3m_rt                 numeric not null,
  blk_rt                  numeric not null,
  stl_rt                  numeric not null,
  tov_rt                  numeric not null,
  availability_score      numeric not null,            -- product-spec.md 2.3
  -- Basis-Ratings ohne Punt (ADR 0002). Punt-Varianten werden NICHT gespeichert,
  -- sondern vom Frontend zur Laufzeit aus den 9 Kategorie-Ratings berechnet.
  total_rating            numeric not null,            -- "Overall Rating"
  total_available_rating  numeric not null,            -- "Performance Rating"
  combined_rating         numeric not null,            -- "Combined Rating"
  updated_at              timestamptz not null default now()
);

create index ratings_total_rating_idx on ratings (total_rating desc);

create table pipeline_runs (
  id             bigint generated always as identity primary key,
  run_at         timestamptz not null default now(),
  season         text not null,
  games_ingested int not null default 0,
  status         text not null check (status in ('success', 'partial', 'failed')),
  note           text
);

create index pipeline_runs_run_at_idx on pipeline_runs (run_at desc);

alter table players enable row level security;
alter table ratings enable row level security;
alter table pipeline_runs enable row level security;

create policy "players are public read" on players for select using (true);
create policy "ratings are public read" on ratings for select using (true);
create policy "pipeline_runs are public read" on pipeline_runs for select using (true);
-- Kein INSERT/UPDATE/DELETE-Policy fuer normale Nutzer -> nur der Service-Role-Key
-- (von der GitHub Action verwendet, umgeht RLS grundsaetzlich) kann hier schreiben.

-- =========================================================================
-- App-Tabellen (geschrieben von eingeloggten Nutzern ueber die Website)
-- =========================================================================

create table teams (
  id         bigint generated always as identity primary key,
  creator_id uuid not null references auth.users (id) on delete cascade,
  name       text not null,
  is_active  boolean not null default false,
  created_at timestamptz not null default now()
);

-- Garantiert "genau ein aktives Team pro Nutzer" auf DB-Ebene statt nur per Anwendungslogik (siehe docs/schema.md).
create unique index teams_one_active_per_user_idx on teams (creator_id) where is_active;

create table team_players (
  team_id    bigint not null references teams (id) on delete cascade,
  player_id  bigint not null references players (player_id) on delete cascade,
  status     text not null default 'AVAILABLE' check (status in ('ON_TEAM', 'AVAILABLE', 'UNAVAILABLE')),
  primary key (team_id, player_id)
);

create table draft_picks (
  team_id     bigint not null references teams (id) on delete cascade,
  player_id   bigint not null references players (player_id) on delete cascade,
  pick_number int not null,
  primary key (team_id, player_id),
  -- Deferrable: erlaubt das Vertauschen zweier pick_number-Werte in einem einzigen UPDATE
  -- innerhalb einer Transaktion, ohne den v1-Placeholder-Hack (siehe docs/schema.md).
  constraint draft_picks_team_pick_unique unique (team_id, pick_number) deferrable initially deferred
);

create table user_player_state (
  user_id       uuid not null references auth.users (id) on delete cascade,
  player_id     bigint not null references players (player_id) on delete cascade,
  is_highlighted boolean not null default false,
  is_injured     boolean not null default false,
  primary key (user_id, player_id)
);

alter table teams enable row level security;
alter table team_players enable row level security;
alter table draft_picks enable row level security;
alter table user_player_state enable row level security;

create policy "users manage their own teams" on teams
  for all using (auth.uid() = creator_id) with check (auth.uid() = creator_id);

create policy "users manage their own team_players" on team_players
  for all using (
    exists (select 1 from teams where teams.id = team_players.team_id and teams.creator_id = auth.uid())
  ) with check (
    exists (select 1 from teams where teams.id = team_players.team_id and teams.creator_id = auth.uid())
  );

create policy "users manage their own draft_picks" on draft_picks
  for all using (
    exists (select 1 from teams where teams.id = draft_picks.team_id and teams.creator_id = auth.uid())
  ) with check (
    exists (select 1 from teams where teams.id = draft_picks.team_id and teams.creator_id = auth.uid())
  );

create policy "users manage their own player state" on user_player_state
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
