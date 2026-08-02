"""
Datenabruf ueber nba_api. Nutzt bewusst nur Endpunkte, die im alten fantasy_nba-Projekt
bereits produktiv liefen (load_data.py, update_nba_game_logs.py, fetch_positions.py) --
keine neuen, ungetesteten Endpunkte, damit die Pipeline beim ersten echten Lauf verlaesslich ist.
"""
import time

import pandas as pd
import requests
from nba_api.stats.endpoints import CommonAllPlayers, CommonPlayerInfo, LeagueGameLog

from . import config

# stats.nba.com antwortet von Cloud-/Rechenzentrums-IPs (z. B. GitHub-Actions-Runnern) gelegentlich
# sehr langsam -- kein Blockieren, sondern einfaches Timeout beim Standard-30s-Limit von nba_api.
# Deshalb hier grosszuegigerer Timeout + Retry mit Backoff fuer die beiden Calls, ohne die der
# gesamte Lauf nicht sinnvoll weitermachen kann.
DEFAULT_TIMEOUT_SECONDS = 60
MAX_RETRIES = 4
RETRY_BACKOFF_SECONDS = 8


def _call_with_retries(fn, *, description: str):
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fn()
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as exc:
            last_exc = exc
            wait_seconds = RETRY_BACKOFF_SECONDS * attempt
            print(f"{description}: Versuch {attempt}/{MAX_RETRIES} fehlgeschlagen ({exc}). "
                  f"Warte {wait_seconds}s und versuche erneut...")
            time.sleep(wait_seconds)
    raise last_exc


def fetch_all_players() -> pd.DataFrame:
    """Aktuelle Saison-Roster-Liste: PERSON_ID, DISPLAY_FIRST_LAST, TEAM_ID, TEAM_NAME."""
    def _fetch():
        result = CommonAllPlayers(is_only_current_season=1, timeout=DEFAULT_TIMEOUT_SECONDS)
        return result.get_data_frames()[0]

    df = _call_with_retries(_fetch, description="CommonAllPlayers")
    return df[["PERSON_ID", "DISPLAY_FIRST_LAST", "TEAM_ID", "TEAM_NAME"]].copy()


def fetch_season_game_logs() -> pd.DataFrame:
    """
    Holt die kompletten Game-Logs der laufenden Saison (Season-Start bis heute) in einem
    einzigen API-Call. Bewusst KEIN inkrementeller Abruf: LeagueGameLog liefert die ganze
    Liga in einem Request unabhaengig von der Zeitspanne, daher ist ein taeglicher Voll-
    Neuaufbau genauso teuer wie ein inkrementeller Abruf, aber robuster (kein persistenter
    Zustand zwischen den taeglichen, zustandslosen GitHub-Action-Laeufen noetig).
    """
    date_from = config.SEASON_START_DATE.strftime("%Y-%m-%d")

    def _fetch():
        endpoint = LeagueGameLog(
            season=config.SEASON_API_FORMAT,
            league_id="00",
            season_type_all_star="Regular Season",
            date_from_nullable=date_from,
            player_or_team_abbreviation="P",
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        return endpoint.get_data_frames()[0]

    df = _call_with_retries(_fetch, description="LeagueGameLog")
    if df.empty:
        return df

    df = df.rename(columns={"PLAYER_ID": "Player_ID", "GAME_ID": "Game_ID"})
    df["Player_ID"] = pd.to_numeric(df["Player_ID"], errors="coerce")
    df = df.dropna(subset=["Player_ID"])
    df["Player_ID"] = df["Player_ID"].astype(int)
    return df


def fetch_player_position(player_id: int) -> str | None:
    """Rohposition eines einzelnen Spielers (z. B. 'Guard', 'Forward-Center'). Rate-limited."""
    try:
        info = CommonPlayerInfo(player_id=player_id, timeout=DEFAULT_TIMEOUT_SECONDS)
        df = info.common_player_info.get_data_frame()
        if df.empty:
            return None
        position = df["POSITION"].iloc[0]
        return position.strip() if position else None
    except Exception as exc:  # noqa: BLE001 - einzelne fehlgeschlagene Spieler duerfen den Lauf nicht abbrechen
        print(f"Warnung: Position fuer Player_ID {player_id} konnte nicht geladen werden: {exc}")
        return None
    finally:
        time.sleep(0.7)  # NBA-API ist streng bei Request-Raten (siehe altes fetch_positions.py)


def fetch_positions_for_new_players(player_ids: list[int]) -> dict[int, str]:
    """Holt Rohpositionen nur fuer Spieler, die noch keine hinterlegte Position haben."""
    positions: dict[int, str] = {}
    for player_id in player_ids:
        position = fetch_player_position(player_id)
        if position:
            positions[player_id] = position
    return positions
