"""
Einstiegspunkt der taeglichen Pipeline. Laeuft als GitHub Action (.github/workflows/daily-pipeline.yml),
kann aber genauso lokal ausgefuehrt werden: `python -m pipeline.main` (mit gesetzten Env-Vars,
siehe docs/environment.md und pipeline/.env.example).

Ablauf: Spielerliste holen -> neue Spieler-Positionen nachladen -> Saison-Game-Logs holen ->
Ratings berechnen -> alles nach Supabase schreiben -> Pipeline-Lauf protokollieren.
"""
import sys

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


def run() -> None:
    client = supabase_io.get_client()

    print("Lade Spielerliste...")
    all_players_df = nba_data.fetch_all_players()

    existing_rows = client.table("players").select("player_id, fantasy_positions").execute().data or []
    existing_positions = {row["player_id"]: row["fantasy_positions"] for row in existing_rows}

    player_records = _build_player_records(all_players_df, existing_positions)
    supabase_io.upsert_players(client, player_records)
    print(f"{len(player_records)} Spieler in Supabase aktualisiert.")

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

    ratings_df = ratings_engine.compute_ratings(game_logs, all_players_df)
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
