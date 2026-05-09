"""Completion helpers for shell programs (Python port of ``cc.shell.completion``).

Mirrors the Lua module: each function takes ``(shell, text, previous, ...)``
and returns a list of suffix strings (or ``None``). ``build`` composes a
positional schema describing how to complete each argument of a program.

Path completion delegates to :func:`cc.fs.complete` with the same options as
Lua (including ``shell.autocomplete_hidden`` via :mod:`cc.settings`).
"""

from cc import completion as _completion
from cc import fs as _fs
from cc import settings as _settings


def _autocomplete_hidden() -> bool:
    v = _settings.get("shell.autocomplete_hidden")
    return False if v is None else bool(v)


def file(shell, text, previous=None, add_space=False):
    return _fs.complete(
        text,
        shell.dir(),
        {
            "include_files": True,
            "include_dirs": False,
            "include_hidden": _autocomplete_hidden(),
        },
    )


def dir(shell, text, previous=None):
    return _fs.complete(
        text,
        shell.dir(),
        {
            "include_files": False,
            "include_dirs": True,
            "include_hidden": _autocomplete_hidden(),
        },
    )


def dir_or_file(shell, text, previous=None, add_space=False):
    results = _fs.complete(
        text,
        shell.dir(),
        {
            "include_files": True,
            "include_dirs": True,
            "include_hidden": _autocomplete_hidden(),
        },
    )
    if add_space:
        out = []
        for result in results:
            if not result.endswith("/"):
                out.append(result + " ")
            else:
                out.append(result)
        return out
    return results


dirOrFile = dir_or_file


def choice(shell, text, previous, choices, add_space=False):
    return _completion.choice(text, choices, add_space=add_space)


def program(shell, text, previous=None):
    if hasattr(shell, "complete_program"):
        return shell.complete_program(text)
    if hasattr(shell, "completeProgram"):
        return shell.completeProgram(text)
    return []


def program_with_args(shell, text, previous=None, starting=2):
    """Same behavior as Lua ``programWithArgs`` (``cc.shell.completion``)."""
    if previous is None:
        previous = []
    if len(previous) + 1 == starting:
        t_completion_info = shell.get_completion_info()
        text_str = str(text)
        resolved_text = shell.resolve_program(text_str) if text_str else None
        if (
            text_str
            and not text_str.endswith("/")
            and resolved_text
            and t_completion_info.get(resolved_text)
        ):
            return [" "]
        results = shell.complete_program(text_str)
        out = []
        for s_result in results:
            combined = shell.resolve_program(text_str + s_result)
            if (
                combined
                and not s_result.endswith("/")
                and t_completion_info.get(combined)
            ):
                out.append(s_result + " ")
            else:
                out.append(s_result)
        return out

    if starting < 1 or starting > len(previous):
        return None
    program = previous[starting - 1]
    resolved = shell.resolve_program(program)
    if not resolved:
        return None
    entry = shell.get_completion_info().get(resolved)
    if not entry:
        return None
    fn = entry.get("fnComplete")
    if fn is None:
        return None
    arg_index = len(previous) - starting + 1
    prev_tail = previous[starting - 1 :]
    try:
        return fn(shell, arg_index, text, prev_tail)
    except Exception:
        return None


programWithArgs = program_with_args


def peripheral(shell, text, previous=None, add_space=False):
    # Peripheral side completion is not wired yet; return nothing rather than crash.
    return []


def side(shell, text, previous=None, add_space=False):
    sides = ["top", "bottom", "left", "right", "front", "back"]
    return _completion.choice(text, sides, add_space=add_space)


def setting(shell, text, previous=None, add_space=False):
    # Settings completion is not wired yet.
    return []


def command(shell, text, previous=None, add_space=False):
    # Minecraft-command completion is not wired yet.
    return []


def help(shell, text, previous=None, add_space=False):
    # Help-topic completion is not wired yet (depends on the help API).
    return []


def build(*specs):
    """Build a completion function from a list of per-argument specs.

    Each spec is either a callable (used as-is) or a list/tuple ``(fn, *args)``
    where ``fn`` is one of the helpers above. ``many=True`` may be passed in
    a dict-like spec to repeat the last spec for trailing arguments.
    """
    normalised = []
    many = False
    for spec in specs:
        if isinstance(spec, dict):
            many = bool(spec.get("many"))
            continue
        if spec is None:
            normalised.append(None)
            continue
        if callable(spec):
            normalised.append((spec, ()))
            continue
        if isinstance(spec, (list, tuple)) and spec:
            fn = spec[0]
            extra = tuple(spec[1:])
            normalised.append((fn, extra))
            continue
        normalised.append(None)

    def _complete(shell, index, text, previous):
        if 0 <= index - 1 < len(normalised):
            entry = normalised[index - 1]
        elif many and normalised:
            entry = normalised[-1]
        else:
            return None
        if entry is None:
            return None
        fn, extra = entry
        try:
            return fn(shell, text, previous, *extra)
        except TypeError:
            try:
                return fn(shell, text, previous)
            except Exception:
                return None
        except Exception:
            return None

    return _complete
