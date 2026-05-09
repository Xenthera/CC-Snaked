// SPDX-FileCopyrightText: 2026 The CC: Tweaked Developers
//
// SPDX-License-Identifier: MPL-2.0

package dan200.computercraft.core.python;

import org.graalvm.polyglot.Context;

import java.util.List;
import java.util.TreeSet;

/**
 * Host policy for which GraalPy stdlib top-level names are rejected in favour of {@code cc.*} ROM
 * modules with the same basename (e.g. stdlib {@code http} vs {@code cc.http}).
 * <p>
 * Graal Polyglot does not expose a per-module stdlib denylist for the embedded distribution;
 * enforcement is implemented in the Python bootstrap by wrapping {@code builtins.__import__} and
 * {@code importlib.import_module}. Rules defined here are the single source of truth for that
 * behaviour.
 * <p>
 * A determined guest can still replace those hooks or mutate {@code sys.meta_path}; this policy is
 * not a cryptographic sandbox. The primary trust boundary remains {@link PythonHostBridge} and
 * {@link Context} access flags ({@code allowIO}, {@code allowNativeAccess}, etc.).
 */
public final class PythonImportPolicy {
    /**
     * Stdlib top-level names that must not be imported; use the matching {@code cc} submodule (for
     * example {@code cc.http}) instead.
     * <p>
     * Do not add {@code os}: Python still requires the real stdlib {@code os} at runtime despite
     * {@code cc.os}.
     */
    public static final List<String> SHADOWED_STDLIB_ROOTS = List.of("http");

    private PythonImportPolicy() {
    }

    /**
     * Optional Graal engine / context options reserved for future use (e.g. custom stdlib layout).
     */
    public static void applyContextOptions(Context.Builder builder) {
        // Intentionally empty: keep hook-based enforcement until a VM-level option exists.
    }

    /**
     * Python source appended after ROM {@code sys.meta_path} setup: defines {@code _CCT_SHADOW_ROOTS}
     * and installs import wrappers derived from {@link #SHADOWED_STDLIB_ROOTS}.
     */
    public static String shadowImportEnforcementPython() {
        var sorted = new TreeSet<>(SHADOWED_STDLIB_ROOTS);
        var frozenset = new StringBuilder("_CCT_SHADOW_ROOTS = frozenset({");
        var first = true;
        for (String root : sorted) {
            if (!first) frozenset.append(", ");
            first = false;
            frozenset.append('"').append(escapePythonStringLiteral(root)).append('"');
        }
        frozenset.append("})\n");

        return frozenset + SHADOW_ENFORCEMENT_BODY;
    }

    private static String escapePythonStringLiteral(String s) {
        return s.replace("\\", "\\\\").replace("\"", "\\\"");
    }

    private static final String SHADOW_ENFORCEMENT_BODY = """

        import builtins as _cct_builtins
        import importlib as _cct_importlib

        _cct_orig_import = _cct_builtins.__import__
        def _cct_import(name, globals=None, locals=None, fromlist=(), level=0):
            if level == 0 and isinstance(name, str):
                _root = name.partition(".")[0]
                if _root in _CCT_SHADOW_ROOTS:
                    raise ImportError(
                        "ComputerCraft provides this API as 'cc.%s', not the stdlib package (got %r)"
                        % (_root, name)
                    )
            return _cct_orig_import(name, globals, locals, fromlist, level)
        _cct_builtins.__import__ = _cct_import

        _cct_orig_import_module = _cct_importlib.import_module
        def _cct_import_module(name, package=None):
            if isinstance(name, str):
                _root = name.partition(".")[0]
                if _root in _CCT_SHADOW_ROOTS:
                    raise ImportError(
                        "ComputerCraft provides this API as 'cc.%s', not the stdlib package (got %r)"
                        % (_root, name)
                    )
            return _cct_orig_import_module(name, package)
        _cct_importlib.import_module = _cct_import_module
        """;
}
