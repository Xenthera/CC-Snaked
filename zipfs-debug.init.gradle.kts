import java.nio.file.spi.FileSystemProvider
import org.gradle.api.initialization.Settings

gradle.settingsEvaluated { _: Settings ->
    val schemes = FileSystemProvider.installedProviders().map { it.scheme() }.sorted()
    println("zipfs-debug: installed FileSystemProvider schemes=$schemes")
}

