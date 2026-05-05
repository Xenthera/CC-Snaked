// SPDX-FileCopyrightText: 2026 The CC: Tweaked Developers
//
// SPDX-License-Identifier: MPL-2.0

package dan200.computercraft.core.runtime;

import dan200.computercraft.api.filesystem.Mount;
import dan200.computercraft.core.computer.GlobalEnvironment;
import dan200.computercraft.core.lua.ILuaMachine;
import org.jspecify.annotations.Nullable;

import java.io.InputStream;

/**
 * Describes a language runtime that a computer can boot into.
 * <p>
 * A runtime bundles together the {@linkplain ILuaMachine.Factory machine factory} that executes scripts and the
 * resources required to bootstrap that machine: a ROM mount and a BIOS file. This allows the computer execution
 * pipeline to be language-agnostic, while leaving the choice of language (and its boot resources) to the runtime
 * registration site.
 * <p>
 * The returned {@link Mount} and {@link InputStream} are resolved lazily through {@link GlobalEnvironment}, so that the
 * same {@link LanguageRuntime} instance can be reused across multiple computers and environments.
 *
 * @param id             A stable identifier for the runtime (for example {@code "lua"}).
 * @param resourceDomain The domain (mod id) under which {@link #romPath} and {@link #biosPath} are looked up via
 *                       {@link GlobalEnvironment#createResourceMount(String, String)} and
 *                       {@link GlobalEnvironment#createResourceFile(String, String)}.
 * @param romPath        The sub-path under {@link #resourceDomain} containing the ROM mount for this runtime.
 * @param biosPath       The sub-path under {@link #resourceDomain} pointing at the BIOS file for this runtime.
 * @param machineFactory The factory used to create a fresh {@link ILuaMachine} for each computer boot.
 * @see LanguageRuntimes
 */
public record LanguageRuntime(
    String id,
    String resourceDomain,
    String romPath,
    String biosPath,
    ILuaMachine.Factory machineFactory
) {
    /**
     * Resolve this runtime's ROM mount in a given environment.
     *
     * @param environment The global environment to resolve resources against.
     * @return The ROM mount, or {@code null} if it could not be found.
     */
    public @Nullable Mount mountRom(GlobalEnvironment environment) {
        return environment.createResourceMount(resourceDomain, romPath);
    }

    /**
     * Open this runtime's BIOS resource in a given environment.
     * <p>
     * The caller is responsible for closing the returned stream.
     *
     * @param environment The global environment to resolve resources against.
     * @return An open input stream for the BIOS, or {@code null} if it could not be found.
     */
    public @Nullable InputStream openBios(GlobalEnvironment environment) {
        return environment.createResourceFile(resourceDomain, biosPath);
    }
}
