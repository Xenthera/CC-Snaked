"""ComputerCraft HTTP for Python (mirrors ``rom/apis/http/http.lua``).

Uses the host bridge (``cct.httpRequest``, …). Stdlib ``import http`` is rejected in
favour of ``import cc.http`` (same basename as GraalPy's HTTP package).
"""

from cc.expect import expect, field
from cc import os as ccos

_METHODS = frozenset({
    "GET", "POST", "HEAD", "OPTIONS", "PUT", "DELETE", "PATCH", "TRACE",
})


def _check_key(options, key, ty, optional=True):
    if not isinstance(options, dict):
        return
    value = options.get(key)
    actual = type(value).__name__ if value is not None else "nil"
    if value is None:
        if not optional:
            raise TypeError("bad field '%s' (%s expected, got nil)" % (key, ty))
        return
    if ty == "string" and not isinstance(value, str):
        raise TypeError("bad field '%s' (string expected, got %s)" % (key, actual))
    if ty == "table" and not isinstance(value, dict):
        raise TypeError("bad field '%s' (table expected, got %s)" % (key, actual))
    if ty == "number" and not (isinstance(value, (int, float)) and not isinstance(value, bool)):
        raise TypeError("bad field '%s' (number expected, got %s)" % (key, actual))
    if ty == "boolean" and not isinstance(value, bool):
        raise TypeError("bad field '%s' (boolean expected, got %s)" % (key, actual))


def check_request_options(options, body_required=None):
    """Validate options dict for ``get`` / ``post`` / ``request``."""
    if not isinstance(options, dict):
        raise TypeError("options must be a dict")
    field(options, "url", "string")
    if body_required is False:
        field(options, "body", "nil")
    elif body_required is True:
        field(options, "body", "string")
    else:
        _check_key(options, "body", "string", optional=True)
    _check_key(options, "headers", "table", optional=True)
    _check_key(options, "method", "string", optional=True)
    _check_key(options, "redirect", "boolean", optional=True)
    _check_key(options, "timeout", "number", optional=True)
    _check_key(options, "binary", "boolean", optional=True)
    m = options.get("method")
    if m is not None and m not in _METHODS:
        raise RuntimeError("Unsupported HTTP method")


def check_websocket_options(options):
    if not isinstance(options, dict):
        raise TypeError("options must be a dict")
    field(options, "url", "string")
    _check_key(options, "headers", "table", optional=True)
    _check_key(options, "timeout", "number", optional=True)


def _unpack_pair(result):
    """Normalize Java ``Object[]`` / sequence from ``cct.http*``."""
    if result is None:
        return False, "no result"
    try:
        seq = list(result)
    except TypeError:
        return False, "bad result"
    if len(seq) == 0:
        return False, "empty result"
    if bool(seq[0]):
        return True, None
    return False, seq[1] if len(seq) > 1 else "failed"


async def _wait_http(wait_url):
    while True:
        ev = await ccos.pull_event_raw()
        if not ev:
            continue
        name = ev[0]
        if name == "http_success" and len(ev) >= 3 and ev[1] == wait_url:
            return ev[2]
        if name == "http_failure" and len(ev) >= 3 and ev[1] == wait_url:
            err = ev[2]
            resp = ev[3] if len(ev) >= 4 else None
            return (None, err, resp)


async def _wrap_request(wait_url, *req_args):
    ok, err = _unpack_pair(cct.httpRequest(*req_args))
    if not ok:
        return None, err
    got = await _wait_http(wait_url)
    return got


async def get(url, headers=None, binary=None):
    """Synchronous GET (waits for ``http_success`` / ``http_failure``)."""
    if isinstance(url, dict):
        check_request_options(url, False)
        out = await _wrap_request(url["url"], url)
    else:
        expect(1, url, "string")
        expect(2, headers, "table", "nil")
        expect(3, binary, "boolean", "nil")
        bin_flag = False if binary is None else bool(binary)
        out = await _wrap_request(url, url, None, headers, bin_flag)
    if isinstance(out, tuple) and len(out) == 3:
        return out[0], out[1], out[2]
    return out


async def post(url, post_body, headers=None, binary=None):
    """Synchronous POST."""
    if isinstance(url, dict):
        check_request_options(url, True)
        out = await _wrap_request(url["url"], url)
    else:
        expect(1, url, "string")
        expect(2, post_body, "string")
        expect(3, headers, "table", "nil")
        expect(4, binary, "boolean", "nil")
        bin_flag = False if binary is None else bool(binary)
        out = await _wrap_request(url, url, post_body, headers, bin_flag)
    if isinstance(out, tuple) and len(out) == 3:
        return out[0], out[1], out[2]
    return out


async def request(url, post_body=None, headers=None, binary=False):
    """Queue an HTTP request (async); mirrors Lua ``http.request``."""
    actual_url = None
    if isinstance(url, dict):
        check_request_options(url)
        actual_url = url["url"]
        req_args = (url,)
    else:
        expect(1, url, "string")
        expect(2, post_body, "string", "nil")
        expect(3, headers, "table", "nil")
        expect(4, binary, "boolean", "nil")
        actual_url = url
        req_args = (url, post_body, headers, binary)

    ok, err = _unpack_pair(cct.httpRequest(*req_args))
    if not ok:
        ccos.queue_event("http_failure", actual_url, err)
    return ok, err


async def check_url(url):
    """Synchronous URL allowlist check (waits for ``http_check``)."""
    expect(1, url, "string")
    ok, err = _unpack_pair(cct.httpCheckURL(url))
    if not ok:
        return ok, err

    while True:
        ev = await ccos.pull_event_raw("http_check")
        if len(ev) >= 2 and ev[1] == url:
            if len(ev) >= 4:
                return ev[2], ev[3]
            return ev[2], None


def check_url_async(url):
    """Submit URL check (listen for ``http_check`` for the outcome)."""
    expect(1, url, "string")
    return _unpack_pair(cct.httpCheckURL(url))


async def websocket_async(url, headers=None):
    """Open a websocket asynchronously."""
    actual_url = None
    if isinstance(url, dict):
        check_websocket_options(url)
        actual_url = url["url"]
        req_args = (url,)
    else:
        expect(1, url, "string")
        expect(2, headers, "table", "nil")
        actual_url = url
        req_args = (url, headers)

    ok, err = _unpack_pair(cct.httpWebsocket(*req_args))
    if not ok:
        ccos.queue_event("websocket_failure", actual_url, err)
    return ok, err


async def websocket(url, headers=None):
    """Open a websocket and wait for success or failure."""
    actual_url = None
    if isinstance(url, dict):
        check_websocket_options(url)
        actual_url = url["url"]
        req_args = (url,)
    else:
        expect(1, url, "string")
        expect(2, headers, "table", "nil")
        actual_url = url
        req_args = (url, headers)

    ok, err = _unpack_pair(cct.httpWebsocket(*req_args))
    if not ok:
        return ok, err

    while True:
        ev = await ccos.pull_event_raw()
        if not ev:
            continue
        name = ev[0]
        if name == "websocket_success" and len(ev) >= 3 and ev[1] == actual_url:
            return ev[2]
        if name == "websocket_failure" and len(ev) >= 3 and ev[1] == actual_url:
            return False, ev[2]


# CamelCase aliases (Lua names)
checkURL = check_url
checkURLAsync = check_url_async
websocketAsync = websocket_async
