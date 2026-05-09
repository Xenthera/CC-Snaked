"""Tiny wrapper that runs an :mod:`cc.internal.edit_runner` job in a tab.

``edit``'s Run menu calls :func:`cc.internal.edit_runner.submit_request` to
stash the buffer and then launches this program through ``multishell.launch``
with the returned token as ``argv[1]``.
"""

from cc.internal import edit_runner as _r


async def main(*args) -> None:
    if not args:
        return
    try:
        token = int(args[0])
    except (TypeError, ValueError):
        return
    request = _r.pop_request(token)
    if request is None:
        return
    title, path, contents = request
    await _r.run(title, path, contents)
