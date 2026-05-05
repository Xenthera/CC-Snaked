// SPDX-FileCopyrightText: 2026 The CC: Tweaked Developers
//
// SPDX-License-Identifier: MPL-2.0

package dan200.computercraft.core.runtime;

import dan200.computercraft.core.lua.CobaltLuaMachine;
import dan200.computercraft.core.lua.ILuaMachine;

/**
 * Built-in {@link LanguageRuntime} definitions and helpers.
 * <p>
 * The Lua entry preserves the original boot resources used since ComputerCraft introduced its Cobalt-backed runtime:
 * the {@code computercraft:lua/rom} resource mount and the {@code computercraft:lua/bios.lua} BIOS file.
 *
 * @see LanguageRuntime
 */
public final class LanguageRuntimes {
    /**
     * The {@link LanguageRuntime#id() id} used for the built-in Lua runtime.
     */
    public static final String LUA_ID = "lua";

    /**
     * The resource domain (mod id) used for the built-in Lua runtime's ROM and BIOS.
     */
    public static final String LUA_RESOURCE_DOMAIN = "computercraft";

    /**
     * The resource sub-path used for the built-in Lua runtime's ROM mount.
     */
    public static final String LUA_ROM_PATH = "lua/rom";

    /**
     * The resource sub-path used for the built-in Lua runtime's BIOS file.
     */
    public static final String LUA_BIOS_PATH = "lua/bios.lua";

    /**
     * The {@link LanguageRuntime#id() id} used for the experimental Python runtime.
     */
    public static final String PYTHON_ID = "python";

    /**
     * The resource sub-path used for the experimental Python runtime's ROM mount.
     */
    public static final String PYTHON_ROM_PATH = "python/rom";

    /**
     * The resource sub-path used for the experimental Python runtime's BIOS file.
     */
    public static final String PYTHON_BIOS_PATH = "python/bios.py";

    private LanguageRuntimes() {
    }

    /**
     * Create a {@link LanguageRuntime} for Lua, backed by a given {@link ILuaMachine.Factory}.
     *
     * @param factory The factory that will create the underlying {@link ILuaMachine}. The default in production is
     *                {@link CobaltLuaMachine}.
     * @return A {@link LanguageRuntime} pointing at the standard Lua ROM/BIOS resources.
     */
    public static LanguageRuntime lua(ILuaMachine.Factory factory) {
        return new LanguageRuntime(LUA_ID, LUA_RESOURCE_DOMAIN, LUA_ROM_PATH, LUA_BIOS_PATH, factory);
    }

    /**
     * The default Lua runtime, backed by {@link CobaltLuaMachine}.
     *
     * @return A {@link LanguageRuntime} pointing at the standard Lua ROM/BIOS resources, using the bundled Cobalt
     * machine factory.
     */
    public static LanguageRuntime defaultLua() {
        return lua(CobaltLuaMachine::new);
    }

    /**
     * Create a {@link LanguageRuntime} for Python, backed by a given {@link ILuaMachine.Factory}.
     *
     * @param factory The factory that will create the underlying {@link ILuaMachine}.
     * @return A {@link LanguageRuntime} pointing at the experimental Python ROM/BIOS resources.
     */
    public static LanguageRuntime python(ILuaMachine.Factory factory) {
        return new LanguageRuntime(PYTHON_ID, LUA_RESOURCE_DOMAIN, PYTHON_ROM_PATH, PYTHON_BIOS_PATH, factory);
    }
}
