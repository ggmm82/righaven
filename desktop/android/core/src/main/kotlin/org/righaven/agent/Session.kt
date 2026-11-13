package org.righaven.agent

import org.json.JSONArray
import org.json.JSONObject
import java.io.Closeable
import java.io.InputStream
import java.io.OutputStream
import java.nio.ByteBuffer
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

/** The channel to the server (a WebSocket); the Android app gives OkHttp's, tests a fake. */
interface Channel {
    fun sendText(text: String): Boolean
    fun sendBinary(data: ByteArray): Boolean
    fun close(code: Int, reason: String)
}

/** A tunnel's end on the phone: a host of its private network. */
interface Stream : Closeable {
    val input: InputStream
    val output: OutputStream
}

/**
 * One connection of RigHaven Agent to the server, with the same protocol as the Windows agent:
 * hello, actions as request/result, tunnels as open/opened/close plus binary frames (4-byte stream
 * number, then the bytes). Actions run one at a time, as on a PC.
 */
class AgentSession(
    private val channel: Channel,
    private val platform: String,
    private val version: String,
    private val actions: List<String>,
    private val networks: () -> List<String>,
    private val handle: (String, Map<String, String>) -> Map<String, Any?>,
    private val openStream: (String) -> Stream,
    private val work: ExecutorService = Executors.newSingleThreadExecutor(),
    private val pumps: ExecutorService = Executors.newCachedThreadPool(),
) {
    private val streams = ConcurrentHashMap<Int, Stream>()

    fun hello() {
        channel.sendText(JSONObject(mapOf("type" to "hello", "platform" to platform, "version" to version,
            "actions" to JSONArray(actions), "networks" to JSONArray(networks()))).toString())
    }

    fun ping() = channel.sendText("{\"type\":\"ping\"}")

    fun onText(text: String) {
        val message = try { JSONObject(text) } catch (error: Exception) { return }
        when (message.optString("type")) {
            "request" -> {
                val id = message.optString("id")
                val action = message.optString("action")
                val args = message.optJSONObject("args")?.let { json -> json.keys().asSequence().associateWith { json.optString(it) } } ?: emptyMap()
                work.execute {
                    val result = try {
                        if (action !in actions) mapOf("error" to "unknown action $action") else handle(action, args)
                    } catch (error: Exception) {
                        mapOf("error" to (error.message ?: error.javaClass.simpleName))
                    }
                    channel.sendText(JSONObject(mapOf("type" to "result", "id" to id, "result" to toJson(result))).toString())
                }
            }
            "open" -> open(message.optInt("stream"), message.optString("target"))
            "close" -> streams.remove(message.optInt("stream"))?.close()
        }
    }

    fun onBinary(data: ByteArray) {
        if (data.size < 4) return
        val number = ByteBuffer.wrap(data, 0, 4).int
        val stream = streams[number] ?: return
        try {
            stream.output.write(data, 4, data.size - 4)
            stream.output.flush()
        } catch (error: Exception) {
            closeStream(number, error.message)
        }
    }

    fun closeAll() {
        streams.keys.toList().forEach { streams.remove(it)?.close() }
        work.shutdownNow()
        pumps.shutdownNow()
    }

    private fun open(number: Int, target: String) {
        pumps.execute {
            val stream = try {
                // COM ports exist only on a PC: a phone carries hosts of its network and its
                // Bluetooth devices as byte channels (ble:ADDRESS[/service/write/notify]).
                when {
                    target.startsWith("tcp:") -> openStream(target.removePrefix("tcp:"))
                    target.startsWith("ble:") -> openStream(target)
                    else -> throw IllegalArgumentException("only devices of this phone's network or Bluetooth")
                }
            } catch (error: Exception) {
                channel.sendText(JSONObject(mapOf("type" to "close", "stream" to number, "error" to (error.message ?: "refused"))).toString())
                return@execute
            }
            streams[number] = stream
            channel.sendText(JSONObject(mapOf("type" to "opened", "stream" to number)).toString())
            val buffer = ByteArray(32768)
            try {
                while (true) {
                    val size = stream.input.read(buffer)
                    if (size < 0) break
                    if (size > 0 && !channel.sendBinary(ByteBuffer.allocate(4 + size).putInt(number).put(buffer, 0, size).array())) break
                }
            } catch (error: Exception) {
                // the device or the phone closed the connection
            }
            closeStream(number, null)
        }
    }

    private fun closeStream(number: Int, error: String?) {
        val stream = streams.remove(number) ?: return
        stream.close()
        channel.sendText(JSONObject(mapOf("type" to "close", "stream" to number) + (error?.let { mapOf("error" to it) } ?: emptyMap())).toString())
    }

    companion object {
        fun toJson(value: Any?): Any = when (value) {
            null -> JSONObject.NULL
            is Map<*, *> -> JSONObject().apply { value.forEach { (k, v) -> put(k.toString(), toJson(v)) } }
            is Iterable<*> -> JSONArray().apply { value.forEach { put(toJson(it)) } }
            is Array<*> -> JSONArray().apply { value.forEach { put(toJson(it)) } }
            else -> value
        }
    }
}

/** Pairing: the code typed by the owner becomes this phone's own access. */
object Pairing {
    fun server(value: String): String {
        val trimmed = value.trim().trimEnd('/')
        return if (trimmed.isEmpty() || trimmed.startsWith("http://") || trimmed.startsWith("https://")) trimmed else "https://$trimmed"
    }

    fun request(code: String, version: String): String {
        require(Regex("^[A-Za-z0-9-]{4,20}$").matches(code.trim())) { "The pairing code is not valid: copy it from the server's Connected PCs panel." }
        return JSONObject(mapOf("code" to code.trim(), "platform" to "android", "version" to version)).toString()
    }

    data class Paired(val agent: String, val token: String, val name: String)

    fun answer(body: String): Paired {
        val value = JSONObject(body)
        val token = value.optString("token")
        require(token.startsWith("rha_")) { "The server refused the pairing." }
        return Paired(value.optString("agent"), token, value.optString("name"))
    }
}
