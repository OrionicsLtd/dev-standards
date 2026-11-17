"""Launch the context package by path, so hooks never import from the repo they run in."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from context.cli import main  # noqa: E402 - the path must be set before the import

sys.exit(main(sys.argv))
