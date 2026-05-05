// SPDX-FileCopyrightText: 2026 The CC: Tweaked Developers
//
// SPDX-License-Identifier: MPL-2.0

package dan200.computercraft.core.graalpy;

import org.graalvm.polyglot.Context;
import org.graalvm.polyglot.HostAccess;
import org.graalvm.polyglot.PolyglotException;
import org.graalvm.polyglot.Value;

import java.time.Duration;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicReference;

/**
 * GraalPy embed spike used to validate suspend/resume and cancellation semantics from a Java host.
 * <p>
 * This is intended for manual execution during early experimentation.
 */
public final class GraalPyCoroutineSpike {
    private GraalPyCoroutineSpike() {
    }

    public static void main(String[] args) {
        suspendResumeProbe();
        timeoutProbe();
        System.out.println("GraalPy coroutine spike completed");
    }

    private static void suspendResumeProbe() {
        try (var context = createContext()) {
            var bindings = context.getBindings("python");
            context.eval("python", """
                class AwaitPullEvent:
                    def __init__(self, filter):
                        self.filter = filter

                    def __await__(self):
                        event = yield self.filter
                        return event

                def start(coro):
                    return coro.send(None)

                def resume(coro, payload):
                    try:
                        return coro.send(payload)
                    except StopIteration as e:
                        return e.value

                async def main():
                    event = await AwaitPullEvent("key")
                    return event
                """);

            var main = bindings.getMember("main");
            var coroutine = main.execute();

            // Start the coroutine within Python to avoid host/null conversion issues.
            var yielded = bindings.getMember("start").execute(coroutine);
            if (!"key".equals(yielded.asString())) {
                throw new IllegalStateException("Unexpected first yield: " + yielded);
            }

            var payload = new Object[]{ "key", "payload" };
            var result = bindings.getMember("resume").execute(coroutine, payload);

            System.out.println("suspendResumeProbe result: " + result);
        }
    }

    private static void timeoutProbe() {
        try (var context = createContext()) {
            context.eval("python", """
                async def main_blocking():
                    while True:
                        pass

                async def main_polling():
                    x = 0
                    while True:
                        x += 1
                """);

            var bindings = context.getBindings("python");
            var main = bindings.getMember("main_blocking");
            var coroutine = main.execute();

            var started = new CountDownLatch(1);
            var done = new CountDownLatch(1);
            var thrown = new AtomicReference<Throwable>();

            var worker = new Thread(() -> {
                started.countDown();
                try {
                    coroutine.invokeMember("send", (Object) null);
                } catch (Throwable t) {
                    thrown.set(t);
                } finally {
                    done.countDown();
                }
            });

            worker.start();
            awaitLatch(started);

            var soft = Duration.ofMillis(150);
            var hard = Duration.ofMillis(350);

            sleep(soft);
            try {
                context.interrupt(Duration.ofMillis(10));
            } catch (Exception ignored) {
                System.err.println("timeoutProbe interrupt failed: " + ignored);
            }

            sleep(hard);
            try {
                if (!worker.isAlive()) {
                    done.await();
                } else {
                    context.close(true);
                }
            } catch (Exception ignored) {
                System.err.println("timeoutProbe close failed: " + ignored);
            }

            awaitLatch(done);

            var t = thrown.get();
            if (t == null) throw new IllegalStateException("Expected coroutine cancellation/interrupt");

            if (t instanceof PolyglotException polyglot) {
                System.out.println("timeoutProbe PolyglotException cancelled=" + polyglot.isCancelled()
                    + " interrupted=" + polyglot.isInterrupted());
            } else {
                System.out.println("timeoutProbe throwable: " + t);
            }
        }
    }

    private static Context createContext() {
        return Context.newBuilder("python")
            .allowHostAccess(HostAccess.ALL)
            .allowHostClassLookup(s -> true)
            .build();
    }

    private static void awaitLatch(CountDownLatch latch) {
        try {
            latch.await();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Interrupted waiting for latch", e);
        }
    }

    private static void sleep(Duration duration) {
        try {
            Thread.sleep(duration.toMillis());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Interrupted", e);
        }
    }
}

