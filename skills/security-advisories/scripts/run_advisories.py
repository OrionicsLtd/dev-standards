"""Launch the advisories package by path, so it never imports from the repository being scanned."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from advisories.cli import main  # noqa: E402

sys.exit(main(sys.argv[1:]))
