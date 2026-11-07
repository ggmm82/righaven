package org.righaven.agent.android

import android.annotation.SuppressLint
import android.bluetooth.BluetoothClass
import android.bluetooth.BluetoothManager
import android.content.Context
import android.content.pm.PackageManager
import android.hardware.ConsumerIrManager
import android.hardware.Sensor
import android.hardware.SensorManager
import android.hardware.usb.UsbConstants
import android.hardware.usb.UsbManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.nfc.NfcAdapter
import android.os.BatteryManager
import android.os.Build

/**
 * Everything the phone sees now, in the shape of «all the PC's devices»: what is plugged into its
 * USB-C port (OTG), the paired Bluetooth devices, NFC, infrared, UWB and its sensors, and the phone
 * itself. Nothing is changed.
 */
class PhoneDevices(private val context: Context) {
    // Serial chips of boards and adapters (the same list as the PC's USB peripherals).
    private val chips = mapOf("10c4" to "CP210x (Silicon Labs)", "1a86" to "CH340/CH9102 (WCH)", "0403" to "FTDI", "067b" to "PL2303 (Prolific)",
        "303a" to "Espressif (ESP32-S2/S3/C3)", "2341" to "Arduino", "2e8a" to "Raspberry Pi Pico", "239a" to "Adafruit", "1d50" to "OpenMoko/Black Magic")

    fun list(): Map<String, Any?> {
        val devices = mutableListOf<Map<String, Any?>>()
        usb(devices)
        bluetooth(devices)
        internal(devices)
        system(devices)
        return mapOf("devices" to devices, "platform" to "android")
    }

    private fun usb(devices: MutableList<Map<String, Any?>>) {
        val manager = context.getSystemService(UsbManager::class.java) ?: return
        for (device in manager.deviceList.values) {
            val vid = "%04x".format(device.vendorId)
            val classes = (0 until device.interfaceCount).map { device.getInterface(it).interfaceClass }.toSet()
            val kind = when {
                chips.containsKey(vid) || UsbConstants.USB_CLASS_COMM in classes || UsbConstants.USB_CLASS_CDC_DATA in classes -> "Ports"
                UsbConstants.USB_CLASS_HID in classes -> "HID"
                UsbConstants.USB_CLASS_MASS_STORAGE in classes -> "DiskDrive"
                UsbConstants.USB_CLASS_AUDIO in classes -> "AudioEndpoint"
                UsbConstants.USB_CLASS_VIDEO in classes -> "Camera"
                else -> "USB"
            }
            // Names need the owner's permission for that device on recent Android: the IDs never do.
            val name = runCatching { listOfNotNull(device.manufacturerName, device.productName).joinToString(" ") }.getOrNull()?.takeIf { it.isNotBlank() }
                ?: chips[vid]?.let { "Adattatore seriale $it" } ?: "Dispositivo USB"
            devices += mapOf("class" to kind, "name" to name, "bus" to "usb", "ok" to true, "vidpid" to "$vid:%04x".format(device.productId),
                "chip" to chips[vid])
        }
    }

    @SuppressLint("MissingPermission")
    private fun bluetooth(devices: MutableList<Map<String, Any?>>) {
        val adapter = context.getSystemService(BluetoothManager::class.java)?.adapter ?: return
        val bonded = runCatching { adapter.bondedDevices.orEmpty() }.getOrDefault(emptySet())
        for (device in bonded) {
            val major = runCatching { device.bluetoothClass?.majorDeviceClass }.getOrNull()
            val kind = when (major) {
                BluetoothClass.Device.Major.AUDIO_VIDEO -> "AudioEndpoint"
                BluetoothClass.Device.Major.PHONE -> "Phone"
                BluetoothClass.Device.Major.COMPUTER -> "Computer"
                BluetoothClass.Device.Major.WEARABLE -> "Wearable"
                BluetoothClass.Device.Major.PERIPHERAL -> "HID"
                BluetoothClass.Device.Major.HEALTH -> "Health"
                else -> "Bluetooth"
            }
            devices += mapOf("class" to kind, "name" to (runCatching { device.name }.getOrNull() ?: device.address), "bus" to "bluetooth", "ok" to true,
                "address" to device.address)
        }
    }

    private fun internal(devices: MutableList<Map<String, Any?>>) {
        val features = context.packageManager
        NfcAdapter.getDefaultAdapter(context)?.let {
            devices += mapOf("class" to "NFC", "name" to if (it.isEnabled) "NFC (attivo)" else "NFC (spento nelle impostazioni)", "bus" to "internal", "ok" to it.isEnabled)
        }
        if (context.getSystemService(ConsumerIrManager::class.java)?.hasIrEmitter() == true)
            devices += mapOf("class" to "IR", "name" to "Trasmettitore a infrarossi", "bus" to "internal", "ok" to true)
        if (Build.VERSION.SDK_INT >= 31 && features.hasSystemFeature("android.hardware.uwb"))
            devices += mapOf("class" to "UWB", "name" to "Ultra-wideband (UWB)", "bus" to "internal", "ok" to true)
        if (features.hasSystemFeature(PackageManager.FEATURE_USB_HOST))
            devices += mapOf("class" to "USB", "name" to "Porta USB-C con modalità host (OTG): accetta schede e adattatori", "bus" to "internal", "ok" to true)
        context.getSystemService(SensorManager::class.java)?.getSensorList(Sensor.TYPE_ALL).orEmpty()
            .distinctBy { it.type }.forEach { sensor ->
                devices += mapOf("class" to "Sensor", "name" to sensor.name, "bus" to "internal", "ok" to true, "vendor" to sensor.vendor)
            }
    }

    private fun system(devices: MutableList<Map<String, Any?>>) {
        devices += mapOf("class" to "Phone", "name" to "${Build.MANUFACTURER} ${Build.MODEL} · Android ${Build.VERSION.RELEASE}", "bus" to "system", "ok" to true)
        context.getSystemService(BatteryManager::class.java)?.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)?.takeIf { it in 0..100 }?.let {
            devices += mapOf("class" to "Battery", "name" to "Batteria $it%", "bus" to "system", "ok" to true)
        }
        val connectivity = context.getSystemService(ConnectivityManager::class.java)
        val capabilities = connectivity?.getNetworkCapabilities(connectivity.activeNetwork)
        val network = when {
            capabilities == null -> "nessuna rete"
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "Wi-Fi"
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "rete mobile"
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> "Ethernet"
            else -> "altra rete"
        }
        val addresses = connectivity?.getLinkProperties(connectivity.activeNetwork)?.linkAddresses?.mapNotNull { it.address.hostAddress }.orEmpty()
        devices += mapOf("class" to "Net", "name" to "Collegato via $network" + (if (addresses.isNotEmpty()) " · " + addresses.joinToString(", ") else ""),
            "bus" to "system", "ok" to (capabilities != null))
    }
}
