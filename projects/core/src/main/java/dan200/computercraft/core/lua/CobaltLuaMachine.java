// Copyright Daniel Ratcliffe, 2011-2022. Do not distribute without permission.
//
// SPDX-License-Identifier: LicenseRef-CCPL

package dan200.computercraft.core.lua;

import dan200.computercraft.api.lua.ILuaAPI;
import dan200.computercraft.api.lua.ILuaContext;
import dan200.computercraft.core.CoreConfig;
import dan200.computercraft.core.Logging;
import dan200.computercraft.core.computer.TimeoutState;
import dan200.computercraft.core.lua.errorinfo.ErrorInfoLib;
import dan200.computercraft.core.methods.LuaMethod;
import dan200.computercraft.core.methods.MethodSupplier;
import dan200.computercraft.core.util.Nullability;
import dan200.computercraft.core.util.SanitisedError;
import org.jspecify.annotations.Nullable;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.squiddev.cobalt.*;
import org.squiddev.cobalt.compiler.CompileException;
import org.squiddev.cobalt.compiler.LoadState;
import org.squiddev.cobalt.interrupt.InterruptAction;
import org.squiddev.cobalt.lib.Bit32Lib;
import org.squiddev.cobalt.lib.CoreLibraries;

import java.io.InputStream;
import java.io.Serial;
import java.util.*;

public class CobaltLuaMachine implements ILuaMachine {
    private static final Logger LOG = LoggerFactory.getLogger(CobaltLuaMachine.class);

    private final TimeoutState timeout;
    private final Runnable timeoutListener = this::updateTimeout;
    private final CobaltScriptInterop interop;

    private final LuaState state;
    private final LuaThread mainRoutine;

    private volatile boolean isDisposed = false;
    private boolean thrownSoftAbort;

    private @Nullable String eventFilter = null;

    public CobaltLuaMachine(MachineEnvironment environment, InputStream bios) throws MachineException {
        timeout = environment.timeout();
        interop = new CobaltScriptInterop(environment.context(), environment.luaMethods());

        // Create an environment to run in
        var state = this.state = LuaState.builder()
            .interruptHandler(() -> {
                if (timeout.isHardAborted() || isDisposed) throw new HardAbortError();
                if (timeout.isSoftAborted() && !thrownSoftAbort) {
                    thrownSoftAbort = true;
                    throw new LuaError(TimeoutState.ABORT_MESSAGE);
                }

                return timeout.isPaused() ? InterruptAction.SUSPEND : InterruptAction.CONTINUE;
            })
            .errorReporter((e, msg) -> {
                if (LOG.isErrorEnabled(Logging.VM_ERROR)) {
                    LOG.error(Logging.VM_ERROR, "Error occurred in the Lua runtime. Computer will continue to execute:\n{}", msg.get(), e);
                }
            })
            .build();

        // Set up our global table.
        try {
            var globals = state.globals();
            CoreLibraries.debugGlobals(state);
            Bit32Lib.add(state);
            ErrorInfoLib.add(state);
            globals.rawset("_HOST", ValueFactory.valueOf(environment.hostString()));
            globals.rawset("_CC_DEFAULT_SETTINGS", ValueFactory.valueOf(CoreConfig.defaultComputerSettings));

            // Add default APIs
            for (var api : environment.apis()) addAPI(state, globals, api);

            // And load the BIOS
            var value = LoadState.load(state, bios, "@bios.lua", globals);
            mainRoutine = new LuaThread(state, value);
        } catch (LuaError | CompileException e) {
            throw new MachineException(Nullability.assertNonNull(e.getMessage()));
        }

        timeout.addListener(timeoutListener);
    }

    private void addAPI(LuaState state, LuaTable globals, ILuaAPI api) throws LuaError {
        // Add the methods of an API to the global table
        var table = new LuaTable();
        if (!interop.makeLuaObject(api, table)) LOG.warn("API {} does not provide any methods", api);

        var names = api.getNames();
        for (var name : names) globals.rawset(name, table);

        var moduleName = api.getModuleName();
        if (moduleName != null) state.registry().getSubTable(Constants.LOADED).rawset(moduleName, table);
    }

    private void updateTimeout() {
        if (isDisposed) return;
        if (!timeout.isSoftAborted()) thrownSoftAbort = false;
        if (timeout.isSoftAborted() || timeout.isPaused()) state.interrupt();
    }

    @Override
    public MachineResult handleEvent(@Nullable String eventName, @Nullable Object @Nullable [] arguments) {
        if (isDisposed) throw new IllegalStateException("Machine has been closed");

        if (eventFilter != null && eventName != null && !eventName.equals(eventFilter) && !eventName.equals("terminate")) {
            return MachineResult.OK;
        }

        try {
            var resumeArgs = eventName == null ? Constants.NONE : ValueFactory.varargsOf(ValueFactory.valueOf(eventName), interop.toValues(arguments));

            // Resume the current thread, or the main one when first starting off.
            var thread = state.getCurrentThread();
            if (thread == null || thread == state.getMainThread()) thread = mainRoutine;

            var results = LuaThread.run(thread, resumeArgs);
            if (timeout.isHardAborted()) throw new HardAbortError();
            if (results == null) return MachineResult.PAUSE;

            var filter = results.first();
            eventFilter = filter.isString() ? filter.toString() : null;

            if (!mainRoutine.isAlive()) {
                close();
                return MachineResult.GENERIC_ERROR;
            } else {
                return MachineResult.OK;
            }
        } catch (HardAbortError e) {
            close();
            return MachineResult.TIMEOUT;
        } catch (LuaError e) {
            close();
            LOG.warn("Top level coroutine errored: {}", new SanitisedError(e));
            return MachineResult.error(e);
        }
    }

    @Override
    public void printExecutionState(StringBuilder out) {
    }

    @Override
    public void close() {
        isDisposed = true;
        state.interrupt();
        timeout.removeListener(timeoutListener);
    }

    static @Nullable Object toObject(LuaValue value, @Nullable IdentityHashMap<LuaValue, Object> objects) {
        return CobaltScriptInterop.toObject(value, objects);
    }

    private static final class HardAbortError extends Error {
        @Serial
        private static final long serialVersionUID = 7954092008586367501L;

        private HardAbortError() {
            super("Hard Abort");
        }
    }
}
