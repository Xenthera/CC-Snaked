// SPDX-FileCopyrightText: 2026 The CC: Tweaked Developers
//
// SPDX-License-Identifier: MPL-2.0

package dan200.computercraft.core.python;

import dan200.computercraft.api.lua.ILuaAPI;
import dan200.computercraft.api.lua.LuaException;
import dan200.computercraft.core.apis.FSAPI;
import dan200.computercraft.core.apis.OSAPI;
import dan200.computercraft.core.apis.TermMethods;
import dan200.computercraft.core.apis.handles.AbstractHandle;
import dan200.computercraft.core.apis.handles.ReadHandle;
import dan200.computercraft.core.terminal.Terminal;
import org.graalvm.polyglot.HostAccess;
import org.jspecify.annotations.Nullable;

/**
 * The host-side bridge exposed to Python guest code.
 * <p>
 * Methods are explicitly annotated with {@link HostAccess.Export} so they can be reached from
 * Python under {@link HostAccess#EXPLICIT}. Every method delegates to the same primitives used by
 * Lua's {@link TermMethods} / {@link OSAPI}, so behavior stays identical across language runtimes.
 * <p>
 * Coordinates and colour codes use the user-facing Lua conventions (1-based cursor positions,
 * power-of-two colour codes such as {@code 1, 2, 4, 8 ...}) so {@code cc.term}/{@code cc.os} can
 * present the same surface as the Lua APIs without doing further translation.
 */
public final class PythonHostBridge {
    private final @Nullable Terminal terminal;
    private final @Nullable OSAPI osApi;
    private final @Nullable FSAPI fsApi;

    PythonHostBridge(Iterable<ILuaAPI> apis) {
        Terminal foundTerminal = null;
        OSAPI foundOs = null;
        FSAPI foundFs = null;
        for (var api : apis) {
            if (foundTerminal == null && api instanceof TermMethods term) {
                try {
                    foundTerminal = term.getTerminal();
                } catch (Exception ignored) {
                    // The terminal may not yet be available; we just skip in that case.
                }
            }
            if (foundOs == null && api instanceof OSAPI os) foundOs = os;
            if (foundFs == null && api instanceof FSAPI fs) foundFs = fs;
        }
        terminal = foundTerminal;
        osApi = foundOs;
        fsApi = foundFs;
    }

    // -------- Terminal: text + cursor --------

    /**
     * Writes {@code text} at the current cursor position, advancing the cursor.
     * Mirrors {@link TermMethods#write(dan200.computercraft.api.lua.Coerced)}.
     */
    @HostAccess.Export
    public void write(String text) {
        var t = terminal;
        if (t == null) return;
        synchronized (t) {
            for (int i = 0, n = text.length(); i < n; i++) {
                var ch = text.charAt(i);
                if (ch == '\n') {
                    newLine(t);
                    continue;
                }

                // Terminal.write does not advance the cursor, so we track it here.
                t.write(String.valueOf(ch));
                var x = t.getCursorX() + 1;
                if (x >= t.getWidth()) {
                    newLine(t);
                } else {
                    t.setCursorPos(x, t.getCursorY());
                }
            }
        }
    }

    private static void newLine(Terminal t) {
        var y = t.getCursorY();
        if (y + 1 < t.getHeight()) {
            t.setCursorPos(0, y + 1);
        } else {
            t.scroll(1);
            t.setCursorPos(0, t.getHeight() - 1);
        }
    }

    @HostAccess.Export
    public int termGetWidth() {
        var t = terminal;
        return t == null ? 0 : t.getWidth();
    }

    @HostAccess.Export
    public int termGetHeight() {
        var t = terminal;
        return t == null ? 0 : t.getHeight();
    }

    @HostAccess.Export
    public int termGetCursorX() {
        var t = terminal;
        return t == null ? 1 : t.getCursorX() + 1;
    }

    @HostAccess.Export
    public int termGetCursorY() {
        var t = terminal;
        return t == null ? 1 : t.getCursorY() + 1;
    }

    @HostAccess.Export
    public void termSetCursorPos(int x, int y) {
        var t = terminal;
        if (t == null) return;
        synchronized (t) {
            t.setCursorPos(x - 1, y - 1);
        }
    }

    @HostAccess.Export
    public boolean termGetCursorBlink() {
        var t = terminal;
        return t != null && t.getCursorBlink();
    }

    @HostAccess.Export
    public void termSetCursorBlink(boolean blink) {
        var t = terminal;
        if (t == null) return;
        synchronized (t) {
            t.setCursorBlink(blink);
        }
    }

    @HostAccess.Export
    public void termScroll(int lines) {
        var t = terminal;
        if (t == null) return;
        t.scroll(lines);
    }

    @HostAccess.Export
    public void termClear() {
        var t = terminal;
        if (t == null) return;
        t.clear();
    }

    @HostAccess.Export
    public void termClearLine() {
        var t = terminal;
        if (t == null) return;
        t.clearLine();
    }

    // -------- Terminal: colour --------

    @HostAccess.Export
    public boolean termIsColor() {
        var t = terminal;
        return t != null && t.isColour();
    }

    @HostAccess.Export
    public int termGetTextColor() {
        var t = terminal;
        if (t == null) return 1;
        return TermMethods.encodeColour(t.getTextColour());
    }

    @HostAccess.Export
    public void termSetTextColor(int colour) throws LuaException {
        var t = terminal;
        if (t == null) return;
        var parsed = TermMethods.parseColour(colour);
        synchronized (t) {
            t.setTextColour(parsed);
        }
    }

    @HostAccess.Export
    public int termGetBackgroundColor() {
        var t = terminal;
        if (t == null) return 1 << 15;
        return TermMethods.encodeColour(t.getBackgroundColour());
    }

    @HostAccess.Export
    public void termSetBackgroundColor(int colour) throws LuaException {
        var t = terminal;
        if (t == null) return;
        var parsed = TermMethods.parseColour(colour);
        synchronized (t) {
            t.setBackgroundColour(parsed);
        }
    }

    // -------- OS: timers --------

    @HostAccess.Export
    public int osStartTimer(double seconds) throws LuaException {
        var os = osApi;
        if (os == null) throw new LuaException("os api unavailable");
        return os.startTimer(seconds);
    }

    @HostAccess.Export
    public void osCancelTimer(int id) {
        var os = osApi;
        if (os == null) return;
        os.cancelTimer(id);
    }

    // -------- FS: basic path + file reading --------

    @HostAccess.Export
    public String[] fsList(String path) throws LuaException {
        var fs = fsApi;
        if (fs == null) throw new LuaException("fs api unavailable");
        var result = fs.list(path);
        return result.toArray(String[]::new);
    }

    @HostAccess.Export
    public boolean fsExists(String path) {
        var fs = fsApi;
        return fs != null && fs.exists(path);
    }

    @HostAccess.Export
    public boolean fsIsDir(String path) {
        var fs = fsApi;
        return fs != null && fs.isDir(path);
    }

    @HostAccess.Export
    public @Nullable String fsReadAll(String path) throws LuaException {
        var fs = fsApi;
        if (fs == null) throw new LuaException("fs api unavailable");

        Object[] opened = fs.open(path, "r");
        if (opened.length >= 2 && opened[0] == null) return null;
        if (opened.length == 0 || opened[0] == null) return null;

        var handle = opened[0];
        if (!(handle instanceof ReadHandle reader)) return null;
        try {
            var contents = reader.readAll();
            return contents == null || contents.length == 0 || contents[0] == null ? null : String.valueOf(contents[0]);
        } finally {
            ((AbstractHandle) reader).close();
        }
    }
}
