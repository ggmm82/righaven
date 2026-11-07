package org.righaven.agent.android

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.net.wifi.WifiManager
import android.os.Build
import org.righaven.agent.HomeDial
import org.righaven.agent.NetworkScan
import org.righaven.agent.PrivateNetwork
import org.righaven.agent.printable
import java.util.UUID
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit

/**
 * What this phone does for the server, with the same results as RigHaven Agent for Windows:
 * Bluetooth LE search and exploration (reads; writes only as approved by the owner on the server),
 * nearby Wi-Fi networks, the search of its network and whether a host of its network answers.
 */
class Actions(private val context: Context) {
    val names = listOf("bluetooth-scan", "ble-inspect", "ble-read", "ble-write", "wifi-scan", "net-scan", "tcp-check",
        "net-listen", "pc-devices", "nfc-read")

    fun handle(action: String, args: Map<String, String>): Map<String, Any?> = when (action) {
        "bluetooth-scan" -> bluetoothScan()
        "ble-inspect", "ble-read", "ble-write" -> gatt(action, args)
        "wifi-scan" -> wifiScan()
        "net-scan" -> NetworkScan().scan(args["network"].orEmpty())
        "tcp-check" -> HomeDial().open(args["target"].orEmpty(), 6000).use { mapOf("ok" to true, "address" to it.remoteSocketAddress.toString().removePrefix("/")) }
        "net-listen" -> listen()
        "pc-devices" -> PhoneDevices(context).list()
        "nfc-read" -> NfcBus.read(context)
        else -> mapOf("error" to "unknown action $action")
    }

    /** The phone's private networks, for the server's "search this network". */
    fun networks(): List<String> {
        val connectivity = context.getSystemService(ConnectivityManager::class.java) ?: return emptyList()
        val properties = connectivity.getLinkProperties(connectivity.activeNetwork) ?: return emptyList()
        return properties.linkAddresses.mapNotNull { PrivateNetwork.cidr(it.address, it.prefixLength) }.distinct()
    }

    /** Devices that announce themselves on the phone's Wi-Fi (mDNS/Bonjour, SSDP/UPnP). */
    private fun listen(): Map<String, Any?> {
        val wifi = context.applicationContext.getSystemService(WifiManager::class.java)
        val lock = wifi?.createMulticastLock("righaven-listen")?.apply { setReferenceCounted(false); acquire() }
        try {
            return org.righaven.agent.NetListen().listen(6)
        } finally {
            lock?.release()
        }
    }

    private fun granted(permission: String) = context.checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED

    private fun requireBluetooth() {
        val needed = if (Build.VERSION.SDK_INT >= 31) listOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
        else listOf(Manifest.permission.ACCESS_FINE_LOCATION)
        if (!needed.all(::granted)) throw IllegalStateException(tr("Consenti a RigHaven l’accesso al Bluetooth (dispositivi nelle vicinanze) nelle impostazioni del telefono",
            "Allow RigHaven to use Bluetooth (nearby devices) in the phone's settings"))
    }

    private fun adapter() = context.getSystemService(BluetoothManager::class.java)?.adapter?.takeIf { it.isEnabled }
        ?: throw IllegalStateException(tr("Il Bluetooth del telefono è spento", "The phone's Bluetooth is off"))

    @SuppressLint("MissingPermission")
    private fun bluetoothScan(): Map<String, Any?> {
        requireBluetooth()
        val adapter = adapter()
        val heard = LinkedHashMap<String, MutableMap<String, Any?>>()
        val callback = object : ScanCallback() {
            override fun onScanResult(callbackType: Int, result: ScanResult) {
                val record = result.scanRecord
                val entry = linkedMapOf<String, Any?>("name" to (record?.deviceName ?: result.device.name ?: ""), "address" to result.device.address,
                    "kind" to "ble", "paired" to (result.device.bondState == BluetoothDevice.BOND_BONDED), "signal" to result.rssi, "present" to true)
                record?.manufacturerSpecificData?.takeIf { it.size() > 0 }?.let { entry["company"] = "%04x".format(it.keyAt(0)) }
                record?.serviceData?.takeIf { it.isNotEmpty() }?.let { data ->
                    entry["service_data"] = data.entries.associate { (uuid, bytes) -> short(uuid.uuid) to hex(bytes) }
                }
                synchronized(heard) { heard[result.device.address] = entry }
            }
        }
        val scanner = adapter.bluetoothLeScanner ?: throw IllegalStateException(tr("Bluetooth LE non disponibile", "Bluetooth LE not available"))
        // Android drops a search for every device without a word while the screen is off, while
        // Location is off, or after five searches in 30 seconds: say so instead of an empty list.
        val warnings = mutableListOf<String>()
        if (context.getSystemService(android.os.PowerManager::class.java)?.isInteractive == false)
            warnings += tr("Schermo del telefono spento: Android blocca la ricerca dei dispositivi Bluetooth vicini. Accendi lo schermo e riprova.",
                "The phone's screen is off: Android blocks the search for nearby Bluetooth devices. Turn the screen on and try again.")
        if (context.getSystemService(android.location.LocationManager::class.java)?.let { Build.VERSION.SDK_INT >= 28 && !it.isLocationEnabled } == true)
            warnings += tr("Posizione del telefono spenta: con la posizione spenta molti telefoni non riportano i dispositivi Bluetooth vicini.",
                "The phone's Location is off: with it off many phones report no nearby Bluetooth devices.")
        if (context.getSystemService(android.os.PowerManager::class.java)?.isIgnoringBatteryOptimizations(context.packageName) == false)
            warnings += tr("Batteria ottimizzata per RigHaven: il telefono limita l’agente in background e la ricerca Bluetooth può non trovare nulla. Agente → Batteria → «Senza restrizioni».",
                "Battery optimized for RigHaven: the phone limits the agent in the background and the Bluetooth search may find nothing. Agent → Battery → “Unrestricted”.")
        if (!granted(Manifest.permission.ACCESS_FINE_LOCATION))
            warnings += tr("Posizione precisa non concessa a RigHaven: Android non riporta i dispositivi Bluetooth vicini. Impostazioni → App → RigHaven → Autorizzazioni → Posizione → «Usa posizione precisa».",
                "Precise location not granted to RigHaven: Android reports no nearby Bluetooth devices. Settings → Apps → RigHaven → Permissions → Location → “Use precise location”.")
        var failed = 0
        val watched = object : ScanCallback() {
            override fun onScanResult(callbackType: Int, result: ScanResult) = callback.onScanResult(callbackType, result)
            override fun onScanFailed(errorCode: Int) { failed = errorCode }
        }
        scanner.startScan(null, ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build(), watched)
        Thread.sleep(8000)
        scanner.stopScan(watched)
        if (failed != 0) warnings += when (failed) {
            ScanCallback.SCAN_FAILED_APPLICATION_REGISTRATION_FAILED, 6 /* SCANNING_TOO_FREQUENTLY */ ->
                tr("Troppe ricerche Bluetooth ravvicinate: Android ne permette cinque ogni 30 secondi. Riprova tra poco.",
                    "Too many Bluetooth searches in a row: Android allows five every 30 seconds. Try again shortly.")
            else -> tr("La ricerca Bluetooth del telefono non è partita (errore $failed)", "The phone's Bluetooth search did not start (error $failed)")
        }
        if (synchronized(heard) { heard.isEmpty() } && failed == 0 && warnings.isEmpty())
            warnings += tr("Nessun dispositivo Bluetooth sentito in 8 secondi. Se ce ne sono vicini, Android potrebbe aver limitato la ricerca (troppe ricerche ravvicinate): riprova tra 30 secondi.",
                "No Bluetooth device heard in 8 seconds. If some are nearby, Android may have limited the search (too many in a row): try again in 30 seconds.")
        val devices = synchronized(heard) { heard.values.toMutableList<Map<String, Any?>>() }
        for (device in adapter.bondedDevices.orEmpty()) {
            if (devices.none { it["address"] == device.address }) {
                devices += mapOf("name" to (device.name ?: ""), "address" to device.address, "paired" to true, "present" to false,
                    "kind" to if (device.type == BluetoothDevice.DEVICE_TYPE_CLASSIC) "classic" else "ble")
            }
        }
        return mapOf("devices" to devices, "warnings" to warnings)
    }

    @SuppressLint("MissingPermission")
    @Suppress("DEPRECATION")
    private fun gatt(action: String, args: Map<String, String>): Map<String, Any?> {
        requireBluetooth()
        val address = args["address"].orEmpty()
        require(BluetoothAdapterCheck.valid(address)) { "invalid Bluetooth address $address" }
        val events = LinkedBlockingQueue<Pair<String, Any?>>()
        val callback = object : BluetoothGattCallback() {
            override fun onConnectionStateChange(gatt: BluetoothGatt, status: Int, newState: Int) {
                events.put((if (newState == BluetoothProfile.STATE_CONNECTED) "connected" else "disconnected") to status)
            }
            override fun onServicesDiscovered(gatt: BluetoothGatt, status: Int) { events.put("services" to status) }
            override fun onCharacteristicRead(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic, value: ByteArray, status: Int) {
                events.put("read" to (if (status == BluetoothGatt.GATT_SUCCESS) value else null))
            }
            @Deprecated("Android 12 and earlier")
            override fun onCharacteristicRead(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic, status: Int) {
                if (Build.VERSION.SDK_INT < 33) events.put("read" to (if (status == BluetoothGatt.GATT_SUCCESS) characteristic.value else null))
            }
            override fun onCharacteristicWrite(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic, status: Int) {
                events.put("write" to status)
            }
        }
        fun await(kind: String, seconds: Long = 15): Any? {
            while (true) {
                val (name, value) = events.poll(seconds, TimeUnit.SECONDS) ?: throw IllegalStateException(
                    tr("Il dispositivo non risponde: avvicinalo al telefono e riprova", "The device does not answer: bring it near the phone and try again"))
                if (name == "disconnected") throw IllegalStateException(tr("Il dispositivo si è scollegato", "The device disconnected"))
                if (name == kind) return value
            }
        }
        val device = adapter().getRemoteDevice(address)
        val gatt = device.connectGatt(context, false, callback, BluetoothDevice.TRANSPORT_LE)
        try {
            await("connected", 20)
            gatt.discoverServices()
            await("services")
            fun characteristic(): BluetoothGattCharacteristic =
                gatt.getService(UUID.fromString(args["service"]))?.getCharacteristic(UUID.fromString(args["characteristic"]))
                    ?: throw IllegalStateException(tr("Servizio o caratteristica non presenti sul dispositivo", "Service or characteristic not on the device"))
            return when (action) {
                "ble-read" -> {
                    gatt.readCharacteristic(characteristic())
                    val value = hex(await("read") as? ByteArray ?: throw IllegalStateException("read refused"))
                    mapOf("value" to value, "text" to printable(value))
                }
                "ble-write" -> {
                    val value = args["value"].orEmpty()
                    require(Regex("^([0-9a-f]{2}){1,512}$").matches(value)) { "the value to write must be hexadecimal bytes (at most 512)" }
                    val target = characteristic()
                    val bytes = value.chunked(2).map { it.toInt(16).toByte() }.toByteArray()
                    if (Build.VERSION.SDK_INT >= 33) gatt.writeCharacteristic(target, bytes, BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT)
                    else { target.value = bytes; gatt.writeCharacteristic(target) }
                    val status = await("write") as Int
                    if (status != BluetoothGatt.GATT_SUCCESS) throw IllegalStateException("write refused ($status)")
                    mapOf("ok" to true)
                }
                else -> mapOf("name" to (device.name ?: ""), "services" to gatt.services.map { service ->
                    mapOf("uuid" to service.uuid.toString(), "characteristics" to service.characteristics.map { item ->
                        val entry = linkedMapOf<String, Any?>("uuid" to item.uuid.toString(), "properties" to properties(item.properties))
                        if (item.properties and BluetoothGattCharacteristic.PROPERTY_READ != 0) {
                            runCatching { gatt.readCharacteristic(item); await("read", 5) as? ByteArray }.getOrNull()?.let {
                                entry["value"] = hex(it); entry["text"] = printable(hex(it))
                            } ?: run { entry["error"] = "not readable now" }
                        }
                        entry
                    })
                })
            }
        } finally {
            gatt.disconnect()
            gatt.close()
        }
    }

    @SuppressLint("MissingPermission")
    @Suppress("DEPRECATION")
    private fun wifiScan(): Map<String, Any?> {
        if (!granted(Manifest.permission.ACCESS_FINE_LOCATION)) throw IllegalStateException(
            tr("Consenti a RigHaven la posizione: Android la chiede per elencare le reti Wi-Fi", "Allow RigHaven the location: Android needs it to list Wi-Fi networks"))
        val wifi = context.applicationContext.getSystemService(WifiManager::class.java) ?: throw IllegalStateException("Wi-Fi not available")
        wifi.startScan() // Android allows a few scans every two minutes; otherwise the last results are used
        Thread.sleep(4000)
        val networks = wifi.scanResults.filter { it.SSID.isNotEmpty() }.sortedByDescending { it.level }.map {
            val secured = listOf("WEP", "WPA", "SAE", "PSK", "EAP", "OWE").any { word -> it.capabilities.contains(word) }
            mapOf("ssid" to it.SSID, "bssid" to it.BSSID, "signal" to (2 * (it.level + 100)).coerceIn(0, 100), "open" to !secured)
        }
        return mapOf("networks" to networks.distinctBy { it["ssid"] })
    }

    private fun properties(value: Int) = buildList {
        if (value and BluetoothGattCharacteristic.PROPERTY_READ != 0) add("Read")
        if (value and BluetoothGattCharacteristic.PROPERTY_WRITE != 0) add("Write")
        if (value and BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE != 0) add("WriteWithoutResponse")
        if (value and BluetoothGattCharacteristic.PROPERTY_NOTIFY != 0) add("Notify")
        if (value and BluetoothGattCharacteristic.PROPERTY_INDICATE != 0) add("Indicate")
    }

    private fun hex(bytes: ByteArray) = bytes.joinToString("") { "%02x".format(it) }

    private fun short(uuid: UUID): String {
        val text = uuid.toString()
        return if (text.endsWith("-0000-1000-8000-00805f9b34fb") && text.startsWith("0000")) text.substring(4, 8) else text
    }
}

object BluetoothAdapterCheck {
    fun valid(address: String) = Regex("^[0-9A-F]{2}(:[0-9A-F]{2}){5}$").matches(address)
}
