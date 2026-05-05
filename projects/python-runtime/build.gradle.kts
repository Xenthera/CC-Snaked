// SPDX-FileCopyrightText: 2026 The CC: Tweaked Developers
//
// SPDX-License-Identifier: MPL-2.0

import cc.tweaked.gradle.CCTweakedPlugin

plugins {
    `java-library`
    alias(libs.plugins.shadow)
}

// A standalone, plain-Java module that produces a single shaded jar containing GraalPy and its
// transitive runtime, so the in-game runtime classpath does not require Loom to walk the
// individual GraalPy artifacts (which previously failed during configuration).
java {
    toolchain { languageVersion = CCTweakedPlugin.JDK_VERSION }
    sourceCompatibility = CCTweakedPlugin.JAVA_VERSION
    targetCompatibility = CCTweakedPlugin.JAVA_VERSION
}

repositories {
    mavenCentral()
}

dependencies {
    api(libs.graalvmPolyglot)
    api(libs.graalpyPythonEmbedding)
}

// Some GraalPy transitive dependencies (e.g. org.graalvm.python:python) are POM-only
// aggregators. Shadow's default expansion mode tries to open every artifact as a zip, so we
// disable that and instead feed it the unpacked contents of each jar artifact ourselves.
val jarOnlyRuntime = configurations.runtimeClasspath.map { cc -> cc.filter { it.extension == "jar" } }

tasks.shadowJar {
    setProperty("configurations", emptyList<Configuration>())
    from(jarOnlyRuntime.map { files -> files.map { zipTree(it) } })
    mergeServiceFiles()
}

tasks.assemble {
    dependsOn(tasks.shadowJar)
}
