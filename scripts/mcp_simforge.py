"""Launch the SimForge MCP server over stdio from any working directory."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.mcp_server import main  # noqa: E402

if __name__ == "__main__":
    main()
