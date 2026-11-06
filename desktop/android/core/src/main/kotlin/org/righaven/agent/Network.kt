package org.righaven.agent

import java.io.IOException
import java.net.HttpURLConnection
import java.net.Inet4Address
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.Socket
import java.net.URL
import java.util.concurrent.Callable
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/** The phone's private networks: tunnels and searches never reach the internet. */
object PrivateNetwork {
    fun isPrivate(address: InetAddress): Boolean {
        if (address.isSiteLocalAddress || address.isLinkLocalAddress) return true
        val bytes = address.address
        return bytes.size == 16 && (bytes[0].toInt() and 0xfe) == 0xfc // IPv6 unique local fc00::/7
    }

    /** "192.168.1.0/24" for a private IPv4 address and its prefix length. */
    fun cidr(address: InetAddress, prefix: Int): String? {
        if (address !is Inet4Address || !isPrivate(address) || prefix !in 16..30) return null
        val value = address.address.fold(0L) { acc, b -> (acc shl 8) or (b.toLong() and 0xff) }
        val mask = (0xffffffffL shl (32 - prefix)) and 0xffffffffL
        val base = value and mask
        return "${(base shr 24) and 0xff}.${(base shr 16) and 0xff}.${(base shr 8) and 0xff}.${base and 0xff}/$prefix"
    }
}

/** Opens host:port of the phone's private network: a private IP, or a name whose addresses are all private. */
class HomeDial(
    private val resolve: (String) -> List<InetAddress> = { InetAddress.getAllByName(it).toList() },
    private val connect: (InetSocketAddress, Int) -> Socket = { address, timeout -> Socket().apply { this.connect(address, timeout) } },
) {
    fun open(target: String, timeoutMs: Int = 10_000): Socket {
        val separator = target.lastIndexOf(':')
        require(separator > 0) { "address: host:port" }
        val host = target.substring(0, separator).removePrefix("[").removeSuffix("]")
        val port = target.substring(separator + 1).toIntOrNull()
        require(port != null && port in 1..65535 && host.isNotEmpty()) { "address: host:port" }
        val addresses = try {
            resolve(host)
        } catch (error: IOException) {
            throw IOException("$host: name not resolved on this phone")
        }
        if (addresses.isEmpty()) throw IOException("$host: name not resolved on this phone")
        addresses.firstOrNull { !PrivateNetwork.isPrivate(it) }?.let {
            throw IOException("$host is not an address of this phone's private network (${it.hostAddress})")
        }
        var last: IOException? = null
        for (address in addresses) {
            try {
                return connect(InetSocketAddress(address, port), timeoutMs)
            } catch (error: IOException) {
                last = error
            }
        }
        throw last ?: IOException("$target does not answer")
    }
}

/** The search of the phone's network: the usual ports of devices, TVs and phones, as RigHaven Agent for Windows does. */
class NetworkScan(
    private val dial: (String, Int) -> Boolean = { host, port ->
        try {
            Socket().use { it.connect(InetSocketAddress(host, port), 600); true }
        } catch (error: IOException) {
            false
        }
    },
    private val page: (String, Int) -> String = ::homePage,
    private val name: (String) -> String = { address ->
        val host = InetAddress.getByName(address).canonicalHostName
        if (host == address) "" else host.removeSuffix(".")
    },
) {
    companion object {
        val PORTS = listOf(80, 8080, 443, 1883, 8883, 502, 5555, 6053, 6668, 8008, 8009, 6466, 8001, 8002, 3000, 3001, 7000, 62078, 554)
    }

    fun scan(network: String): Map<String, Any?> {
        val (base, size) = parse(network)
        val addresses = (0 until size).filter { size <= 2 || (it != 0 && it != size - 1) }.map { format(base + it) }
        val pool = Executors.newFixedThreadPool(64)
        try {
            val answers = addresses.flatMap { address -> PORTS.map { port -> Triple(address, port, pool.submit(Callable { dial(address, port) })) } }
            val open = answers.filter { it.third.get(30, TimeUnit.SECONDS) }.groupBy({ it.first }, { it.second })
            val devices = open.entries.sortedBy { parse(it.key + "/32").first }.map { (address, ports) ->
                val sorted = ports.sorted()
                val web = listOf(80, 8080).firstOrNull { it in sorted }
                linkedMapOf<String, Any?>("address" to address, "ports" to sorted).apply {
                    runCatching { name(address) }.getOrNull()?.takeIf { it.isNotEmpty() }?.let { put("name", it) }
                    web?.let { port -> runCatching { page(address, port) }.getOrNull()?.takeIf { it.isNotBlank() }?.let { put("page", it) } }
                }
            }
            return mapOf("devices" to devices)
        } finally {
            pool.shutdownNow()
        }
    }

    /** First address and count of a private IPv4 network of at most 4096 addresses. */
    fun parse(network: String): Pair<Long, Int> {
        val parts = network.split("/")
        val prefix = parts.getOrNull(1)?.toIntOrNull()
        val octets = parts[0].split(".").map { it.toIntOrNull() }
        require(parts.size == 2 && prefix != null && octets.size == 4 && octets.all { it != null && it in 0..255 }) {
            "a private IPv4 network, for example 192.168.1.0/24"
        }
        require(prefix in 20..32) { "network too large: at most 4096 addresses" }
        val value = octets.fold(0L) { acc, b -> (acc shl 8) or b!!.toLong() }
        require(PrivateNetwork.isPrivate(InetAddress.getByAddress(octets.map { it!!.toByte() }.toByteArray()))) {
            "a private IPv4 network, for example 192.168.1.0/24"
        }
        val mask = (0xffffffffL shl (32 - prefix)) and 0xffffffffL
        return Pair(value and mask, 1 shl (32 - prefix))
    }

    private fun format(value: Long) = "${(value shr 24) and 0xff}.${(value shr 16) and 0xff}.${(value shr 8) and 0xff}.${value and 0xff}"
}

fun homePage(address: String, port: Int): String {
    val connection = URL("http://$address:$port/").openConnection() as HttpURLConnection
    connection.connectTimeout = 2000
    connection.readTimeout = 2000
    return try {
        val body = connection.inputStream.use { stream ->
            val buffer = ByteArray(8192)
            var size = 0
            while (size < buffer.size) {
                val read = stream.read(buffer, size, buffer.size - size)
                if (read < 0) break
                size += read
            }
            String(buffer, 0, size)
        }
        (connection.getHeaderField("Server") ?: "") + " " + body
    } catch (error: IOException) {
        ""
    } finally {
        connection.disconnect()
    }
}

/** A value read from a device shown as text when it is printable text (a name, a firmware version). */
fun printable(hex: String): String {
    val builder = StringBuilder()
    var i = 0
    while (i + 1 < hex.length) {
        val byte = hex.substring(i, i + 2).toIntOrNull(16) ?: return ""
        if (byte == 0 && i + 2 == hex.length) break
        if (byte < 0x20 || byte > 0x7e) return ""
        builder.append(byte.toChar())
        i += 2
    }
    return builder.toString()
}
