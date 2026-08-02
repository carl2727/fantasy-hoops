"""Alles, was mit Supabase spricht. Nutzt den Service-Role-Key -> umgeht RLS bewusst
(siehe docs/environment.md) und darf deshalb NUR hier, nie im Frontend, verwendet werden."""
import math

import numpy as np
from supabase import Client, create_client

from . import config


def get_client() -> Client:
    url = config.require_env(config.SUPABASE_URL_ENV)
    key = config.require_env(config.SUPABASE_SERVICE_ROLE_KEY_ENV)
    return create_client(url, key)


def _sanitize_value(value):
    """pandas/numpy-Skalare (int64, float64, NaN) sind nicht JSON-serialisierbar --
    in native Python-Typen umwandeln, bevor sie an den Supabase-Client gehen."""
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _sanitize_records(records: list[dict]) -> list[dict]:
    return [{key: _sanitize_value(value) for key, value in record.items()} for record in records]


def upsert_players(client: Client, players: list[dict]) -> None:
    if not players:
        return
    client.table("players").upsert(_sanitize_records(players), on_conflict="player_id").execute()


def sync_ratings(client: Client, ratings: list[dict]) -> None:
    """Ersetzt den kompletten Inhalt von `ratings` durch die heutigen Werte:
    upsert der aktuellen Zeilen + loeschen aller Zeilen, die heute nicht mehr
    vorkommen (z. B. Spieler ohne Spiele mehr in der laufenden Saison)."""
    current_ids = {_sanitize_value(row["player_id"]) for row in ratings}

    existing = client.table("ratings").select("player_id").execute().data or []
    existing_ids = {row["player_id"] for row in existing}

    stale_ids = existing_ids - current_ids
    if stale_ids:
        client.table("ratings").delete().in_("player_id", list(stale_ids)).execute()

    if ratings:
        client.table("ratings").upsert(_sanitize_records(ratings), on_conflict="player_id").execute()


def log_pipeline_run(client: Client, *, season: str, games_ingested: int, status: str, note: str = "") -> None:
    client.table("pipeline_runs").insert({
        "season": season,
        "games_ingested": games_ingested,
        "status": status,
        "note": note,
    }).execute()


def get_existing_player_ids(client: Client) -> set[int]:
    rows = client.table("players").select("player_id").execute().data or []
    return {row["player_id"] for row in rows}
