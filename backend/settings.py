import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.getenv("SIMFORGE_DATA_DIR", str(ROOT / "data"))).resolve()
PRODUCTION = os.getenv("SIMFORGE_ENV", "development") == "production"
MAX_POPULATION = 5000
MAX_HORIZON = 120
