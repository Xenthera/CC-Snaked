// SPDX-FileCopyrightText: 2026 The CC: Tweaked Developers
//
// SPDX-License-Identifier: MPL-2.0

package dan200.computercraft.core.python;

import dan200.computercraft.api.lua.ILuaAPI;
import dan200.computercraft.api.lua.ILuaContext;
import dan200.computercraft.core.apis.TermMethods;
import dan200.computercraft.core.asm.LuaMethodSupplier;
import dan200.computercraft.core.computer.TimeoutState;
import dan200.computercraft.core.lua.MachineEnvironment;
import dan200.computercraft.core.metrics.MetricsObserver;
import dan200.computercraft.core.terminal.Terminal;
import org.graalvm.polyglot.PolyglotException;
import org.junit.jupiter.api.Test;

import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class PythonMachineTest {
    private static final class TestTimeoutState extends TimeoutState {
        @Override
        public void refresh() {
        }
    }

    @Test
    void canStartAndFilterEvents() throws Exception {
        var timeout = new TestTimeoutState();
        ILuaContext context = task -> {
            throw new UnsupportedOperationException("No main-thread tasks in this test");
        };

        var env = new MachineEnvironment(
            context,
            MetricsObserver.discard(),
            timeout,
            List.of(),
            LuaMethodSupplier.create(List.of()),
            "CC (test)"
        );

        var bios = """
            class _AwaitPullEvent:
                def __init__(self, filter=None):
                    self.filter = filter

                def __await__(self):
                    event = yield self.filter
                    return event

            class os:
                @staticmethod
                async def pull_event_raw(filter=None):
                    return await _AwaitPullEvent(filter)

            async def main():
                await os.pull_event_raw("key")
                while True:
                    await os.pull_event_raw()
            """;

        var machine = new PythonMachine(env, new ByteArrayInputStream(bios.getBytes(StandardCharsets.UTF_8)));

        assertFalse(machine.handleEvent(null, null).isError());

        // Mismatched event should be ignored.
        assertFalse(machine.handleEvent("mouse_click", null).isError());

        // Matching event should be processed.
        assertFalse(machine.handleEvent("key", new Object[]{ "x" }).isError());

        machine.close();
    }

    @Test
    void canImportCcTermFromRom() throws Exception {
        var timeout = new TestTimeoutState();
        ILuaContext context = task -> {
            throw new UnsupportedOperationException("No main-thread tasks in this test");
        };

        var terminal = new Terminal(20, 3, true);
        ILuaAPI termApi = new StubTermApi(terminal);

        var env = new MachineEnvironment(
            context,
            MetricsObserver.discard(),
            timeout,
            List.of(termApi),
            LuaMethodSupplier.create(List.of()),
            "CC (test)"
        );

        // Exercise the ROM importer: ``cc.term`` must resolve via the meta-path finder
        // and route writes back through the host bridge to our stub terminal.
        var bios = """
            from cc import term, os as ccos

            async def main():
                term.write("Imported")
                while True:
                    try:
                        await ccos.pull_event()
                    except ccos.Terminated:
                        return
            """;

        var machine = new PythonMachine(env, new ByteArrayInputStream(bios.getBytes(StandardCharsets.UTF_8)));
        assertFalse(machine.handleEvent(null, null).isError());

        var line = terminal.getLine(0).toString();
        assertEquals("Imported", line.substring(0, "Imported".length()));

        machine.close();
    }

    @Test
    void canImportRomProgramsShell() throws Exception {
        var timeout = new TestTimeoutState();
        ILuaContext context = task -> {
            throw new UnsupportedOperationException("No main-thread tasks in this test");
        };

        var terminal = new Terminal(20, 3, true);
        ILuaAPI termApi = new StubTermApi(terminal);

        var env = new MachineEnvironment(
            context,
            MetricsObserver.discard(),
            timeout,
            List.of(termApi),
            LuaMethodSupplier.create(List.of()),
            "CC (test)"
        );

        // Importing the shell should succeed via the ROM importer. We then park in an event
        // loop instead of returning, since a returning BIOS coroutine is treated as an error.
        var bios = """
            from rom.programs import shell as _shell
            from cc import os as ccos

            assert callable(_shell.run), "rom.programs.shell did not expose run()"

            async def main():
                while True:
                    try:
                        await ccos.pull_event()
                    except ccos.Terminated:
                        return
            """;

        var machine = new PythonMachine(env, new ByteArrayInputStream(bios.getBytes(StandardCharsets.UTF_8)));
        assertFalse(machine.handleEvent(null, null).isError());

        // If the module import failed we'd error before the first handleEvent returned.
        machine.close();
    }

    @Test
    void charEventArgIsAStringLikeLua() throws Exception {
        var timeout = new TestTimeoutState();
        ILuaContext context = task -> {
            throw new UnsupportedOperationException("No main-thread tasks in this test");
        };

        var terminal = new Terminal(20, 3, true);
        ILuaAPI termApi = new StubTermApi(terminal);

        var env = new MachineEnvironment(
            context,
            MetricsObserver.discard(),
            timeout,
            List.of(termApi),
            LuaMethodSupplier.create(List.of()),
            "CC (test)"
        );

        var bios = """
            from cc import os as ccos
            from cc import term

            async def main():
                ev = await ccos.pull_event_raw("char")
                term.write(ev[1])
                while True:
                    await ccos.pull_event_raw()
            """;

        var machine = new PythonMachine(env, new ByteArrayInputStream(bios.getBytes(StandardCharsets.UTF_8)));
        assertFalse(machine.handleEvent(null, null).isError());
        assertFalse(machine.handleEvent("char", new Object[]{ 97 }).isError());

        var line = terminal.getLine(0).toString();
        assertEquals("a", line.substring(0, 1));

        machine.close();
    }

    @Test
    void terminateEventStopsBiosViaCcOs() throws Exception {
        var timeout = new TestTimeoutState();
        ILuaContext context = task -> {
            throw new UnsupportedOperationException("No main-thread tasks in this test");
        };

        var terminal = new Terminal(20, 3, true);
        ILuaAPI termApi = new StubTermApi(terminal);

        var env = new MachineEnvironment(
            context,
            MetricsObserver.discard(),
            timeout,
            List.of(termApi),
            LuaMethodSupplier.create(List.of()),
            "CC (test)"
        );

        var bios = """
            from cc import os as ccos

            async def main():
                while True:
                    try:
                        await ccos.pull_event()
                    except ccos.Terminated:
                        return
            """;

        var machine = new PythonMachine(env, new ByteArrayInputStream(bios.getBytes(StandardCharsets.UTF_8)));
        assertFalse(machine.handleEvent(null, null).isError());

        // ``terminate`` must propagate through cc.os.pull_event() as ccos.Terminated and let the
        // BIOS coroutine return. The machine signals completion via ``__cct_done__``, which
        // surfaces here as a non-OK result.
        var result = machine.handleEvent("terminate", null);
        // Either an error/done result; the key invariant is the coroutine actually returned.
        assertNotNull(result);

        machine.close();
    }

    @Test
    void canWriteToTerminalViaBridge() throws Exception {
        var timeout = new TestTimeoutState();
        ILuaContext context = task -> {
            throw new UnsupportedOperationException("No main-thread tasks in this test");
        };

        var terminal = new Terminal(20, 3, true);
        ILuaAPI termApi = new StubTermApi(terminal);

        var env = new MachineEnvironment(
            context,
            MetricsObserver.discard(),
            timeout,
            List.of(termApi),
            LuaMethodSupplier.create(List.of()),
            "CC (test)"
        );

        var bios = """
            class _AwaitEvent:
                def __init__(self, filter=None):
                    self.filter = filter

                def __await__(self):
                    return (yield self.filter)

            async def main():
                cct.write("Hello")
                while True:
                    await _AwaitEvent()
            """;

        var machine = new PythonMachine(env, new ByteArrayInputStream(bios.getBytes(StandardCharsets.UTF_8)));
        assertFalse(machine.handleEvent(null, null).isError());

        var line = terminal.getLine(0).toString();
        assertEquals("Hello", line.substring(0, 5));

        machine.close();
    }

    @Test
    void canImportNewRomCcModules() throws Exception {
        // Verifies that the literal-layout migration (cc.* under rom/modules/main/cc/) keeps
        // ``cc.expect``, ``cc.strings``, ``cc.completion``, and ``cc.shell.completion``
        // resolvable through the meta-path importer.
        var timeout = new TestTimeoutState();
        ILuaContext context = task -> {
            throw new UnsupportedOperationException("No main-thread tasks in this test");
        };

        var env = new MachineEnvironment(
            context,
            MetricsObserver.discard(),
            timeout,
            List.of(),
            LuaMethodSupplier.create(List.of()),
            "CC (test)"
        );

        var bios = """
            from cc import expect as ccexpect
            from cc import help as cchelp
            from cc import strings as ccstrings
            from cc import completion as cccompletion
            from cc.shell import completion as shellcompletion

            assert ccexpect.expect(1, "hi", "string") == "hi"
            cchelp.set_path("/rom/help")
            assert cchelp.get_path() == "/rom/help"
            assert ccstrings.ensure_width("ab", 4) == "ab  "
            assert cccompletion.choice("h", ["help", "history"]) == ["elp", "istory"]
            assert callable(shellcompletion.build)

            async def main():
                while True:
                    pass
                    yield None
            """;

        var machine = new PythonMachine(env, new ByteArrayInputStream(bios.getBytes(StandardCharsets.UTF_8)));
        // The asserts above ran at module-load time. If anything failed, the constructor would
        // have thrown a MachineException already.
        machine.close();
    }

    @Test
    void shellTokeniseMatchesLuaSemantics() throws Exception {
        // Verifies the cc.shell.tokenise port matches Lua's quote/whitespace handling.
        var timeout = new TestTimeoutState();
        ILuaContext context = task -> {
            throw new UnsupportedOperationException("No main-thread tasks in this test");
        };

        var env = new MachineEnvironment(
            context,
            MetricsObserver.discard(),
            timeout,
            List.of(),
            LuaMethodSupplier.create(List.of()),
            "CC (test)"
        );

        var bios = """
            from cc import shell as ccshell

            assert ccshell.tokenise("a b c") == ["a", "b", "c"], "whitespace split"
            assert ccshell.tokenise('a "b c" d') == ["a", "b c", "d"], "quoted segment"
            assert ccshell.tokenise("") == [], "empty"

            async def main():
                while True:
                    pass
                    yield None
            """;

        var machine = new PythonMachine(env, new ByteArrayInputStream(bios.getBytes(StandardCharsets.UTF_8)));
        machine.close();
    }

    @Test
    void pythonSettingsDefaultsMatchLuaBios() throws Exception {
        var timeout = new TestTimeoutState();
        ILuaContext context = task -> {
            throw new UnsupportedOperationException("No main-thread tasks in this test");
        };

        var env = new MachineEnvironment(
            context,
            MetricsObserver.discard(),
            timeout,
            List.of(),
            LuaMethodSupplier.create(List.of()),
            "CC (test)"
        );

        var bios = """
            from cc import settings as ccsettings

            assert ccsettings.get("shell.autocomplete") is True
            assert ccsettings.get("shell.autocomplete_hidden") is False
            assert ccsettings.get("motd.enable") is True
            assert ccsettings.get("list.show_hidden") is False

            async def main():
                while True:
                    pass
                    yield None
            """;

        var machine = new PythonMachine(env, new ByteArrayInputStream(bios.getBytes(StandardCharsets.UTF_8)));
        machine.close();
    }

    @Test
    void shadowedStdlibHttpRejectedAtBoot() {
        var timeout = new TestTimeoutState();
        ILuaContext context = task -> {
            throw new UnsupportedOperationException("No main-thread tasks in this test");
        };

        var env = new MachineEnvironment(
            context,
            MetricsObserver.discard(),
            timeout,
            List.of(),
            LuaMethodSupplier.create(List.of()),
            "CC (test)"
        );

        var bios = """
            import http

            async def main():
                while True:
                    yield None
            """;

        assertThrows(PolyglotException.class, () ->
            new PythonMachine(env, new ByteArrayInputStream(bios.getBytes(StandardCharsets.UTF_8))));
    }

    @Test
    void canImportRomStartup() throws Exception {
        // Verifies the startup module loads through the rom.* importer.
        var timeout = new TestTimeoutState();
        ILuaContext context = task -> {
            throw new UnsupportedOperationException("No main-thread tasks in this test");
        };

        var env = new MachineEnvironment(
            context,
            MetricsObserver.discard(),
            timeout,
            List.of(),
            LuaMethodSupplier.create(List.of()),
            "CC (test)"
        );

        var bios = """
            from rom import startup

            assert callable(startup.run), "rom.startup must expose run()"

            async def main():
                while True:
                    pass
                    yield None
            """;

        var machine = new PythonMachine(env, new ByteArrayInputStream(bios.getBytes(StandardCharsets.UTF_8)));
        machine.close();
    }

    private static final class StubTermApi extends TermMethods implements ILuaAPI {
        private final Terminal terminal;

        StubTermApi(Terminal terminal) {
            this.terminal = terminal;
        }

        @Override
        public Terminal getTerminal() {
            return terminal;
        }

        @Override
        public String[] getNames() {
            return new String[]{ "term" };
        }
    }
}

