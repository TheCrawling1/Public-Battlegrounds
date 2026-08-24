"""Central logging configuration.

The game engine emits a large amount of diagnostic output during combat
resolution, event processing, and database migration. This is logged at DEBUG
level and is silent by default. Set the LOG_LEVEL environment variable
(DEBUG, INFO, WARNING, ERROR) to control verbosity.

Call configure_logging() once at application startup (done in create_app()).
Modules obtain a logger with `logging.getLogger(__name__)`.
"""

import logging
import os

_DEFAULT_LEVEL = "INFO"
_configured = False


def configure_logging(level=None):
    """Install a console handler on the root logger. Idempotent.

    Level resolution: explicit `level` arg → LOG_LEVEL env var → INFO.
    """
    global _configured

    if level is None:
        level = os.environ.get("LOG_LEVEL", _DEFAULT_LEVEL)
    level = str(level).upper()

    root = logging.getLogger()
    root.setLevel(level)

    if not _configured:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        root.addHandler(handler)
        _configured = True

    return root
