"""
Reine Rating-Berechnung (keine Datei-/Netzwerk-I/O). Migriert und bereinigt aus dem alten
fantasy_nba/nba_project/fantasy_nba/{ratings,games_played,helpers}.py:
- helpers.normalize()          -> normalize()
- ratings.calc_fgn_ftn()       -> calc_fgn_ftn() (unveraendert)
- games_played.calculate_player_availability_score() -> compute_availability_scores()
- ratings.py Hauptskript       -> compute_ratings()

Bewusst NICHT migriert: Punt-Varianten (ADR 0002 -- werden vom Frontend zur Laufzeit
berechnet) und Wochen-Ratings (ADR 0003 -- zurueckgestellt).
"""
import pandas as pd

from . import config


def normalize(series: pd.Series) -> pd.Series:
    max_value = series.max()
    if max_value == 0:
        return series
    return series / max_value * 100


def calc_fgn_ftn(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["FGPM"] = df["FGM"] - (df["FGA"] - df["FGM"])
    df["FGN"] = df["FGPM"] - df["FGPM"].min()
    df["FTPM"] = df["FTM"] - (df["FTA"] - df["FTM"])
    df["FTN"] = df["FTPM"] - df["FTPM"].min()
    return df


def _extract_team_from_matchup(matchup) -> str | None:
    if pd.isna(matchup):
        return None
    parts = str(matchup).split()
    return parts[0] if parts else None


def _compute_team_game_counts(game_logs: pd.DataFrame) -> dict[str, int]:
    if game_logs.empty or "MATCHUP" not in game_logs.columns:
        return {}
    df = game_logs.copy()
    df["TEAM_ABBR"] = df["MATCHUP"].apply(_extract_team_from_matchup)
    return df.dropna(subset=["TEAM_ABBR"]).groupby("TEAM_ABBR")["Game_ID"].nunique().to_dict()


def compute_availability_scores(game_logs: pd.DataFrame, players_df: pd.DataFrame) -> dict[int, float]:
    """availability_score = Spiele des Spielers / Spiele seines Teams (aktuelle Saison)."""
    team_game_counts = _compute_team_game_counts(game_logs)
    player_team_abbr = players_df.set_index("PERSON_ID")["TEAM_ID"].map(config.TEAM_ID_TO_ABBR)
    player_games_played = game_logs.groupby("Player_ID")["Game_ID"].nunique()

    scores: dict[int, float] = {}
    for player_id, team_abbr in player_team_abbr.items():
        games_played = int(player_games_played.get(player_id, 0))
        team_games = team_game_counts.get(team_abbr, 0)
        scores[player_id] = (games_played / team_games) if team_games else 0.0
    return scores


def compute_ratings(game_logs: pd.DataFrame, players_df: pd.DataFrame) -> pd.DataFrame:
    """
    Gibt eine DataFrame mit einer Zeile pro Spieler zurueck, Spalten passend zu
    supabase/schema.sql::ratings (player_id, 9x *_rt, availability_score,
    total_rating, total_available_rating, combined_rating). Nur Spieler mit
    mindestens einem geloggten Spiel dieser Saison tauchen auf.
    """
    if game_logs.empty:
        return pd.DataFrame(columns=[
            "player_id", *[c.lower() + "_rt" for c in config.CATEGORIES],
            "availability_score", "total_rating", "total_available_rating", "combined_rating",
        ])

    numeric_cols = game_logs.select_dtypes(include="number").columns
    season_avg = game_logs.groupby("Player_ID", as_index=False)[numeric_cols].mean()
    season_avg = calc_fgn_ftn(season_avg)

    for cat in config.CATEGORIES:
        season_avg[f"{cat}_RT"] = normalize(season_avg[cat])
    season_avg["TOV_RT"] = season_avg["TOV_RT"] * -1 + 100

    availability_scores = compute_availability_scores(game_logs, players_df)
    season_avg["availability_score"] = season_avg["Player_ID"].map(availability_scores).fillna(0.0)

    season_avg["total_rating"] = normalize(season_avg[config.RATING_COLUMNS].sum(axis=1))
    season_avg["total_available_rating"] = normalize(
        season_avg["total_rating"] * season_avg["availability_score"]
    )
    season_avg["combined_rating"] = normalize(
        (season_avg["total_rating"] + season_avg["total_available_rating"]) / 2
    )

    rename_map = {"Player_ID": "player_id", **{f"{c}_RT": f"{c.lower()}_rt" for c in config.CATEGORIES}}
    columns = ["Player_ID", *config.RATING_COLUMNS,
               "availability_score", "total_rating", "total_available_rating", "combined_rating"]
    return season_avg[columns].rename(columns=rename_map)
