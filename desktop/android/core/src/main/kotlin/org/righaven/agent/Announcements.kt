package org.righaven.agent

import java.io.ByteArrayOutputStream
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.SocketTimeoutException
import java.nio.ByteBuffer

/**
 * «Listen to the network» on the phone: the devices that announce themselves (mDNS/Bonjour and
 * SSDP/UPnP), even when no port of the search answers. Same result as RigHaven Agent for Windows:
 * devices with address, names, services, server and kinds. Only replies from private addresses.
 */
object Mdns {
    val TYPES = listOf("_services._dns-sd._udp", "_googlecast._tcp", "_airplay._tcp", "_raop._tcp", "_spotify-connect._tcp", "_http._tcp",
        "_hap._tcp", "_ipp._tcp", "_printer._tcp", "_esphomelib._tcp", "_shelly._tcp", "_home-assistant._tcp", "_sonos._tcp",
        "_amzn-wplay._tcp", "_matter._tcp", "_matterc._udp", "_workstation._tcp", "_smb._tcp", "_companion-link._tcp", "_androidtvremote2._tcp")

    /** A query for the usual services, asking unicast answers (sent from an ordinary port). */
    fun query(): ByteArray {
        val out = ByteArrayOutputStream()
        out.write(byteArrayOf(0, 0, 0, 0, 0, TYPES.size.toByte(), 0, 0, 0, 0, 0, 0))
        for (type in TYPES) {
            for (label in "$type.local".split('.')) {
                out.write(label.length)
                out.write(label.toByteArray())
            }
            out.write(byteArrayOf(0, 0, 12, 0x80.toByte(), 1)) // PTR, class IN with the unicast-response bit
        }
        return out.toByteArray()
    }

    data class Answers(val names: MutableSet<String> = linkedSetOf(), val services: MutableSet<String> = linkedSetOf())

    /** Names and services announced in one mDNS message (PTR, SRV and A records). */
    fun parse(data: ByteArray): Answers {
        val answers = Answers()
        val buffer = ByteBuffer.wrap(data)
        if (data.size < 12) return answers
        val questions = buffer.getShort(4).toInt() and 0xffff
        val records = (buffer.getShort(6).toInt() and 0xffff) + (buffer.getShort(8).toInt() and 0xffff) + (buffer.getShort(10).toInt() and 0xffff)
        var offset = 12
        repeat(questions) { offset = name(data, offset).second + 4 }
        repeat(records) {
            val (owner, end) = name(data, offset)
            if (end + 10 > data.size) return answers
            val type = buffer.getShort(end).toInt() and 0xffff
            val length = buffer.getShort(end + 8).toInt() and 0xffff
            val start = end + 10
            if (start + length > data.size) return answers
            when (type) {
                12 -> { // PTR: a service type, or an instance of a type
                    val target = name(data, start).first
                    if (owner.startsWith("_services._dns-sd")) answers.services += target.removeSuffix(".local")
                    else {
                        answers.services += owner.removeSuffix(".local")
                        target.removeSuffix("." + owner).takeIf { it.isNotBlank() && it != target }?.let { answers.names += it }
                    }
                }
                33 -> name(data, start + 6).first.removeSuffix(".local").takeIf { it.isNotBlank() }?.let { answers.names += it } // SRV target host
                1 -> owner.removeSuffix(".local").takeIf { it.isNotBlank() }?.let { answers.names += it } // A: the host's own name
            }
            offset = start + length
        }
        return answers
    }

    /** A DNS name at [start] (with compression pointers) and the offset after it. */
    fun name(data: ByteArray, start: Int): Pair<String, Int> {
        val labels = mutableListOf<String>()
        var offset = start
        var end = -1
        var jumps = 0
        while (offset < data.size) {
            val length = data[offset].toInt() and 0xff
            when {
                length == 0 -> { if (end < 0) end = offset + 1; break }
                length and 0xc0 == 0xc0 -> {
                    if (offset + 1 >= data.size || ++jumps > 20) break
                    if (end < 0) end = offset + 2
                    offset = ((length and 0x3f) shl 8) or (data[offset + 1].toInt() and 0xff)
                }
                else -> {
                    if (offset + 1 + length > data.size) break
                    labels += String(data, offset + 1, length, Charsets.UTF_8)
                    offset += 1 + length
                }
            }
        }
        return labels.joinToString(".") to (if (end < 0) data.size else end)
    }
}

object Ssdp {
    val SEARCH = ("M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: \"ssdp:discover\"\r\nMX: 2\r\nST: ssdp:all\r\n\r\n").toByteArray()

    /** The headers of an SSDP answer (lower-case names). */
    fun headers(text: String): Map<String, String> = text.split("\r\n", "\n").drop(1).mapNotNull { line ->
        val colon = line.indexOf(':')
        if (colon <= 0) null else line.substring(0, colon).trim().lowercase() to line.substring(colon + 1).trim()
    }.toMap()

    /** A UPnP device type or service in a readable form (urn:schemas-upnp-org:device:MediaRenderer:1 → MediaRenderer). */
    fun kind(target: String): String = target.split(':').let { if (it.size >= 4 && it[0] == "urn") it[it.size - 2] else target }

    /** The friendly name in a UPnP description document. */
    fun friendlyName(xml: String): String = Regex("<friendlyName>([^<]{1,120})</friendlyName>").find(xml)?.groupValues?.get(1)?.trim().orEmpty()
}

class NetListen(
    private val socket: () -> DatagramSocket = { DatagramSocket() },
    private val description: (String) -> String = ::homePageXml,
) {
    fun listen(seconds: Int = 6): Map<String, Any?> {
        val devices = LinkedHashMap<String, MutableMap<String, Any?>>()
        fun device(address: String) = devices.getOrPut(address) {
            linkedMapOf("address" to address, "names" to linkedSetOf<String>(), "services" to linkedSetOf<String>(), "server" to "", "kinds" to linkedSetOf<String>())
        }
        val locations = mutableMapOf<String, String>()
        socket().use { udp ->
            udp.soTimeout = 300
            val query = Mdns.query()
            udp.send(DatagramPacket(query, query.size, InetAddress.getByName("224.0.0.251"), 5353))
            udp.send(DatagramPacket(Ssdp.SEARCH, Ssdp.SEARCH.size, InetAddress.getByName("239.255.255.250"), 1900))
            val deadline = System.currentTimeMillis() + seconds * 1000L
            val buffer = ByteArray(9000)
            while (System.currentTimeMillis() < deadline) {
                val packet = DatagramPacket(buffer, buffer.size)
                try { udp.receive(packet) } catch (timeout: SocketTimeoutException) { continue }
                if (!PrivateNetwork.isPrivate(packet.address)) continue
                val address = packet.address.hostAddress ?: continue
                val data = packet.data.copyOf(packet.length)
                if (packet.port == 5353) {
                    val answers = Mdns.parse(data)
                    if (answers.names.isEmpty() && answers.services.isEmpty()) continue
                    val entry = device(address)
                    @Suppress("UNCHECKED_CAST") (entry["names"] as MutableSet<String>).addAll(answers.names)
                    @Suppress("UNCHECKED_CAST") (entry["services"] as MutableSet<String>).addAll(answers.services.filter { it != "_services._dns-sd._udp" })
                    @Suppress("UNCHECKED_CAST") (entry["kinds"] as MutableSet<String>).add("mDNS")
                } else {
                    val headers = Ssdp.headers(String(data, Charsets.UTF_8))
                    if (headers.isEmpty()) continue
                    val entry = device(address)
                    if ((entry["server"] as String).isEmpty()) entry["server"] = headers["server"].orEmpty().take(120)
                    headers["st"]?.let { @Suppress("UNCHECKED_CAST") (entry["services"] as MutableSet<String>).add(Ssdp.kind(it)) }
                    @Suppress("UNCHECKED_CAST") (entry["kinds"] as MutableSet<String>).add("UPnP")
                    headers["location"]?.let { locations.putIfAbsent(address, it) }
                }
            }
        }
        for ((address, location) in locations) { // the UPnP device's own name, from its description on the private network
            val host = Regex("^https?://([^/:]+)").find(location)?.groupValues?.get(1) ?: continue
            if (host != address) continue
            val name = runCatching { Ssdp.friendlyName(description(location)) }.getOrDefault("")
            @Suppress("UNCHECKED_CAST") if (name.isNotEmpty()) (devices[address]!!["names"] as MutableSet<String>).add(name)
        }
        return mapOf("devices" to devices.values.map { entry ->
            entry.mapValues { (_, value) -> if (value is Set<*>) value.toList() else value }
        }.sortedBy { (it["address"] as String).split('.').fold(0L) { acc, part -> acc * 256 + (part.toLongOrNull() ?: 0) } })
    }
}

fun homePageXml(url: String): String {
    val connection = java.net.URL(url).openConnection() as java.net.HttpURLConnection
    connection.connectTimeout = 2000
    connection.readTimeout = 2000
    return try {
        connection.inputStream.use { stream -> String(stream.readNBytes(32768), Charsets.UTF_8) }
    } finally {
        connection.disconnect()
    }
}
