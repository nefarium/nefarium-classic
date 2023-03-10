# nefarium provides an API similar to OAuth for websites that do not support it
# Copyright (C) 2023  Parker Wahle
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
from __future__ import annotations

import sys
from logging import DEBUG, basicConfig, INFO, getLogger, StreamHandler, ERROR, Logger
from os import environ

from aiohttp.web import run_app
from dislog import DiscordWebhookHandler

from . import *
from .. import *

logger = getLogger(__name__)


def main() -> None:
    standard_handler = StreamHandler(sys.stdout)
    error_handler = StreamHandler(sys.stderr)

    standard_handler.addFilter(
        lambda record: record.levelno < ERROR
    )  # keep errors to stderr
    error_handler.setLevel(ERROR)

    basicConfig(
        format="%(asctime)s\t%(levelname)s\t%(name)s@%(threadName)s: %(message)s",
        level=DEBUG if IS_DEBUG else INFO,
        handlers=[standard_handler, error_handler],
        force=True,
    )

    if dislog_url := truthy_string(environ.get("NEFARIUM_DISCORD_WEBHOOK", "")):
        logger.info("Discord Webhook provided, enabling Discord logging.")

        handler = DiscordWebhookHandler(
            dislog_url,
            level=max(
                Logger.root.level, INFO
            ),  # DEBUG < INFO, higher is less selective and more severe
            run_async=True,
        )
        Logger.root.addHandler(handler)

    port = int(environ.get("NEFARIUM_PORT", "8080"))
    host = environ.get("NEFARIUM_HOST", "0.0.0.0")

    run_app(app_factory(), port=port, host=host)


if __name__ == "__main__":
    main()
