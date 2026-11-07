package org.righaven.agent

import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * What the agent did on this phone, kept on the phone: connections to the server and why they
 * ended, each action asked with its outcome and duration, tunnels, errors. Readable from the app
 * even when the server does not answer. At most [max] lines; the oldest go first.
 */
class ActivityLog(private val file: File, private val max: Int = 300, private val now: () -> Long = System::currentTimeMillis) {
    private val format = SimpleDateFormat("dd/MM HH:mm:ss", Locale.ROOT)

    @Synchronized
    fun add(text: String) {
        val line = format.format(Date(now())) + "  " + text.replace('\n', ' ').take(300)
        val lines = (read() + line).takeLast(max)
        file.parentFile?.mkdirs()
        file.writeText(lines.joinToString("\n", postfix = "\n"))
    }

    /** Newest first. */
    @Synchronized
    fun lines(): List<String> = read().asReversed()

    @Synchronized
    fun clear() {
        file.delete()
    }

    private fun read(): List<String> = if (file.isFile) file.readLines().filter { it.isNotBlank() } else emptyList()

    /** Runs an action and writes its outcome: the result's "error" or an exception count as failures. */
    fun <T> action(name: String, detail: String, work: () -> T): T {
        val started = now()
        add("→ $name ${detail.take(80)}".trimEnd())
        try {
            val result = work()
            val error = (result as? Map<*, *>)?.get("error")?.toString()
            val seconds = "%.1f s".format(Locale.ROOT, (now() - started) / 1000.0)
            add(if (error != null) "✗ $name · $seconds · $error" else "✓ $name · $seconds" + summary(result))
            return result
        } catch (error: Exception) {
            add("✗ $name · ${error.message ?: error.javaClass.simpleName}")
            throw error
        }
    }

    private fun summary(result: Any?): String {
        val map = result as? Map<*, *> ?: return ""
        val devices = map["devices"] as? Collection<*> ?: (map["networks"] as? Collection<*>) ?: return ""
        return " · ${devices.size} " + if (map.containsKey("devices")) "dispositivi" else "reti"
    }
}
