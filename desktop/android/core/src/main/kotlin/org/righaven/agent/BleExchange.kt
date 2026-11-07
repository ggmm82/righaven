package org.righaven.agent

/**
 * A Bluetooth LE exchange: commands written one after the other in one connection while the
 * device's notifications are collected (OBD-II adapters and serial bridges answer only that way).
 * Same rules as RigHaven Agent for Windows; the server sends it only after the owner's approval,
 * or for the fixed read-only OBD-II requests.
 */
data class BleExchange(val service: String, val characteristic: String, val notify: String, val commands: List<ByteArray>,
                       val until: Int, val waitMillis: Long) {
    /** Whether what was received so far is a whole answer. */
    fun complete(received: ByteArray, quietMillis: Long): Boolean =
        if (until >= 0) received.any { it.toInt() and 0xff == until } else received.isNotEmpty() && quietMillis > 500

    companion object {
        const val MAX = 16
        private val uuid = Regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
        private val bytes = Regex("^([0-9a-f]{2}){1,64}$")

        fun parse(args: Map<String, String>): BleExchange {
            val service = args["service"].orEmpty()
            val characteristic = args["characteristic"].orEmpty()
            val notify = args["notify"].orEmpty()
            require(uuid.matches(service) && uuid.matches(characteristic) && (notify.isEmpty() || uuid.matches(notify))) {
                "service and characteristics must be UUIDs"
            }
            val commands = args["commands"].orEmpty().lowercase().split(',')
            require(commands.size in 1..MAX) { "an exchange sends from 1 to $MAX commands" }
            require(commands.all(bytes::matches)) { "each command must be hexadecimal bytes (at most 64)" }
            val until = args["until"].orEmpty().lowercase()
            require(until.isEmpty() || Regex("^[0-9a-f]{2}$").matches(until)) { "until must be one hexadecimal byte" }
            val wait = args["wait"].orEmpty().ifEmpty { "3000" }.toLongOrNull()
            require(wait != null && wait in 200..10000) { "wait must be from 200 to 10000 milliseconds" }
            return BleExchange(service.lowercase(), characteristic.lowercase(), notify.lowercase(),
                commands.map { command -> command.chunked(2).map { it.toInt(16).toByte() }.toByteArray() },
                if (until.isEmpty()) -1 else until.toInt(16), wait)
        }
    }
}
