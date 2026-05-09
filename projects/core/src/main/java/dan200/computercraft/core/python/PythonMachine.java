// SPDX-FileCopyrightText: 2026 The CC: Tweaked Developers
//
// SPDX-License-Identifier: MPL-2.0

package dan200.computercraft.core.python;

import dan200.computercraft.core.Logging;
import dan200.computercraft.core.computer.TimeoutState;
import dan200.computercraft.core.lua.ILuaMachine;
import dan200.computercraft.core.lua.MachineEnvironment;
import dan200.computercraft.core.lua.MachineException;
import dan200.computercraft.core.lua.MachineResult;
import org.graalvm.polyglot.Context;
import org.graalvm.polyglot.EnvironmentAccess;
import org.graalvm.polyglot.HostAccess;
import org.graalvm.polyglot.PolyglotAccess;
import org.graalvm.polyglot.PolyglotException;
import org.graalvm.polyglot.Value;
import org.graalvm.polyglot.io.IOAccess;
import org.jspecify.annotations.Nullable;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * A minimal embedded Python runtime backed by GraalPy.
 * <p>
 * This initial implementation exists to validate boot, event resume, and the yield/filter protocol. It will be
 * expanded in later milestones to expose ComputerCraft APIs and enforce stronger sandboxing.
 */
public final class PythonMachine implements ILuaMachine {
    private static final Logger LOG = LoggerFactory.getLogger(PythonMachine.class);

    private static final String BOOTSTRAP = """
        import importlib.abc
        import importlib.machinery
        import sys

        class AwaitPullEvent:
            def __init__(self, filter):
                self.filter = filter

            def __await__(self):
                event = yield self.filter
                return event

        # Track whether we've primed each coroutine. Python requires the first
        # send() into a coroutine to be None, but the host may deliver an initial
        # event on first resume.
        try:
            import weakref
            __cct_started = weakref.WeakKeyDictionary()
        except Exception:
            __cct_started = {}

        def __cct_start(coro):
            __cct_started[coro] = True
            return coro.send(None)

        def __cct_resume(coro, event_name, *args):
            payload = (event_name, *args)
            try:
                if not __cct_started.get(coro, False):
                    __cct_started[coro] = True
                    coro.send(None)
                return coro.send(payload)
            except StopIteration as e:
                return ("__cct_done__", e.value)

        class _CctRomLoader(importlib.abc.Loader):
            # Import-machinery loader for ComputerCraft's Python ROM modules.
            # Source bytes come from the JVM via the host-bound ``__cct_rom`` object,
            # which only resolves names inside the allowlisted ``cc`` package tree.
            def __init__(self, source, is_package):
                self._source = source
                self._is_package = is_package

            def create_module(self, spec):
                return None

            def exec_module(self, module):
                if self._is_package:
                    module.__path__ = []
                # ``cct`` is a top-level binding installed by the host before BIOS execution.
                # We inject it as a module-level global so cc.* code can call host methods
                # directly without re-importing the bridge.
                module.__dict__["cct"] = cct
                code = compile(self._source, "<cct-rom:" + module.__name__ + ">", "exec")
                exec(code, module.__dict__)

        class _CctRomFinder(importlib.abc.MetaPathFinder):
            # NOTE: ``_cct_rom`` (single leading underscore) avoids Python's class-body name
            # mangling, which would otherwise rewrite ``__cct_rom`` to ``_CctRomFinder__cct_rom``.
            def find_spec(self, fullname, path, target=None):
                source = _cct_rom.loadSource(fullname)
                if source is None:
                    return None
                is_package = _cct_rom.isPackage(fullname)
                return importlib.machinery.ModuleSpec(
                    name=fullname,
                    loader=_CctRomLoader(source, is_package),
                    is_package=is_package,
                )

        # ROM (``cc``, ``rom``) before host/builtin importers.
        sys.meta_path.insert(0, _CctRomFinder())
        """;

    private final TimeoutState timeout;
    private final Runnable timeoutListener = this::onTimeoutChanged;

    private final Context context;
    private final Value bindings;
    private final Value startFn;
    private final Value resumeFn;

    private final Value coroutine;
    private volatile boolean disposed;
    private @Nullable String eventFilter;

    private final AtomicBoolean userInterruptRequested = new AtomicBoolean(false);

    public PythonMachine(MachineEnvironment environment, InputStream bios) throws IOException, MachineException {
        timeout = environment.timeout();

        context = Context.newBuilder("python")
            // Only methods explicitly marked with @HostAccess.Export are reachable from Python.
            .allowHostAccess(HostAccess.EXPLICIT)
            .allowIO(IOAccess.NONE)
            .allowNativeAccess(false)
            .allowCreateProcess(false)
            .allowEnvironmentAccess(EnvironmentAccess.NONE)
            .allowPolyglotAccess(PolyglotAccess.NONE)
            .build();
        bindings = context.getBindings("python");

        // The ROM loader and host bridge must be bound before BOOTSTRAP installs the meta-path
        // finder, since that finder closes over ``cct``/``__cct_rom`` lexically and the BIOS may
        // trigger ``cc.*`` imports immediately.
        bindings.putMember("_cct_rom", new PythonRomLoader());
        bindings.putMember("cct", new PythonHostBridge(environment.apis(), timeout, userInterruptRequested));

        context.eval("python", BOOTSTRAP);
        startFn = bindings.getMember("__cct_start");
        resumeFn = bindings.getMember("__cct_resume");

        var biosSource = new String(bios.readAllBytes(), StandardCharsets.UTF_8);
        context.eval("python", biosSource);

        var main = bindings.getMember("main");
        if (main == null || !main.canExecute()) throw new MachineException("Python BIOS does not define an async main()");
        coroutine = main.execute();

        timeout.addListener(timeoutListener);
    }

    /**
     * Mirror {@link dan200.computercraft.core.lua.CobaltLuaMachine#updateTimeout()}: wake in-flight guest execution so
     * tight loops observe {@linkplain TimeoutState#isSoftAborted() soft abort} and {@linkplain TimeoutState#isPaused()
     * pause}; hard abort tears down the context.
     */
    private void onTimeoutChanged() {
        if (disposed) return;
        if (timeout.isHardAborted()) {
            close();
            return;
        }
        // Soft abort is handled inside guest code via a trace hook calling cct.timeoutIsSoftAborted().
    }

    @Override
    public void interruptGuestExecution() {
        if (disposed) return;
        userInterruptRequested.set(true);
    }

    @Override
    public MachineResult handleEvent(@Nullable String eventName, @Nullable Object @Nullable [] arguments) {
        if (disposed) throw new IllegalStateException("Machine has been closed");

        if (timeout.isHardAborted()) {
            close();
            return MachineResult.TIMEOUT;
        }
        if (timeout.isPaused()) return MachineResult.PAUSE;

        if (eventFilter != null && eventName != null && !eventName.equals(eventFilter) && !"terminate".equals(eventName)) {
            return MachineResult.OK;
        }

        try {
            Value result;
            if (eventName == null) {
                result = startFn.execute(coroutine);
            } else {
                var convertedArgs = convertEventArgs(eventName, arguments);
                if (convertedArgs == null || convertedArgs.length == 0) {
                    result = resumeFn.execute(coroutine, eventName);
                } else {
                    var callArgs = new Object[convertedArgs.length + 2];
                    callArgs[0] = coroutine;
                    callArgs[1] = eventName;
                    System.arraycopy(convertedArgs, 0, callArgs, 2, convertedArgs.length);
                    result = resumeFn.execute(callArgs);
                }
            }

            if (isDoneTuple(result)) {
                close();
                return MachineResult.GENERIC_ERROR;
            }

            eventFilter = result.isString() ? result.asString() : null;
            return MachineResult.OK;
        } catch (PolyglotException e) {
            close();
            if (e.isInterrupted()) {
                // We don't currently use host-side interrupts for soft abort/user terminate. If we do end up here,
                // prefer a safe, Lua-like message.
                return MachineResult.error("Terminated");
            }
            LOG.warn(Logging.VM_ERROR, "Top level Python coroutine errored: {}", e.getMessage());
            return MachineResult.error(String.valueOf(e.getMessage()));
        } catch (Exception e) {
            close();
            LOG.warn(Logging.VM_ERROR, "Top level Python coroutine errored: {}", e.getMessage(), e);
            return MachineResult.error(e);
        }
    }

    private static @Nullable Object @Nullable [] convertEventArgs(String eventName, @Nullable Object @Nullable [] arguments) {
        if (arguments == null || arguments.length == 0) return arguments;

        // Match Lua semantics: the `char` event's first argument is a 1-character string.
        // Some platforms appear to deliver this as an integer codepoint or a 1-byte array.
        if ("char".equals(eventName)) {
            var arg0 = arguments[0];
            var converted = coerceCharArg(arg0);
            if (converted == null || converted == arg0) return arguments;

            var copy = Arrays.copyOf(arguments, arguments.length);
            copy[0] = converted;
            return copy;
        }

        return arguments;
    }

    private static @Nullable Object coerceCharArg(@Nullable Object value) {
        if (value == null) return null;
        if (value instanceof String) return value;

        if (value instanceof Number n) {
            return String.valueOf((char) n.intValue());
        }

        if (value instanceof byte[] bytes) {
            var s = new String(bytes, StandardCharsets.UTF_8);
            return s.isEmpty() ? "" : s.substring(0, 1);
        }

        return value;
    }

    private static boolean isDoneTuple(Value value) {
        if (!value.hasArrayElements() || value.getArraySize() != 2) return false;
        var tag = value.getArrayElement(0);
        return tag.isString() && "__cct_done__".equals(tag.asString());
    }

    @Override
    public void printExecutionState(StringBuilder out) {
    }

    @Override
    public void close() {
        if (disposed) return;
        disposed = true;
        timeout.removeListener(timeoutListener);
        context.close(true);
    }
}

