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

from logging import DEBUG, basicConfig, INFO
from os import environ

from aiohttp.web import run_app

from . import *


def main() -> None:
    debug: bool = "NEFARIUM_DEBUG" in environ

    basicConfig(level=DEBUG if debug else INFO)

    run_app(app_factory())


if __name__ == "__main__":
    main()
