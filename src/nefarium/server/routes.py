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

from logging import getLogger
from urllib.parse import urlparse

from aiohttp.web import RouteTableDef
from aiohttp.web_exceptions import (
    HTTPBadRequest,
    HTTPNotFound,
    HTTPFound,
    HTTPInternalServerError,
    HTTPException,
)
from aiohttp.web_request import Request
from aiohttp.web_response import Response
from aiohttp_session import get_session
from authcaptureproxy import AuthCaptureProxy
from bson import ObjectId
from bson.errors import InvalidId
from yarl import URL

from .proxy import create_proxy
from ..helpers import truthy_string, LimitedSizeDict, IS_DEBUG
from ..types import Flow, Session

routes = RouteTableDef()

logger = getLogger(__name__)


@routes.get("/flows/{flow_id}")
async def initialize_flow(request: Request) -> Response:
    aiohttp_session = await get_session(request)

    flow_id: str = request.match_info["flow_id"]  # hex

    try:
        object_id = ObjectId(flow_id)  # raises if invalid
    except InvalidId as e:
        raise HTTPBadRequest(reason="Unparseable Flow ID") from e

    flow = await request.app["db"]["flows"].find_one({"_id": object_id})

    if flow is None:
        raise HTTPNotFound(reason="Flow ID not found")

    redirect_url: str | None = truthy_string(
        request.query.get("redirect_url", "")
    ) or truthy_string(request.query.get("redirect_uri", ""))

    if redirect_url is not None:
        try:
            parsed = urlparse(redirect_url.lower().strip())
        except ValueError as e:
            raise HTTPBadRequest(reason="Unparseable redirect URL") from e
        if not URL(redirect_url).is_absolute():
            raise HTTPBadRequest(reason="Redirect URL must be absolute")
        elif parsed.netloc not in flow["redirect_url_domains"]:
            # TODO: check for wildcards
            raise HTTPBadRequest(reason="Redirect URL not allowed")
    elif not IS_DEBUG:
        raise HTTPBadRequest(reason="Missing redirect URL")
    else:
        redirect_url = "http://localhost/"
        parsed = urlparse(redirect_url)

    new_session = await request.app["db"]["sessions"].insert_one(
        {
            "flow_id": flow["_id"],
            "state": "pending",
            "auth_data": None,
            "redirect_url": parsed.geturl(),
            "ip_address": request.remote,
        }
    )

    new_session_id = new_session.inserted_id

    return HTTPFound(
        location=f"/flows/{flow_id}/session/{new_session_id}/auth"
    )  # auth time


async def handle_auth(request: Request) -> Response:
    aiohttp_session = await get_session(request)

    flow_id: str | None = request.match_info.get("flow_id")  # hex

    if flow_id is None:
        if "flow_id" in aiohttp_session:
            flow_id = aiohttp_session["flow_id"]
        else:
            raise HTTPBadRequest(reason="Missing flow ID")

    try:
        object_id = ObjectId(flow_id)  # raises if invalid
    except InvalidId as e:
        raise HTTPBadRequest(reason="Unparseable Flow ID") from e

    flow: Flow | None = await request.app["db"]["flows"].find_one({"_id": object_id})

    if flow is None:
        raise HTTPNotFound(reason="Flow ID not found")
    else:
        if aiohttp_session.get("flow_id") != flow_id:
            aiohttp_session["flow_id"] = flow_id

    session_id: str | None = request.match_info.get("session_id")  # hex

    if session_id is None:
        if "session_id" in aiohttp_session:
            session_id = aiohttp_session["session_id"]
        else:
            raise HTTPBadRequest(reason="Missing session ID")

    try:
        object_id = ObjectId(session_id)  # raises if invalid
    except InvalidId as e:
        raise HTTPBadRequest(reason="Unparseable Session ID") from e

    session: Session | None = await request.app["db"]["sessions"].find_one(
        {"_id": object_id}
    )

    if session is None:
        raise HTTPNotFound(reason="Session ID not found")
    else:
        if aiohttp_session.get("session_id") != session_id:
            aiohttp_session["session_id"] = session_id

    if session["flow_id"] != flow["_id"]:
        raise HTTPBadRequest(reason="Session ID does not match Flow ID")
    elif session["state"] != "pending":
        raise HTTPBadRequest(reason="Session already completed")

    # get AuthCaptureProxy
    proxies: LimitedSizeDict = request.app["auth_capture_proxies"]

    proxy: AuthCaptureProxy
    if session_id not in proxies:
        proxy = create_proxy(
            flow, session, request.url, request.app.loop, request.app["db"]["sessions"]
        )
        proxies[session_id] = proxy
    else:
        proxy = proxies[session_id]

    try:
        return await proxy.all_handler(request)
    except Exception as e:
        logger.exception("Error in proxy handler!")
        raise HTTPInternalServerError(reason="Failed to pass login data back!") from e


routes.view("/flows/{flow_id}/session/{session_id}/auth")(handle_auth)
routes.view("/flows/{flow_id}/session/{session_id}/auth/{tail:.*}")(
    handle_auth
)  # other routes go through proxy


@routes.view("/{tail:.*}")
async def handle_root(request: Request) -> Response:
    """
    handle bad routes
    :param request:
    :return:
    """
    aiohttp_session = await get_session(request)

    if "flow_id" in aiohttp_session and "session_id" in aiohttp_session:
        try:
            return await handle_auth(request)
        except HTTPException as e:
            raise HTTPInternalServerError(reason="Failed to handle catch-all!") from e
    else:
        raise HTTPNotFound()


__all__ = ("routes",)