"""
Einstiegspunkt der taeglichen Pipeline. Laeuft als GitHub Action (.github/workflows/daily-pipeline.yml),
kann aber genauso lokal ausgefuehrt werden: `python -m pipeline.main` (mit gesetzten Env-Vars,
siehe docs/environment.md und pipeline/.env.example).

Ablauf: Saison-Game-Logs holen -> Spielerliste + neue Positionen nachladen (Fallback auf Supabase,
falls das fehlschlaegt) -> Ratings berechnen -> alles nach Supabase schreiben -> Lauf protokollieren.
"""
import sys

import pandas as pd
from dotenv import load_dotenv

from . import config, nba_data, positions, ratings_engine, supabase_io

load_dotenv()  # no-op, falls keine .env-Datei existiert (z. B. in GitHub Actions)


def _build_player_records(all_players_df, existing_positions: dict[int, list[str]]) -> list[dict]:
    player_ids = [int(pid) for pid in all_players_df["PERSON_ID"]]
    new_player_ids = [pid for pid in player_ids if pid not in existing_positions]

    print(f"{len(player_ids)} Spieler insgesamt, {len(new_player_ids)} davon neu (Positionsabruf noetig).")
    fetched_raw_positions = nba_data.fetch_positions_for_new_players(new_player_ids)

    records = []
    for _, row in all_players_df.iterrows():
        player_id = int(row["PERSON_ID"])
        if player_id in existing_positions:
            fantasy_positions = existing_positions[player_id]
        else:
            raw_position = fetched_raw_positions.get(player_id)
            fantasy_positions = positions.nba_position_to_fantasy(raw_position)

        team_id = int(row["TEAM_ID"]) if row["TEAM_ID"] else None
        records.append({
            "player_id": player_id,
            "name": row["DISPLAY_FIRST_LAST"],
            "team_id": team_id,
            "team_abbr": config.TEAM_ID_TO_ABBR.get(team_id),
            "fantasy_positions": fantasy_positions,
        })
    return records


def _load_fallback_players_from_supabase(client) -> pd.DataFrame:
    """Wird genutzt, wenn CommonAllPlayers fehlschlaegt: nutzt die zuletzt erfolgreich
    gespeicherte Spielerliste aus Supabase, damit die Rating-Berechnung (die nur
    PERSON_ID/TEAM_ID fuer die Verfuegbarkeits-Gewichtung braucht) trotzdem weiterlaufen kann."""
    rows = client.table("players").select("player_id, team_id").execute().data or []
    if not rows:
        return pd.DataFrame(columns=["PERSON_ID", "TEAM_ID"])
    return pd.DataFrame(rows).rename(columns={"player_id": "PERSON_ID", "team_id": "TEAM_ID"})


def run() -> None:
    client = supabase_io.get_client()

    # Game-Logs zuerst: das ist der Teil, der in v1s produktivem taeglichen GitHub-Action-Lauf
    # (update_nba_game_logs.py) bereits nachweislich funktioniert hat. CommonAllPlayers (unten)
    # ist ein anderer nba_api-Endpunkt mit unklarer Zuverlaessigkeit von GitHub-Actions-Runnern aus --
    # falls nur dieser fehlschlaegt, soll das die wichtigeren Ratings nicht mit zu Fall bringen.
    print("Lade Saison-Game-Logs...")
    game_logs = nba_data.fetch_season_game_logs()
    if game_logs.empty:
        # Sicherheitsnetz: leere Game-Logs mitten in der Saison sind ein API-Problem, kein legitimer
        # Zustand. sync_ratings() wuerde sonst ALLE bestehenden Ratings loeschen (current_ids waere
        # leer). Lieber abbrechen, als gute Daten zu zerstoeren.
        print("Warnung: Keine Game-Logs erhalten -- Ratings werden NICHT angefasst.")
        supabase_io.log_pipeline_run(
            client, season=config.SEASON_LABEL, games_ingested=0,
            status="partial", note="Keine Game-Logs von nba_api erhalten; Ratings-Sync uebersprungen.",
        )
        return

    games_ingested = int(game_logs["Game_ID"].nunique())
    print(f"{games_ingested} Spiele geladen, {len(game_logs)} Spieler-Spiel-Zeilen.")

    print("Lade Spielerliste...")
    try:
        all_players_df = nba_data.fetch_all_players()
    except Exception as exc:  # noqa: BLE001 - Spielerliste ist "nice to have", darf Ratings nicht blockieren
        print(f"Warnung: Spielerliste (CommonAllPlayers) konnte nicht geladen werden ({exc}). "
              f"Namen/Positionen werden diesen Lauf NICHT aktualisiert; Ratings laufen mit der "
              f"zuletzt gespeicherten Spielerliste aus Supabase weiter.")
        all_players_df = None

    if all_players_df is not None:
        existing_rows = client.table("players").select("player_id, fantasy_positions").execute().data or []
        existing_positions = {row["player_id"]: row["fantasy_positions"] for row in existing_rows}
        player_records = _build_player_records(all_players_df, existing_positions)
        supabase_io.upsert_players(client, player_records)
        print(f"{len(player_records)} Spieler in Supabase aktualisiert.")
        players_for_ratings = all_players_df
    else:
        players_for_ratings = _load_fallback_players_from_supabase(client)
        print(f"{len(players_for_ratings)} Spieler aus Supabase als Fallback geladen.")

    ratings_df = ratings_engine.compute_ratings(game_logs, players_for_ratings)
    ratings_df["season"] = config.SEASON_LABEL

    ratings_records = ratings_df.to_dict("records")
    supabase_io.sync_ratings(client, ratings_records)
    print(f"{len(ratings_records)} Ratings in Supabase aktualisiert.")

    supabase_io.log_pipeline_run(
        client,
        season=config.SEASON_LABEL,
        games_ingested=games_ingested,
        status="success",
    )
    print("Pipeline-Lauf erfolgreich abgeschlossen.")


def main() -> None:
    client = None
    try:
        run()
    except Exception as exc:  # noqa: BLE001 - Fehler muss den Actions-Lauf sichtbar rot markieren
        print(f"Pipeline-Lauf fehlgeschlagen: {exc}", file=sys.stderr)
        try:
            client = client or supabase_io.get_client()
            supabase_io.log_pipeline_run(
                client, season=config.SEASON_LABEL, games_ingested=0,
                status="failed", note=str(exc),
            )
        except Exception as log_exc:  # noqa: BLE001
            print(f"Konnte fehlgeschlagenen Lauf nicht protokollieren: {log_exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
