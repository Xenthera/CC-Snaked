// Copyright Daniel Ratcliffe, 2011-2022. Do not distribute without permission.
//
// SPDX-License-Identifier: LicenseRef-CCPL

package dan200.computercraft.core.lua;

import dan200.computercraft.api.lua.IDynamicLuaObject;
import dan200.computercraft.api.lua.ILuaContext;
import dan200.computercraft.api.lua.ILuaFunction;
import dan200.computercraft.core.Logging;
import dan200.computercraft.core.methods.LuaMethod;
import dan200.computercraft.core.methods.MethodSupplier;
import dan200.computercraft.core.util.LuaUtil;
import org.jspecify.annotations.Nullable;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.squiddev.cobalt.*;

import java.nio.ByteBuffer;
import java.util.Arrays;
import java.util.Collection;
import java.util.IdentityHashMap;
import java.util.HashMap;
import java.util.Map;
import java.util.Objects;

/**
 * Shared interop helpers for the Cobalt-backed Lua runtime.
 *
 * This centralises method binding and value marshalling rules, so the core VM can delegate these responsibilities.
 */
final class CobaltScriptInterop {
    private static final Logger LOG = LoggerFactory.getLogger(CobaltScriptInterop.class);

    private static final LuaMethod FUNCTION_METHOD = (target, context, args) ->
        ((ILuaFunction) target).call(args);

    private final ILuaContext context;
    private final MethodSupplier<LuaMethod> luaMethods;

    CobaltScriptInterop(ILuaContext context, MethodSupplier<LuaMethod> luaMethods) {
        this.context = Objects.requireNonNull(context);
        this.luaMethods = Objects.requireNonNull(luaMethods);
    }

    boolean makeLuaObject(Object object, LuaTable table) {
        return luaMethods.forEachMethod(object, (target, name, method, info) ->
            table.rawset(name, new ResultInterpreterFunction(this, method, target, context, name)));
    }

    LuaValue toValue(@Nullable Object object, @Nullable IdentityHashMap<Object, LuaValue> values) throws LuaError {
        if (object == null) return Constants.NIL;
        if (object instanceof Number num) return ValueFactory.valueOf(num.doubleValue());
        if (object instanceof Boolean bool) return ValueFactory.valueOf(bool);
        if (object instanceof String str) return ValueFactory.valueOf(str);
        if (object instanceof byte[] b) return ValueFactory.valueOf(Arrays.copyOf(b, b.length));
        if (object instanceof ByteBuffer b) {
            var bytes = new byte[b.remaining()];
            b.get(bytes);
            return ValueFactory.valueOf(bytes);
        }

        // We have a more complex object, which is possibly recursive. First look up our object in the lookup map,
        // and reuse it if present.
        if (values == null) values = new IdentityHashMap<>(1);
        var result = values.get(object);
        if (result != null) return result;

        if (object instanceof ILuaFunction) {
            var function = new ResultInterpreterFunction(this, FUNCTION_METHOD, object, context, object.toString());
            values.put(object, function);
            return function;
        }

        if (object instanceof IDynamicLuaObject) {
            var table = new LuaTable();
            makeLuaObject(object, table);
            values.put(object, table);
            return table;
        }

        // The following objects may be recursive. In these instances, we need to be careful to store the value *before*
        // recursing, to avoid stack overflows.

        if (object instanceof Map<?, ?> map) {
            // Don't share singleton values, and instead convert them to a new table.
            if (LuaUtil.isSingletonMap(map)) return new LuaTable();

            var table = new LuaTable();
            values.put(object, table);

            for (var pair : map.entrySet()) {
                var key = toValue(pair.getKey(), values);
                var value = toValue(pair.getValue(), values);
                if (!key.isNil() && !value.isNil()) table.rawset(key, value);
            }
            return table;
        }

        if (object instanceof Collection<?> objects) {
            // Don't share singleton values, and instead convert them to a new table.
            if (LuaUtil.isSingletonCollection(objects)) return new LuaTable();

            var table = new LuaTable(objects.size(), 0);
            values.put(object, table);

            var i = 0;
            for (var child : objects) table.rawset(++i, toValue(child, values));
            return table;
        }

        if (object instanceof Object[] objects) {
            var table = new LuaTable(objects.length, 0);
            values.put(object, table);

            for (var i = 0; i < objects.length; i++) table.rawset(i + 1, toValue(objects[i], values));
            return table;
        }

        var table = new LuaTable();
        if (makeLuaObject(object, table)) {
            values.put(object, table);
            return table;
        }

        LOG.warn(Logging.JAVA_ERROR, "Received unknown type '{}', returning nil.", object.getClass().getName());
        return Constants.NIL;
    }

    Varargs toValues(@Nullable Object @Nullable [] objects) throws LuaError {
        if (objects == null || objects.length == 0) return Constants.NONE;
        if (objects.length == 1) return toValue(objects[0], null);

        var result = new IdentityHashMap<Object, LuaValue>(0);
        var values = new LuaValue[objects.length];
        for (var i = 0; i < values.length; i++) {
            var object = objects[i];
            values[i] = toValue(object, result);
        }
        return ValueFactory.varargsOf(values);
    }

    @Nullable Object[] toObjects(Varargs values) {
        var count = values.count();
        var objects = new Object[count];
        for (var i = 0; i < count; i++) objects[i] = toObject(values.arg(i + 1), null);
        return objects;
    }

    static @Nullable Object toObject(LuaValue value, @Nullable IdentityHashMap<LuaValue, Object> objects) {
        return switch (value.type()) {
            case Constants.TNIL -> null;
            case Constants.TINT, Constants.TNUMBER -> value.toDouble();
            case Constants.TBOOLEAN -> value.toBoolean();
            case Constants.TSTRING -> value.toString();
            case Constants.TTABLE -> {
                if (objects == null) {
                    objects = new IdentityHashMap<>(1);
                } else {
                    var existing = objects.get(value);
                    if (existing != null) yield existing;
                }
                Map<Object, Object> table = new HashMap<>();
                objects.put(value, table);

                var luaTable = (LuaTable) value;

                // Convert all keys.
                var k = Constants.NIL;
                while (true) {
                    Varargs keyValue;
                    try {
                        keyValue = luaTable.next(k);
                    } catch (LuaError luaError) {
                        break;
                    }
                    k = keyValue.first();
                    if (k.isNil()) break;

                    var v = keyValue.arg(2);
                    var keyObject = toObject(k, objects);
                    var valueObject = toObject(v, objects);
                    if (keyObject != null && valueObject != null) table.put(keyObject, valueObject);
                }
                yield table;
            }
            default -> null;
        };
    }
}

