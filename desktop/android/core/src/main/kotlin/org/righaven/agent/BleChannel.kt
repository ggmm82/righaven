package org.righaven.agent

/**
 * A Bluetooth device as a byte channel, the same for every protocol (same rules as RigHaven Agent
 * for Windows): ble:ADDRESS[/service/write/notify]. A classic device is reached through its serial
 * profile (RFCOMM); a Bluetooth LE device through one write characteristic and the notifications of
 * one characteristic. The phone never reads the bytes: protocols belong to the tools that open the
 * channel. One client per device at a time.
 */
data class BleChannel(val address: String, val service: String, val write: String, val notify: String) {
    companion object {
        private val pattern = Regex("^ble:([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})(?:/([0-9a-fA-F-]{36})/([0-9a-fA-F-]{36})/([0-9a-fA-F-]{36}))?$")
        private val uuid = Regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

        /** Serial-over-BLE profiles of common modules and adapters: service, write, notify. */
        val PROFILES = listOf(
            listOf("0000fff0-0000-1000-8000-00805f9b34fb", "0000fff2-0000-1000-8000-00805f9b34fb", "0000fff1-0000-1000-8000-00805f9b34fb"),
            listOf("0000ffe0-0000-1000-8000-00805f9b34fb", "0000ffe1-0000-1000-8000-00805f9b34fb", "0000ffe1-0000-1000-8000-00805f9b34fb"),
            listOf("000018f0-0000-1000-8000-00805f9b34fb", "00002af1-0000-1000-8000-00805f9b34fb", "00002af0-0000-1000-8000-00805f9b34fb"),
            listOf("6e400001-b5a3-f393-e0a9-e50e24dcca9e", "6e400002-b5a3-f393-e0a9-e50e24dcca9e", "6e400003-b5a3-f393-e0a9-e50e24dcca9e"),
            listOf("e7810a71-73ae-499d-8c15-faa9aef0c3f2", "bef8d6c9-9c21-4c9e-b632-bd58c1009f9f", "bef8d6c9-9c21-4c9e-b632-bd58c1009f9f"))

        /** The serial port profile of classic devices. */
        const val SPP = "00001101-0000-1000-8000-00805f9b34fb"

        fun parse(target: String): BleChannel {
            val match = pattern.matchEntire(target) ?: throw IllegalArgumentException("Bluetooth target: ble:AA:BB:CC:DD:EE:FF[/service/write/notify]")
            val (address, service, write, notify) = match.destructured
            require(service.isEmpty() || listOf(service, write, notify).all(uuid::matches)) { "the channel profile needs three UUIDs" }
            return BleChannel(address.uppercase(), service.lowercase(), write.lowercase(), notify.lowercase())
        }

        /**
         * The channel of a device from its services (service → characteristics with their properties):
         * the profile given, a known serial profile, or the first service that takes writes and notifies.
         */
        fun choose(channel: BleChannel, services: Map<String, Map<String, Set<String>>>): Triple<String, String, String> {
            if (channel.service.isNotEmpty()) return Triple(channel.service, channel.write, channel.notify)
            PROFILES.firstOrNull { (service, write, notify) -> services[service]?.keys?.containsAll(listOf(write, notify)) == true }
                ?.let { return Triple(it[0], it[1], it[2]) }
            for ((service, characteristics) in services) {
                if (service.startsWith("000018") && service.endsWith("-0000-1000-8000-00805f9b34fb") && !service.startsWith("000018f0")) continue
                val write = characteristics.entries.firstOrNull { it.value.any { p -> p == "Write" || p == "WriteWithoutResponse" } }?.key
                val notify = characteristics.entries.firstOrNull { it.value.any { p -> p == "Notify" || p == "Indicate" } }?.key
                if (write != null && notify != null) return Triple(service, write, notify)
            }
            throw IllegalStateException("no service of this device takes writes and notifies: name the channel profile (service, write, notify)")
        }
    }
}
