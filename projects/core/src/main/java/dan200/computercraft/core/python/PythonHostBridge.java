// SPDX-FileCopyrightText: 2026 The CC: Tweaked Developers
//
// SPDX-License-Identifier: MPL-2.0

package dan200.computercraft.core.python;

import dan200.computercraft.api.lua.ILuaAPI;
import dan200.computercraft.api.lua.LuaException;
import dan200.computercraft.api.lua.ObjectArguments;
import dan200.computercraft.core.computer.TimeoutState;
import dan200.computercraft.core.apis.FSAPI;
import dan200.computercraft.core.apis.HTTPAPI;
import dan200.computercraft.core.apis.OSAPI;
import dan200.computercraft.core.apis.TermMethods;
import dan200.computercraft.core.apis.handles.AbstractHandle;
import dan200.computercraft.core.apis.handles.ReadHandle;
import dan200.computercraft.core.apis.handles.ReadWriteHandle;
import dan200.computercraft.core.apis.handles.WriteHandle;
import dan200.computercraft.core.terminal.Terminal;
import org.graalvm.polyglot.HostAccess;
import org.graalvm.polyglot.Value;
import org.jspecify.annotations.Nullable;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicBoolean;

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
    private final @Nullable TermMethods termApi;
    private final @Nullable OSAPI osApi;
    private final @Nullable FSAPI fsApi;
    private final @Nullable HTTPAPI httpApi;
    private final TimeoutState timeout;
    private final AtomicBoolean userInterruptRequested;

    PythonHostBridge(Iterable<ILuaAPI> apis, TimeoutState timeout, AtomicBoolean userInterruptRequested) {
        TermMethods foundTerm = null;
        OSAPI foundOs = null;
        FSAPI foundFs = null;
        HTTPAPI foundHttp = null;
        for (var api : apis) {
            if (foundTerm == null && api instanceof TermMethods term) foundTerm = term;
            if (foundOs == null && api instanceof OSAPI os) foundOs = os;
            if (foundFs == null && api instanceof FSAPI fs) foundFs = fs;
            if (foundHttp == null && api instanceof HTTPAPI http) foundHttp = http;
        }
        termApi = foundTerm;
        osApi = foundOs;
        fsApi = foundFs;
        httpApi = foundHttp;
        this.timeout = timeout;
        this.userInterruptRequested = userInterruptRequested;
    }

    private @Nullable Terminal getTerminal() {
        var api = termApi;
        if (api == null) return null;
        try {
            return api.getTerminal();
        } catch (Exception ignored) {
            // Terminal may not yet be available (for instance, during early boot).
            return null;
        }
    }

    // -------- Terminal: text + cursor --------

    /**
     * Writes {@code text} at the current cursor position, advancing the cursor.
     * Mirrors {@link TermMethods#write(dan200.computercraft.api.lua.Coerced)}.
     */
    @HostAccess.Export
    public void write(String text) {
        var t = getTerminal();
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

    /**
     * Writes {@code text} at the current cursor position, advancing the cursor, without wrapping.
     * <p>
     * This matches the behaviour of Lua's {@code term.write}: it copies text onto the current line, and advances the
     * cursor, but does not wrap or scroll.
     */
    @HostAccess.Export
    public void termWrite(String text) {
        var t = getTerminal();
        if (t == null) return;
        synchronized (t) {
            t.write(text);
            t.setCursorPos(t.getCursorX() + text.length(), t.getCursorY());
        }
    }

    /**
     * Writes {@code text} at the current cursor position with per-character colours, without wrapping.
     * Mirrors {@link TermMethods#blit(ByteBuffer, ByteBuffer, ByteBuffer)}.
     *
     * @param text The text to write.
     * @param textColour A string of hex digits (0-f) representing text colours.
     * @param backgroundColour A string of hex digits (0-f) representing background colours.
     */
    @HostAccess.Export
    public void termBlit(String text, String textColour, String backgroundColour) {
        var t = getTerminal();
        if (t == null) return;
        var n = text.length();
        if (textColour.length() != n || backgroundColour.length() != n) return;

        // Terminal.blit expects raw bytes, with colour buffers holding base-16 digits.
        // Use ISO-8859-1 for a stable 1 byte/char mapping for 0-255 range.
        var textBuf = ByteBuffer.wrap(text.getBytes(StandardCharsets.ISO_8859_1));
        var fgBuf = ByteBuffer.wrap(textColour.getBytes(StandardCharsets.ISO_8859_1));
        var bgBuf = ByteBuffer.wrap(backgroundColour.getBytes(StandardCharsets.ISO_8859_1));
        synchronized (t) {
            t.blit(textBuf, fgBuf, bgBuf);
            t.setCursorPos(t.getCursorX() + n, t.getCursorY());
        }
    }

    // -------- Execution control --------

    /**
     * Whether the current task has run too long without yielding.
     *
     * This mirrors Lua's "Too long without yielding" soft abort flag, but is surfaced as a pollable function so we can
     * raise an exception from inside guest code (via a trace hook) rather than aborting the whole VM.
     */
    @HostAccess.Export
    public boolean timeoutIsSoftAborted() {
        return timeout.isSoftAborted();
    }

    /**
     * Consume a user interrupt request (Ctrl+T/shutdown) set by the host.
     *
     * Returns {@code true} once, then resets to {@code false}.
     */
    @HostAccess.Export
    public boolean consumeUserInterrupt() {
        return userInterruptRequested.getAndSet(false);
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
        var t = getTerminal();
        return t == null ? 0 : t.getWidth();
    }

    @HostAccess.Export
    public int termGetHeight() {
        var t = getTerminal();
        return t == null ? 0 : t.getHeight();
    }

    @HostAccess.Export
    public int termGetCursorX() {
        var t = getTerminal();
        return t == null ? 1 : t.getCursorX() + 1;
    }

    @HostAccess.Export
    public int termGetCursorY() {
        var t = getTerminal();
        return t == null ? 1 : t.getCursorY() + 1;
    }

    @HostAccess.Export
    public void termSetCursorPos(int x, int y) {
        var t = getTerminal();
        if (t == null) return;
        synchronized (t) {
            t.setCursorPos(x - 1, y - 1);
        }
    }

    @HostAccess.Export
    public boolean termGetCursorBlink() {
        var t = getTerminal();
        return t != null && t.getCursorBlink();
    }

    @HostAccess.Export
    public void termSetCursorBlink(boolean blink) {
        var t = getTerminal();
        if (t == null) return;
        synchronized (t) {
            t.setCursorBlink(blink);
        }
    }

    @HostAccess.Export
    public void termScroll(int lines) {
        var t = getTerminal();
        if (t == null) return;
        t.scroll(lines);
    }

    @HostAccess.Export
    public void termClear() {
        var t = getTerminal();
        if (t == null) return;
        t.clear();
    }

    @HostAccess.Export
    public void termClearLine() {
        var t = getTerminal();
        if (t == null) return;
        t.clearLine();
    }

    // -------- Terminal: colour --------

    @HostAccess.Export
    public boolean termIsColor() {
        var t = getTerminal();
        return t != null && t.isColour();
    }

    @HostAccess.Export
    public int termGetTextColor() {
        var t = getTerminal();
        if (t == null) return 1;
        return TermMethods.encodeColour(t.getTextColour());
    }

    @HostAccess.Export
    public void termSetTextColor(int colour) throws LuaException {
        var t = getTerminal();
        if (t == null) return;
        var parsed = TermMethods.parseColour(colour);
        synchronized (t) {
            t.setTextColour(parsed);
        }
    }

    @HostAccess.Export
    public int termGetBackgroundColor() {
        var t = getTerminal();
        if (t == null) return 1 << 15;
        return TermMethods.encodeColour(t.getBackgroundColour());
    }

    @HostAccess.Export
    public void termSetBackgroundColor(int colour) throws LuaException {
        var t = getTerminal();
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

    @HostAccess.Export
    public void osShutdown() throws LuaException {
        var os = osApi;
        if (os == null) throw new LuaException("os api unavailable");
        os.doShutdown();
    }

    @HostAccess.Export
    public void osReboot() throws LuaException {
        var os = osApi;
        if (os == null) throw new LuaException("os api unavailable");
        os.doReboot();
    }

    /**
     * Queue a CraftOS event from Python (same semantics as Lua {@code os.queueEvent}).
     */
    @HostAccess.Export
    public void osQueueEvent(String name, Object... rawArgs) throws LuaException {
        var os = osApi;
        if (os == null) throw new LuaException("os api unavailable");
        var all = new Object[rawArgs.length + 1];
        all[0] = name;
        for (var i = 0; i < rawArgs.length; i++) all[i + 1] = coerceGuestValue(rawArgs[i]);
        os.queueEvent(name, new ObjectArguments(all));
    }

    // -------- HTTP (same implementation as Lua native ``http`` API) --------

    /**
     * Forward to {@link HTTPAPI#request(IArguments)} with Graal guest values coerced to Java maps/strings.
     */
    @HostAccess.Export
    public Object[] httpRequest(Object... rawArgs) throws LuaException {
        var http = httpApi;
        if (http == null) return new Object[]{ false, "http api unavailable" };
        var args = new Object[rawArgs.length];
        for (var i = 0; i < rawArgs.length; i++) args[i] = coerceGuestValue(rawArgs[i]);
        return http.request(new ObjectArguments(args));
    }

    @HostAccess.Export
    public Object[] httpCheckURL(String address) throws LuaException {
        var http = httpApi;
        if (http == null) return new Object[]{ false, "http api unavailable" };
        return http.checkURL(address);
    }

    @HostAccess.Export
    public Object[] httpWebsocket(Object... rawArgs) throws LuaException {
        var http = httpApi;
        if (http == null) return new Object[]{ false, "http api unavailable" };
        var args = new Object[rawArgs.length];
        for (var i = 0; i < rawArgs.length; i++) args[i] = coerceGuestValue(rawArgs[i]);
        return http.websocket(new ObjectArguments(args));
    }

    /**
     * Coerce Graal/polyglot guest objects (Python {@code dict}, {@code list}, etc.) into Java types
     * suitable for {@link ObjectArguments} / {@link HTTPAPI}.
     */
    private static @Nullable Object coerceGuestValue(Object o) {
        if (o == null) return null;
        if (!(o instanceof Value v)) return o;
        if (v.isNull()) return null;
        if (v.isBoolean()) return v.asBoolean();
        if (v.fitsInFloat()) return v.asDouble();
        if (v.isString()) return v.asString();
        if (v.hasBufferElements()) {
            long size = v.getBufferSize();
            var buf = new byte[(int) size];
            v.readBuffer(0, buf, 0, (int) size);
            return ByteBuffer.wrap(buf);
        }
        if (v.hasArrayElements()) {
            long n = v.getArraySize();
            var list = new ArrayList<Object>();
            for (long i = 0; i < n; i++) list.add(coerceGuestValue(v.getArrayElement(i)));
            return list;
        }
        if (v.hasMembers()) {
            var map = new HashMap<String, Object>();
            for (var key : v.getMemberKeys()) {
                map.put(key, coerceGuestValue(v.getMember(key)));
            }
            return map;
        }
        return o;
    }

    // -------- FS: basic path + file reading --------

    @HostAccess.Export
    public String fsList(String path) throws LuaException {
        var fs = fsApi;
        if (fs == null) throw new LuaException("fs api unavailable");
        var result = fs.list(path);
        return String.join("\n", result);
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
    public boolean fsIsReadOnly(String path) {
        var fs = fsApi;
        if (fs == null) return true;
        return fs.isReadOnly(path);
    }

    @HostAccess.Export
    public void fsMakeDir(String path) throws LuaException {
        var fs = fsApi;
        if (fs == null) throw new LuaException("fs api unavailable");
        fs.makeDir(path);
    }

    @HostAccess.Export
    public void fsDelete(String path) throws LuaException {
        var fs = fsApi;
        if (fs == null) throw new LuaException("fs api unavailable");
        fs.delete(path);
    }

    @HostAccess.Export
    public void fsMove(String path, String dest) throws LuaException {
        var fs = fsApi;
        if (fs == null) throw new LuaException("fs api unavailable");
        fs.move(path, dest);
    }

    @HostAccess.Export
    public void fsCopy(String path, String dest) throws LuaException {
        var fs = fsApi;
        if (fs == null) throw new LuaException("fs api unavailable");
        fs.copy(path, dest);
    }

    @HostAccess.Export
    public long fsGetSize(String path) throws LuaException {
        var fs = fsApi;
        if (fs == null) throw new LuaException("fs api unavailable");
        return fs.getSize(path);
    }

    @HostAccess.Export
    public String fsCombine(String a, String b) throws LuaException {
        var fs = fsApi;
        if (fs == null) throw new LuaException("fs api unavailable");
        return fs.combine(new ObjectArguments(a, b));
    }

    @HostAccess.Export
    public String fsGetName(String path) throws LuaException {
        var fs = fsApi;
        if (fs == null) throw new LuaException("fs api unavailable");
        return fs.getName(path);
    }

    @HostAccess.Export
    public String fsGetDir(String path) throws LuaException {
        var fs = fsApi;
        if (fs == null) throw new LuaException("fs api unavailable");
        return fs.getDir(path);
    }

    @HostAccess.Export
    public Object fsAttributes(String path) throws LuaException {
        var fs = fsApi;
        if (fs == null) throw new LuaException("fs api unavailable");
        return fs.attributes(path);
    }

    @HostAccess.Export
    public @Nullable String fsGetDrive(String path) throws LuaException {
        var fs = fsApi;
        if (fs == null) throw new LuaException("fs api unavailable");
        var result = fs.getDrive(path);
        return result == null || result.length == 0 || result[0] == null ? null : String.valueOf(result[0]);
    }

    @HostAccess.Export
    public Object fsGetFreeSpace(String path) throws LuaException {
        var fs = fsApi;
        if (fs == null) throw new LuaException("fs api unavailable");
        return fs.getFreeSpace(path);
    }

    @HostAccess.Export
    public @Nullable Object fsGetCapacity(String path) throws LuaException {
        var fs = fsApi;
        if (fs == null) throw new LuaException("fs api unavailable");
        return fs.getCapacity(path);
    }

    @HostAccess.Export
    public Object[] fsOpen(String path, String mode) {
        var fs = fsApi;
        if (fs == null) return new Object[]{ null, "fs api unavailable" };
        try {
            var opened = fs.open(path, mode);
            if (opened.length >= 2 && opened[0] == null) return opened;
            if (opened.length == 0 || opened[0] == null) return new Object[]{ null, "Failed to open file" };
            // Always return [handle, errorOrNull]. A length-1 array confused some GraalPy interop paths when
            // guest code accessed res[1], so match the failure tuple shape.
            return new Object[]{ new PythonFileHandle(opened[0]), null };
        } catch (LuaException e) {
            return new Object[]{ null, e.getMessage() };
        }
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
            if (contents == null || contents.length == 0 || contents[0] == null) return null;
            var value = contents[0];
            if (value instanceof byte[] bytes) return new String(bytes, java.nio.charset.StandardCharsets.UTF_8);
            return String.valueOf(value);
        } finally {
            ((AbstractHandle) reader).close();
        }
    }

    /**
     * Coerce Python/polyglot guest values to {@link String} for writes. GraalPy often passes string-like values that are
     * not {@code instanceof String}; {@link ObjectArguments#getStringCoerced(int)} would otherwise stringify them
     * incorrectly (or yield unusable bytes).
     */
    private static String guestString(Object value) {
        if (value == null) return "";
        if (value instanceof String s) return s;
        if (value instanceof Value v) {
            if (v.isNull()) return "";
            if (v.isString()) return v.asString();
            return v.toString();
        }
        return String.valueOf(value);
    }

    /**
     * Replace a file with text using JVM-coerced strings (reliable from Python). Prefer over guest {@code handle.write}
     * for bulk diagnostic output.
     */
    @HostAccess.Export
    public void fsWriteText(Object pathObj, Object contentsObj) throws LuaException {
        var fs = fsApi;
        if (fs == null) throw new LuaException("fs api unavailable");

        var path = guestString(pathObj);
        var contents = guestString(contentsObj);

        Object[] opened = fs.open(path, "w");
        if (opened.length >= 2 && opened[0] == null) {
            var err = opened.length > 1 ? opened[1] : null;
            throw new LuaException(err != null ? String.valueOf(err) : "Failed to open file");
        }
        if (opened.length == 0 || opened[0] == null) throw new LuaException("Failed to open file");

        var raw = opened[0];
        try {
            if (raw instanceof WriteHandle w) {
                w.write(new ObjectArguments(contents));
            } else if (raw instanceof ReadWriteHandle rw) {
                rw.write(new ObjectArguments(contents));
            } else {
                throw new LuaException("File not writable");
            }
        } finally {
            ((AbstractHandle) raw).close();
        }
    }

    public static final class PythonFileHandle {
        private final Object handle;

        PythonFileHandle(Object handle) {
            this.handle = handle;
        }

        @HostAccess.Export
        public @Nullable String readAll() throws LuaException {
            if (handle instanceof ReadHandle r) return unpackString(r.readAll());
            if (handle instanceof ReadWriteHandle rw) return unpackString(rw.readAll());
            throw new LuaException("File not readable");
        }

        @HostAccess.Export
        public @Nullable String readLine(@Nullable Boolean withTrailing) throws LuaException {
            var trailing = Optional.ofNullable(withTrailing);
            if (handle instanceof ReadHandle r) return unpackString(r.readLine(trailing));
            if (handle instanceof ReadWriteHandle rw) return unpackString(rw.readLine(trailing));
            throw new LuaException("File not readable");
        }

        @HostAccess.Export
        public @Nullable Object read(@Nullable Integer count) throws LuaException {
            var opt = Optional.ofNullable(count);
            Object[] out;
            if (handle instanceof ReadHandle r) out = r.read(opt);
            else if (handle instanceof ReadWriteHandle rw) out = rw.read(opt);
            else throw new LuaException("File not readable");

            if (out == null) return null;
            if (out.length == 0) return null;
            return out[0];
        }

        @HostAccess.Export
        public void write(Object text) throws LuaException {
            var s = guestString(text);
            if (handle instanceof WriteHandle w) {
                w.write(new ObjectArguments(s));
                return;
            }
            if (handle instanceof ReadWriteHandle rw) {
                rw.write(new ObjectArguments(s));
                return;
            }
            throw new LuaException("File not writable");
        }

        @HostAccess.Export
        public void writeLine(Object text) throws LuaException {
            write(guestString(text) + "\n");
        }

        @HostAccess.Export
        public void flush() throws LuaException {
            if (handle instanceof WriteHandle w) {
                w.flush();
                return;
            }
            if (handle instanceof ReadWriteHandle rw) {
                rw.flush();
                return;
            }
        }

        @HostAccess.Export
        public void close() throws LuaException {
            ((AbstractHandle) handle).close();
        }

        private static @Nullable String unpackString(Object @Nullable [] result) {
            if (result == null || result.length == 0 || result[0] == null) return null;
            var value = result[0];
            if (value instanceof byte[] bytes) return new String(bytes, java.nio.charset.StandardCharsets.UTF_8);
            return String.valueOf(value);
        }
    }
}
