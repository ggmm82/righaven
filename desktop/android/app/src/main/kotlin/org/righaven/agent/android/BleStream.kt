package org.righaven.agent.android

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.BluetoothSocket
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import org.righaven.agent.BleChannel
import org.righaven.agent.Stream
import java.io.InputStream
import java.io.OutputStream
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit

/**
 * A Bluetooth device of the phone as a byte channel for a tunnel (ble:ADDRESS[/service/write/notify]):
 * a classic device through its serial profile, a Bluetooth LE device through one write
 * characteristic and the notifications of another. The bytes are not read here: protocols belong
 * to the tools that open the channel. One client per device at a time.
 */
object BleStream {
    private val busy = ConcurrentHashMap.newKeySet<String>()

    fun open(context: Context, target: String): Stream {
        val channel = BleChannel.parse(target)
        val needed = if (Build.VERSION.SDK_INT >= 31) listOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
        else listOf(Manifest.permission.ACCESS_FINE_LOCATION)
        if (!needed.all { context.checkSelfPermission(it) == PackageManager.PERMISSION_GRANTED })
            throw IllegalStateException(tr("Consenti a RigHaven l’accesso al Bluetooth (dispositivi nelle vicinanze)", "Allow RigHaven to use Bluetooth (nearby devices)"))
        val adapter = context.getSystemService(BluetoothManager::class.java)?.adapter?.takeIf { it.isEnabled }
            ?: throw IllegalStateException(tr("Bluetooth spento: accendilo", "Bluetooth is off: turn it on"))
        if (!busy.add(channel.address)) throw IllegalStateException(tr("Il dispositivo Bluetooth è già in uso da un altro client", "The Bluetooth device is already in use by another client"))
        try {
            val device = adapter.getRemoteDevice(channel.address)
            val stream = if (classic(device)) rfcomm(adapter, device) else gatt(context, device, channel)
            return object : Stream by stream {
                override fun close() {
                    try { stream.close() } finally { busy.remove(channel.address) }
                }
            }
        } catch (error: Exception) {
            busy.remove(channel.address)
            throw error
        }
    }

    @SuppressLint("MissingPermission")
    private fun classic(device: BluetoothDevice) = device.type == BluetoothDevice.DEVICE_TYPE_CLASSIC ||
        (device.bondState == BluetoothDevice.BOND_BONDED && device.uuids?.any { it.uuid.toString() == BleChannel.SPP } == true)

    @SuppressLint("MissingPermission")
    private fun rfcomm(adapter: android.bluetooth.BluetoothAdapter, device: BluetoothDevice): Stream {
        adapter.cancelDiscovery()
        val socket: BluetoothSocket = device.createRfcommSocketToServiceRecord(UUID.fromString(BleChannel.SPP))
        socket.connect()
        return object : Stream {
            override val input: InputStream = socket.inputStream
            override val output: OutputStream = socket.outputStream
            override fun close() = socket.close()
        }
    }

    @SuppressLint("MissingPermission")
    @Suppress("DEPRECATION")
    private fun gatt(context: Context, device: BluetoothDevice, channel: BleChannel): Stream {
        val events = LinkedBlockingQueue<Pair<String, Int>>()
        val received = Notified()
        val input = received
        val callback = object : BluetoothGattCallback() {
            override fun onConnectionStateChange(gatt: BluetoothGatt, status: Int, newState: Int) {
                if (newState == BluetoothProfile.STATE_CONNECTED) events.put("connected" to status)
                else { events.put("disconnected" to status); runCatching { received.close() } }
            }
            override fun onServicesDiscovered(gatt: BluetoothGatt, status: Int) { events.put("services" to status) }
            override fun onDescriptorWrite(gatt: BluetoothGatt, descriptor: BluetoothGattDescriptor, status: Int) { events.put("descriptor" to status) }
            override fun onCharacteristicWrite(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic, status: Int) { events.put("write" to status) }
            override fun onCharacteristicChanged(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic, value: ByteArray) {
                runCatching { received.write(value); received.flush() }
            }
            @Deprecated("Android 12 and earlier")
            override fun onCharacteristicChanged(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic) {
                if (Build.VERSION.SDK_INT < 33) runCatching { received.write(characteristic.value ?: ByteArray(0)); received.flush() }
            }
        }
        fun await(kind: String, seconds: Long): Int {
            while (true) {
                val (name, status) = events.poll(seconds, TimeUnit.SECONDS)
                    ?: throw IllegalStateException(tr("Il dispositivo non risponde: avvicinalo al telefono e riprova", "The device does not answer: bring it near the phone and try again"))
                if (name == "disconnected") throw IllegalStateException(tr("Il dispositivo si è scollegato", "The device disconnected"))
                if (name == kind) return status
            }
        }
        val gatt = device.connectGatt(context, false, callback, BluetoothDevice.TRANSPORT_LE)
        try {
            await("connected", 20)
            gatt.discoverServices()
            await("services", 15)
            val services = gatt.services.associate { service ->
                service.uuid.toString() to service.characteristics.associate { it.uuid.toString() to properties(it.properties) }
            }
            val (serviceId, writeId, notifyId) = BleChannel.choose(channel, services)
            val service = gatt.getService(UUID.fromString(serviceId)) ?: throw IllegalStateException("service not found: $serviceId")
            val target = service.getCharacteristic(UUID.fromString(writeId)) ?: throw IllegalStateException("characteristic not found: $writeId")
            val listen = service.getCharacteristic(UUID.fromString(notifyId)) ?: throw IllegalStateException("characteristic not found: $notifyId")
            if (!gatt.setCharacteristicNotification(listen, true)) throw IllegalStateException("notifications refused")
            val enable = if (listen.properties and BluetoothGattCharacteristic.PROPERTY_NOTIFY != 0) BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
            else BluetoothGattDescriptor.ENABLE_INDICATION_VALUE
            listen.getDescriptor(UUID.fromString("00002902-0000-1000-8000-00805f9b34fb"))?.let { descriptor ->
                if (Build.VERSION.SDK_INT >= 33) gatt.writeDescriptor(descriptor, enable) else { descriptor.value = enable; gatt.writeDescriptor(descriptor) }
                if (await("descriptor", 10) != BluetoothGatt.GATT_SUCCESS) throw IllegalStateException("notifications refused")
            }
            val type = if (target.properties and BluetoothGattCharacteristic.PROPERTY_WRITE != 0) BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
            else BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
            // Writes go in pieces of 20 bytes (the smallest Bluetooth LE packet), one after the other.
            val output = object : OutputStream() {
                override fun write(byte: Int) = write(byteArrayOf(byte.toByte()), 0, 1)
                @Synchronized
                override fun write(data: ByteArray, offset: Int, length: Int) {
                    var at = offset
                    while (at < offset + length) {
                        val piece = data.copyOfRange(at, minOf(at + 20, offset + length))
                        if (Build.VERSION.SDK_INT >= 33) gatt.writeCharacteristic(target, piece, type)
                        else { target.writeType = type; target.value = piece; gatt.writeCharacteristic(target) }
                        if (await("write", 10) != BluetoothGatt.GATT_SUCCESS) throw java.io.IOException("write refused")
                        at += piece.size
                    }
                }
            }
            return object : Stream {
                override val input: InputStream = input
                override val output: OutputStream = output
                override fun close() {
                    runCatching { gatt.setCharacteristicNotification(listen, false) }
                    gatt.disconnect()
                    gatt.close()
                    runCatching { received.close() }
                }
            }
        } catch (error: Exception) {
            gatt.disconnect()
            gatt.close()
            throw error
        }
    }

    /** What the device notified, read in order by the tunnel (a binder thread writes, the tunnel reads). */
    private class Notified : InputStream() {
        private val chunks = LinkedBlockingQueue<ByteArray>()
        private var current = ByteArray(0)
        private var at = 0
        @Volatile private var closed = false

        fun write(data: ByteArray) { if (!closed && data.isNotEmpty()) chunks.put(data.copyOf()) }
        fun flush() {}
        override fun close() { closed = true; chunks.put(ByteArray(0)) }

        override fun read(): Int {
            val one = ByteArray(1)
            return if (read(one, 0, 1) < 0) -1 else one[0].toInt() and 0xff
        }

        override fun read(buffer: ByteArray, offset: Int, length: Int): Int {
            if (at >= current.size) {
                if (closed && chunks.isEmpty()) return -1
                val next = chunks.take()
                if (next.isEmpty()) return -1
                current = next
                at = 0
            }
            val size = minOf(length, current.size - at)
            System.arraycopy(current, at, buffer, offset, size)
            at += size
            return size
        }
    }

    private fun properties(value: Int) = buildSet {
        if (value and BluetoothGattCharacteristic.PROPERTY_READ != 0) add("Read")
        if (value and BluetoothGattCharacteristic.PROPERTY_WRITE != 0) add("Write")
        if (value and BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE != 0) add("WriteWithoutResponse")
        if (value and BluetoothGattCharacteristic.PROPERTY_NOTIFY != 0) add("Notify")
        if (value and BluetoothGattCharacteristic.PROPERTY_INDICATE != 0) add("Indicate")
    }
}
