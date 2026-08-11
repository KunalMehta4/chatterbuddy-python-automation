"""ChatterBuddy entry point.

Kept deliberately thin: load the environment, build the config, build the app,
run it. Anything more interesting than that belongs in the package.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from chatterbuddy.app import create_app
from chatterbuddy.config import PROJECT_ROOT, AppConfig
from chatterbuddy.errors import ChatterBuddyError

LOG_PATH = PROJECT_ROOT / "chatterbuddy.log"


def configure_logging() -> None:
    """Send unexpected tracebacks to a file, never to the user's terminal."""
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> int:
    load_dotenv(Path(PROJECT_ROOT) / ".env")
    configure_logging()

    try:
        config = AppConfig.from_env()
        app = create_app(config)
    except ChatterBuddyError as error:
        print(f"ChatterBuddy could not start: {error}")
        return 1

    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
