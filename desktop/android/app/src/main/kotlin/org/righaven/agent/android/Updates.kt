package org.righaven.agent.android

import android.app.Activity
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageInstaller
import android.os.Build
import org.json.JSONArray
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/**
 * Updates without a store: the releases of the RigHaven repository that carry RigHaven-android.apk,
 * downloaded and handed to Android's package installer, which asks the owner to confirm.
 */
object Updates {
    const val ASSET = "RigHaven-android.apk"
    private const val ACTION = "org.righaven.agent.UPDATE_STATUS"

    data class Release(val tag: String, val prerelease: Boolean, val published: String, val apk: String)

    fun releases(repository: String): List<Release> {
        val connection = URL("https://api.github.com/repos/$repository/releases?per_page=40").openConnection() as HttpURLConnection
        connection.setRequestProperty("Accept", "application/vnd.github+json")
        connection.connectTimeout = 20_000
        connection.readTimeout = 30_000
        try {
            if (connection.responseCode != 200) throw IllegalStateException(tr("GitHub non risponde (HTTP ${connection.responseCode})", "GitHub does not answer (HTTP ${connection.responseCode})"))
            val items = JSONArray(connection.inputStream.bufferedReader().readText())
            return (0 until items.length()).mapNotNull { index ->
                val release = items.getJSONObject(index)
                val assets = release.optJSONArray("assets") ?: return@mapNotNull null
                val apk = (0 until assets.length()).map { assets.getJSONObject(it) }.firstOrNull { it.optString("name") == ASSET }
                    ?: return@mapNotNull null
                Release(release.optString("tag_name"), release.optBoolean("prerelease") || release.optString("tag_name").contains("-rc."),
                    release.optString("published_at").take(10), apk.optString("browser_download_url"))
            }.sortedWith(compareBy<Release> { it.prerelease }.thenByDescending { it.published })
        } finally {
            connection.disconnect()
        }
    }

    fun download(context: Context, release: Release, progress: (Int) -> Unit): File {
        val folder = File(context.cacheDir, "updates").apply { mkdirs() }
        folder.listFiles()?.forEach { it.delete() }
        val target = File(folder, ASSET)
        val connection = URL(release.apk).openConnection() as HttpURLConnection
        connection.connectTimeout = 20_000
        connection.readTimeout = 60_000
        try {
            if (connection.responseCode != 200) throw IllegalStateException(tr("Download non riuscito (HTTP ${connection.responseCode})", "Download failed (HTTP ${connection.responseCode})"))
            val total = connection.contentLengthLong
            connection.inputStream.use { input ->
                target.outputStream().use { output ->
                    val buffer = ByteArray(65536)
                    var done = 0L
                    while (true) {
                        val size = input.read(buffer)
                        if (size < 0) break
                        output.write(buffer, 0, size)
                        done += size
                        if (total > 0) progress((done * 100 / total).toInt())
                    }
                }
            }
        } finally {
            connection.disconnect()
        }
        return target
    }

    /** Hands the APK to Android's installer; the outcome comes back through [listen]. */
    fun install(context: Context, apk: File) {
        val installer = context.packageManager.packageInstaller
        val session = installer.createSession(PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL))
        installer.openSession(session).use { open ->
            apk.inputStream().use { input ->
                open.openWrite("righaven", 0, apk.length()).use { output ->
                    input.copyTo(output)
                    open.fsync(output)
                }
            }
            val flags = PendingIntent.FLAG_UPDATE_CURRENT or (if (Build.VERSION.SDK_INT >= 31) PendingIntent.FLAG_MUTABLE else 0)
            val status = PendingIntent.getBroadcast(context, session, Intent(ACTION).setPackage(context.packageName), flags)
            open.commit(status.intentSender)
        }
    }

    /** The installer's answers: its confirmation screen, success, or why it refused. */
    fun listen(activity: Activity, message: (String) -> Unit): BroadcastReceiver {
        val receiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context, intent: Intent) {
                when (intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)) {
                    PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                        @Suppress("DEPRECATION")
                        val confirm = intent.getParcelableExtra<Intent>(Intent.EXTRA_INTENT)
                        confirm?.let { activity.startActivity(it.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
                    }
                    PackageInstaller.STATUS_SUCCESS -> message(tr("Aggiornamento installato.", "Update installed."))
                    PackageInstaller.STATUS_FAILURE_CONFLICT, PackageInstaller.STATUS_FAILURE_INCOMPATIBLE -> message(tr(
                        "Android ha rifiutato l’aggiornamento: questa versione è firmata con una chiave diversa da quella installata. Disinstalla l’app e installa la versione scelta (poi abbina di nuovo il telefono).",
                        "Android refused the update: this version is signed with a different key from the installed one. Uninstall the app and install the chosen version (then pair the phone again)."))
                    PackageInstaller.STATUS_FAILURE_ABORTED -> message(tr("Aggiornamento annullato.", "Update cancelled."))
                    else -> message(tr("Aggiornamento non installato: ", "Update not installed: ") + (intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE) ?: ""))
                }
            }
        }
        if (Build.VERSION.SDK_INT >= 33) activity.registerReceiver(receiver, IntentFilter(ACTION), Context.RECEIVER_NOT_EXPORTED)
        else @Suppress("UnspecifiedRegisterReceiverFlag") activity.registerReceiver(receiver, IntentFilter(ACTION))
        return receiver
    }
}
