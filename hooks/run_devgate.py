"""Launch the devgate package by path, so hooks never import from the repo they run in."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from devgate.cli import main  # noqa: E402

sys.exit(main(sys.argv))
