"""NBA-Rohposition -> Fantasy-Slots. Siehe product-spec.md 2.6."""
from . import config


def nba_position_to_fantasy(nba_position: str | None) -> list[str]:
    if not nba_position:
        return []
    return config.NBA_TO_FANTASY_POSITIONS.get(nba_position.strip(), [])
