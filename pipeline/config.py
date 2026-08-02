"""Zentrale Konstanten fuer die Rating-Pipeline. Kein Django/Dateisystem-Zustand."""
import os
from datetime import datetime

SEASON_API_FORMAT = "2025-26"  # Format, das nba_api erwartet
SEASON_LABEL = "2025-2026"     # Fuer die 'season'-Spalte in Supabase
SEASON_START_DATE = datetime(2025, 10, 21)

# NBA TEAM_ID -> Kuerzel. Wird fuer die Verfuegbarkeits-Gewichtung gebraucht
# (Spiele des Spielers vs. Spiele seines Teams), siehe ratings_engine.py.
TEAM_ID_TO_ABBR = {
    1610612737: "ATL", 1610612738: "BOS", 1610612739: "CLE", 1610612740: "NOP",
    1610612741: "CHI", 1610612742: "DAL", 1610612743: "DEN", 1610612744: "GSW",
    1610612745: "HOU", 1610612746: "LAC", 1610612747: "LAL", 1610612748: "MIA",
    1610612749: "MIL", 1610612750: "MIN", 1610612751: "BKN", 1610612752: "NYK",
    1610612753: "ORL", 1610612754: "IND", 1610612755: "PHI", 1610612756: "PHX",
    1610612757: "POR", 1610612758: "SAC", 1610612759: "SAS", 1610612760: "OKC",
    1610612761: "TOR", 1610612762: "UTA", 1610612763: "MEM", 1610612764: "WAS",
    1610612765: "DET", 1610612766: "CHA",
}

CATEGORIES = ["FGN", "FTN", "PTS", "FG3M", "REB", "BLK", "STL", "AST", "TOV"]
RATING_COLUMNS = [f"{c}_RT" for c in CATEGORIES]

# Mapping NBA-Rohposition (aus CommonPlayerInfo) -> Fantasy-Slots. Siehe product-spec.md 2.6.
NBA_TO_FANTASY_POSITIONS = {
    "Guard": ["PG", "SG"],
    "Forward-Guard": ["SG", "SF"],
    "Guard-Forward": ["SG", "SF"],
    "Forward": ["SF", "PF"],
    "Center-Forward": ["PF", "C"],
    "Forward-Center": ["PF", "C"],
    "Center": ["C"],
}


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


SUPABASE_URL_ENV = "SUPABASE_URL"
SUPABASE_SERVICE_ROLE_KEY_ENV = "SUPABASE_SERVICE_ROLE_KEY"
