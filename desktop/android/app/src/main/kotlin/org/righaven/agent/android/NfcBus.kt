package org.righaven.agent.android

import android.app.Activity
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.nfc.NfcAdapter
import android.nfc.Tag
import android.nfc.tech.IsoDep
import android.nfc.tech.MifareClassic
import android.nfc.tech.MifareUltralight
import android.nfc.tech.Ndef
import android.nfc.tech.NfcA
import org.righaven.agent.Ndef as Records
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit

/**
 * Reading an NFC tag asked by the server. Android reads NFC only for the app on screen: the agent
 * shows a notification that opens RigHaven, which listens for one tag while the request waits.
 * Reading only: nothing is written to the tag.
 */
object NfcBus {
    private const val NOTIFICATION = 7
    @Volatile private var waiting: LinkedBlockingQueue<Map<String, Any?>>? = null
    @Volatile private var activity: Activity? = null

    val active get() = waiting != null

    fun read(context: Context): Map<String, Any?> {
        val adapter = NfcAdapter.getDefaultAdapter(context) ?: throw IllegalStateException(tr("Questo telefono non ha l’NFC", "This phone has no NFC"))
        if (!adapter.isEnabled) throw IllegalStateException(tr("NFC spento: attivalo nelle impostazioni del telefono", "NFC is off: turn it on in the phone's settings"))
        val queue = LinkedBlockingQueue<Map<String, Any?>>()
        waiting = queue
        activity?.let { current -> current.runOnUiThread { listen(current) } }
        notify(context)
        try {
            return queue.poll(45, TimeUnit.SECONDS) ?: throw IllegalStateException(tr(
                "Nessun tag NFC letto in 45 secondi: apri RigHaven sul telefono (tocca la notifica) e avvicina il tag al retro del telefono",
                "No NFC tag read in 45 seconds: open RigHaven on the phone (tap the notification) and hold the tag to the back of the phone"))
        } finally {
            waiting = null
            context.getSystemService(NotificationManager::class.java)?.cancel(NOTIFICATION)
            activity?.let { current -> current.runOnUiThread { runCatching { NfcAdapter.getDefaultAdapter(current)?.disableReaderMode(current) } } }
        }
    }

    /** Called by the activity when it comes to the screen or leaves it. */
    fun attach(current: Activity?) {
        activity = current
        if (current != null && active) listen(current)
    }

    private fun listen(current: Activity) {
        val flags = NfcAdapter.FLAG_READER_NFC_A or NfcAdapter.FLAG_READER_NFC_B or NfcAdapter.FLAG_READER_NFC_F or NfcAdapter.FLAG_READER_NFC_V
        NfcAdapter.getDefaultAdapter(current)?.enableReaderMode(current, { tag -> waiting?.offer(describe(tag)) }, flags, null)
    }

    private fun notify(context: Context) {
        val open = PendingIntent.getActivity(context, 3, Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP),
            PendingIntent.FLAG_IMMUTABLE)
        val notification = android.app.Notification.Builder(context, "agent").setSmallIcon(R.drawable.ic_righaven)
            .setContentTitle(tr("Leggi un tag NFC", "Read an NFC tag"))
            .setContentText(tr("Tocca qui per aprire RigHaven e avvicina il tag al retro del telefono", "Tap here to open RigHaven and hold the tag to the back of the phone"))
            .setContentIntent(open).setAutoCancel(true).build()
        context.getSystemService(NotificationManager::class.java)?.notify(NOTIFICATION, notification)
    }

    private fun describe(tag: Tag): Map<String, Any?> {
        val result = linkedMapOf<String, Any?>("id" to Records.hex(tag.id), "technologies" to tag.techList.map { it.substringAfterLast('.') })
        NfcA.get(tag)?.let { result["atqa"] = Records.hex(it.atqa); result["sak"] = it.sak.toInt() }
        MifareClassic.get(tag)?.let { result["chip"] = "MIFARE Classic " + (it.size / 1024).let { kb -> if (kb > 0) "${kb}K" else "${it.size} B" }; result["sectors"] = it.sectorCount }
        MifareUltralight.get(tag)?.let { result["chip"] = if (it.type == MifareUltralight.TYPE_ULTRALIGHT_C) "MIFARE Ultralight C" else "MIFARE Ultralight / NTAG" }
        IsoDep.get(tag)?.let { result["iso_dep"] = true; result["historical"] = it.historicalBytes?.let(Records::hex) }
        Ndef.get(tag)?.let { ndef ->
            result["ndef"] = mapOf("type" to ndef.type, "max_size" to ndef.maxSize, "writable" to ndef.isWritable)
            result["records"] = ndef.cachedNdefMessage?.records.orEmpty().map { Records.record(it.tnf.toInt(), it.type, it.payload) }
        }
        return result
    }
}
