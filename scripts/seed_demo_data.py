"""Add the demo book to the local watchlist."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings
from app.db.session import init_db
from app.services.portfolio_service import PortfolioService


def main() -> None:
    settings = get_settings()
    init_db(settings)
    service = PortfolioService(settings)
    saved = service.save_watch("demo", "Demo book")
    print(f"Watchlist has {saved.address} ({saved.label}). Open the app and load it, or call GET /portfolio/demo.")


if __name__ == "__main__":
    main()
