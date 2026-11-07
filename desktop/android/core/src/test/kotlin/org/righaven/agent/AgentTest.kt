package org.righaven.agent

import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.io.PipedInputStream
import java.io.PipedOutputStream
import java.net.InetAddress
import java.nio.ByteBuffer
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class FakeChannel : Channel {
    val texts = LinkedBlockingQueue<JSONObject>()
    val binaries = LinkedBlockingQueue<ByteArray>()
    override fun sendText(text: String): Boolean { texts.put(JSONObject(text)); return true }
    override fun sendBinary(data: ByteArray): Boolean { binaries.put(data); return true }
    override fun close(code: Int, reason: String) {}
    fun next(): JSONObject = texts.poll(5, TimeUnit.SECONDS) ?: error("nothing sent")
}

class AgentTest {
    private fun ip(text: String) = InetAddress.getByName(text)

    @Test
    fun `hello, actions and tunnels follow the agent protocol`() {
        val channel = FakeChannel()
        val toDevice = ByteArrayOutputStream()
        val fromDevice = PipedOutputStream()
        val deviceInput = PipedInputStream(fromDevice)
        val opened = mutableListOf<String>()
        val session = AgentSession(channel, "android", "1.2.0", listOf("net-scan", "tcp-check"), { listOf("192.168.1.0/24") },
            handle = { action, args -> mapOf("action" to action, "network" to args["network"], "devices" to listOf(mapOf("address" to "192.168.1.44", "ports" to listOf(6668)))) },
            openStream = { target ->
                opened += target
                object : Stream {
                    override val input: InputStream = deviceInput
                    override val output: OutputStream = toDevice
                    override fun close() = fromDevice.close()
                }
            })
        session.hello()
        val hello = channel.next()
        assertEquals(listOf("hello", "android"), listOf(hello.getString("type"), hello.getString("platform")))
        assertEquals("192.168.1.0/24", hello.getJSONArray("networks").getString(0))

        session.onText("""{"type":"request","id":"j1","action":"net-scan","args":{"network":"192.168.1.0/24"}}""")
        val result = channel.next()
        assertEquals("j1", result.getString("id"))
        assertEquals(6668, result.getJSONObject("result").getJSONArray("devices").getJSONObject(0).getJSONArray("ports").getInt(0))
        session.onText("""{"type":"request","id":"j2","action":"wifi-provision","args":{}}""")
        assertTrue(channel.next().getJSONObject("result").getString("error").contains("unknown action"))

        session.onText("""{"type":"open","stream":7,"target":"com:COM5"}""")
        assertEquals("close", channel.next().getString("type"))  // no COM ports on a phone
        session.onText("""{"type":"open","stream":3,"target":"tcp:192.168.1.44:6668"}""")
        assertEquals("opened", channel.next().getString("type"))
        assertEquals(listOf("192.168.1.44:6668"), opened)
        session.onBinary(ByteBuffer.allocate(6).putInt(3).put("AT".toByteArray()).array())
        assertEquals("AT", toDevice.toString())
        fromDevice.write("OK".toByteArray()); fromDevice.flush()
        val frame = channel.binaries.poll(5, TimeUnit.SECONDS)!!
        assertEquals(3, ByteBuffer.wrap(frame).int)
        assertEquals("OK", String(frame, 4, frame.size - 4))
        fromDevice.close()
        val closed = channel.next()
        assertEquals(listOf("close", 3), listOf(closed.getString("type"), closed.getInt("stream")))
        session.closeAll()
    }

    @Test
    fun `tunnels reach only the private network of the phone`() {
        val names = mapOf("sql01.office.local" to listOf(ip("10.255.255.1")), "rebind.example" to listOf(ip("10.0.0.5"), ip("8.8.8.8")))
        val dial = HomeDial(resolve = { names[it] ?: (if (it.first().isDigit()) listOf(ip(it)) else throw IOException("unknown")) },
            connect = { address, _ -> throw IOException("dialled ${address.address.hostAddress}") })
        for (target in listOf("8.8.8.8:53", "127.0.0.1:1433", "rebind.example:1433", "unknown.local:1433", "no-port")) {
            val error = assertFailsWith<Exception> { dial.open(target) }
            assertTrue(!error.message.orEmpty().startsWith("dialled"), "$target must be refused before dialling: ${error.message}")
        }
        assertEquals("dialled 10.255.255.1", assertFailsWith<IOException> { dial.open("sql01.office.local:1433") }.message)
    }

    @Test
    fun `the network search is bounded to private networks and reports what answers`() {
        val scan = NetworkScan(dial = { host, port -> (host == "192.168.1.44" && port in setOf(80, 6668)) || (host == "192.168.1.7" && port == 1883) },
            page = { _, _ -> "Server: Tuya" }, name = { if (it == "192.168.1.7") "broker.lan" else "" })
        val devices = scan.scan("192.168.1.0/24")["devices"] as List<*>
        assertEquals(listOf("192.168.1.7", "192.168.1.44"), devices.map { (it as Map<*, *>)["address"] })
        assertEquals(listOf(80, 6668), (devices[1] as Map<*, *>)["ports"])
        assertEquals("broker.lan", (devices[0] as Map<*, *>)["name"])
        assertEquals("Server: Tuya", (devices[1] as Map<*, *>)["page"])
        for (wrong in listOf("8.8.8.0/24", "192.168.0.0/16", "10.0.0.0", "x")) assertFailsWith<IllegalArgumentException> { scan.parse(wrong) }
        assertEquals("192.168.1.0/24", PrivateNetwork.cidr(ip("192.168.1.37"), 24))
        assertEquals(null, PrivateNetwork.cidr(ip("8.8.8.8"), 24))
    }

    @Test
    fun `pairing and printable values`() {
        assertEquals("https://righaven.example.org", Pairing.server(" righaven.example.org/ "))
        assertEquals("android", JSONObject(Pairing.request("ABCDE-FGHJK", "1.2.0")).getString("platform"))
        assertFailsWith<IllegalArgumentException> { Pairing.request("x y", "1") }
        assertEquals("rha_x", Pairing.answer("""{"agent":"ag_1","token":"rha_x","name":"Telefono"}""").token)
        assertFailsWith<IllegalArgumentException> { Pairing.answer("""{"detail":"no"}""") }
        assertEquals("LED", printable("4c454400"))
        assertEquals("", printable("ff00"))
    }

}

class ActivityLogTest {
    @Test
    fun `the log keeps the latest lines, newest first, with outcomes and durations`() {
        val file = kotlin.io.path.createTempFile().toFile()
        var clock = 0L
        val log = ActivityLog(file, max = 5, now = { clock })
        log.add("Collegato a https://righaven.example.org")
        val result = log.action("net-scan", "192.168.1.0/24") { clock += 45_000; mapOf("devices" to listOf(1, 2)) }
        assertEquals(2, (result["devices"] as List<*>).size)
        log.action("ble-inspect", "AA:BB") { mapOf("error" to "Il dispositivo si è scollegato") }
        assertFailsWith<IllegalStateException> { log.action("wifi-scan", "") { throw IllegalStateException("permesso negato") } }
        val lines = log.lines()
        assertEquals(5, lines.size)  // the oldest («Collegato…», «→ net-scan») are gone
        assertTrue(lines[0].endsWith("✗ wifi-scan · permesso negato"), lines[0])
        assertTrue(lines.any { it.endsWith("✓ net-scan · 45.0 s · 2 dispositivi") }, lines.toString())
        assertTrue(lines.any { it.contains("✗ ble-inspect") && it.endsWith("Il dispositivo si è scollegato") }, lines.toString())
        assertEquals(lines, ActivityLog(file, max = 5).lines())  // kept on the phone
        log.clear()
        assertEquals(emptyList<String>(), log.lines())
    }
}
