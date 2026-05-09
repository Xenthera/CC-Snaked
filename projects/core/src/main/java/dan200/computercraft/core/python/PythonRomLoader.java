// SPDX-FileCopyrightText: 2026 The CC: Tweaked Developers
//
// SPDX-License-Identifier: MPL-2.0

package dan200.computercraft.core.python;

import org.graalvm.polyglot.HostAccess;
import org.jspecify.annotations.Nullable;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

/**
 * Resolves Python ROM modules from the classpath so that {@code import cc.*} works under the
 * restricted {@link org.graalvm.polyglot.Context} used by {@link PythonMachine}.
 * <p>
 * The Python BIOS installs a {@code sys.meta_path} finder which delegates to this loader. We
 * intentionally restrict resolution to the {@code cc} package tree to keep the bridge surface
 * narrow: there is no other way for guest code to read host files through this object.
 */
public final class PythonRomLoader {
    /**
     * Top-level packages that this loader is allowed to serve.
     * <p>
     * Restricting to known namespaces prevents guest code from probing arbitrary classpath resources
     * via the import machinery.
     */
    private static final String CC_ROOT = "cc";
    private static final String ROM_ROOT = "rom";

    private static final String CC_RESOURCE_ROOT = "data/computercraft/python/rom/modules/main/";
    private static final String ROM_RESOURCE_ROOT = "data/computercraft/python/rom/";

    @HostAccess.Export
    public @Nullable String loadSource(String fullname) {
        var base = mapToResource(fullname);
        if (base == null) return null;
        var src = readResource(base + ".py");
        if (src != null) return src;
        return readResource(base + "/__init__.py");
    }

    @HostAccess.Export
    public boolean isPackage(String fullname) {
        if (fullname.equals(ROM_ROOT)) return true;
        var base = mapToResource(fullname);
        return base != null && readResource(base + "/__init__.py") != null;
    }

    private static @Nullable String mapToResource(String fullname) {
        if (fullname.equals(CC_ROOT) || fullname.startsWith(CC_ROOT + ".")) {
            return CC_RESOURCE_ROOT + fullname.replace('.', '/');
        }

        if (fullname.equals(ROM_ROOT)) {
            return ROM_RESOURCE_ROOT + "__init__";
        }

        if (fullname.startsWith(ROM_ROOT + ".")) {
            return ROM_RESOURCE_ROOT + fullname.substring(ROM_ROOT.length() + 1).replace('.', '/');
        }

        return null;
    }

    private static @Nullable String readResource(String path) {
        var loader = PythonRomLoader.class.getClassLoader();
        try (var stream = loader.getResourceAsStream(path)) {
            if (stream == null) return null;
            return new String(stream.readAllBytes(), StandardCharsets.UTF_8);
        } catch (IOException e) {
            return null;
        }
    }
}
