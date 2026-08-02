"""
Datenabruf ueber nba_api. Nutzt bewusst nur Endpunkte, die im alten fantasy_nba-Projekt
bereits produktiv liefen (load_data.py, update_nba_game_logs.py, fetch_positions.py) --
keine neuen, ungetesteten Endpunkte, damit die Pipeline beim ersten echten Lauf verlaesslich ist.
"""
import time

import pandas as pd
from nba_api.stats.endpoints import CommonAllPlayers, CommonPlayerInfo, LeagueGameLog

from . import config


def fetch_all_players() -> pd.DataFrame:
    """Aktuelle Saison-Roster-Liste: PERSON_ID, DISPLAY_FIRST_LAST, TEAM_ID, TEAM_NAME."""
    result = CommonAllPlayers(is_only_current_season=1)
    df = result.get_data_frames()[0]
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
    endpoint = LeagueGameLog(
        season=config.SEASON_API_FORMAT,
        league_id="00",
        season_type_all_star="Regular Season",
        date_from_nullable=date_from,
        player_or_team_abbreviation="P",
    )
    df = endpoint.get_data_frames()[0]
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
        info = CommonPlayerInfo(player_id=player_id, timeout=30)
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
