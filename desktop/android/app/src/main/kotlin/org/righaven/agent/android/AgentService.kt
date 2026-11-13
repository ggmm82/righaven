package org.righaven.agent.android

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import okio.ByteString.Companion.toByteString
import org.righaven.agent.ActivityLog
import org.righaven.agent.AgentSession
import org.righaven.agent.Channel
import org.righaven.agent.HomeDial
import org.righaven.agent.Stream
import java.io.InputStream
import java.io.OutputStream
import java.util.concurrent.TimeUnit

/**
 * RigHaven Agent on the phone: a foreground service (Android shows its notification) that keeps
 * the channel to the server open, answers the actions asked from the page or the chat and carries
 * hosts of the phone's network to the server's workers. It reconnects by itself.
 */
class AgentService : Service() {
    companion object {
        const val VERSION_HEADER = "X-RigHaven-Agent"
        const val ACTION_STOP = "org.righaven.agent.STOP"
        const val EXTRA_LOG = "show_log"
        @Volatile var status: String = ""
            private set

        fun start(context: Context) {
            Store.setAgentEnabled(context, true)
            context.startForegroundService(Intent(context, AgentService::class.java))
        }

        fun stop(context: Context) {
            Store.setAgentEnabled(context, false)
            log(context).add(tr("Agente fermato dall’app", "Agent stopped from the app"))
            context.stopService(Intent(context, AgentService::class.java))
        }

        /** The phone's own record of what the agent did (Agent → Log in the app). */
        fun log(context: Context) = ActivityLog(java.io.File(context.filesDir, "agent-log.txt"))
    }

    // The read timeout bounds the opening handshake (OkHttp lifts it once the WebSocket is open; the
    // pings watch it from then on): a server that accepts but never answers is retried, not waited for.
    private val client = OkHttpClient.Builder().pingInterval(25, TimeUnit.SECONDS).connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS).build()
    @Volatile private var running = false
    @Volatile private var socket: WebSocket? = null
    @Volatile private var session: AgentSession? = null
    private var pause = 2000L

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {  // «Stop» in the notification, even with the app closed
            Store.setAgentEnabled(this, false)
            log(this).add(tr("Agente fermato dalla notifica", "Agent stopped from the notification"))
            running = false
            socket?.close(1000, "stopped")
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
            return START_NOT_STICKY
        }
        // Opening the app starts the service again: an agent already connected keeps saying so.
        val notification = notification(status.takeIf { running && it.isNotEmpty() } ?: tr("Collegamento al server…", "Connecting to the server…"))
        if (Build.VERSION.SDK_INT >= 29) startForeground(1, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE)
        else startForeground(1, notification)
        if (!running) {
            running = true
            connect()
        }
        return START_STICKY
    }

    override fun onDestroy() {
        running = false
        socket?.close(1000, "stopped")
        session?.closeAll()
        status = ""
        super.onDestroy()
    }

    private fun connect() {
        val pairing = Store.load(this) ?: run { stopSelf(); return }
        val url = pairing.server.replaceFirst("https://", "wss://").replaceFirst("http://", "ws://") + "/api/webhooks/righaven-agent/connect"
        val request = Request.Builder().url(url).header(VERSION_HEADER, pairing.token).build()
        val log = log(this)
        log.add(tr("Collegamento a ", "Connecting to ") + pairing.server)
        socket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                pause = 2000L
                val actions = Actions(this@AgentService)
                val channel = object : Channel {
                    override fun sendText(text: String) = webSocket.send(text)
                    override fun sendBinary(data: ByteArray) = webSocket.send(data.toByteString())
                    override fun close(code: Int, reason: String) { webSocket.close(code, reason) }
                }
                session = AgentSession(channel, "android", BuildConfigVersion.name(this@AgentService), actions.names, actions::networks,
                    { action, args ->
                        // The notification says what the server asked while it runs, then the outcome.
                        show(tr("Collegato · esegue ", "Connected · running ") + action + "…")
                        try {
                            log.action(action, args.values.joinToString(" ")) { actions.handle(action, args) }
                        } finally {
                            show(tr("Collegato a ", "Connected to ") + pairing.server + " · " + (log.lines().firstOrNull()?.substringAfter("  ") ?: ""))
                        }
                    },
                    openStream = { target ->
                        if (target.startsWith("ble:")) {
                            // A Bluetooth device of the phone as a byte channel for the server's tools.
                            val stream = try {
                                BleStream.open(this@AgentService, target)
                            } catch (error: Exception) {
                                log.add(tr("✗ canale Bluetooth ", "✗ Bluetooth channel ") + target.removePrefix("ble:") + " · " + (error.message ?: error.javaClass.simpleName))
                                throw error
                            }
                            log.add(tr("Canale Bluetooth aperto: ", "Bluetooth channel opened: ") + target.removePrefix("ble:"))
                            stream
                        } else {
                            val tcp = try {
                                HomeDial().open(target)
                            } catch (error: Exception) {
                                log.add(tr("✗ tunnel verso ", "✗ tunnel to ") + target + " · " + (error.message ?: error.javaClass.simpleName))
                                throw error
                            }
                            log.add(tr("Tunnel aperto verso ", "Tunnel opened to ") + target)
                            object : Stream {
                                override val input: InputStream = tcp.getInputStream()
                                override val output: OutputStream = tcp.getOutputStream()
                                override fun close() = tcp.close()
                            }
                        }
                    }).also { it.hello() }
                show(tr("Collegato a ", "Connected to ") + pairing.server)
                log.add(tr("Collegato a ", "Connected to ") + pairing.server)
            }

            override fun onMessage(webSocket: WebSocket, text: String) { session?.onText(text) }
            override fun onMessage(webSocket: WebSocket, bytes: ByteString) { session?.onBinary(bytes.toByteArray()) }

            // A revocation is only what the server itself confirms; a proxy or a restarting server is not.
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                log.add(tr("Collegamento chiuso dal server", "Connection closed by the server") + " ($code${if (reason.isNotEmpty()) " $reason" else ""})")
                ended(code == 4001 || code == 4401)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                log.add(tr("Collegamento non riuscito: ", "Connection failed: ") + (response?.let { "HTTP ${it.code} · " } ?: "") + (t.message ?: t.javaClass.simpleName))
                ended((response?.code ?: 0) in setOf(401, 403))
            }
        })
    }

    private fun ended(refused: Boolean) {
        session?.closeAll()
        session = null
        if (!running) return
        if (refused && confirmedRevoked()) {
            log(this).add(tr("Il server ha revocato questo telefono", "The server revoked this phone"))
            show(tr("Il server non riconosce più questo telefono: abbinalo di nuovo dall’app", "The server no longer recognizes this phone: pair it again from the app"))
            Store.setRevoked(this, true)  // the server address stays, to pair again in one step
            running = false
            stopSelf()
            return
        }
        show(tr("Server non raggiungibile: riprovo", "Server not reachable: retrying"))
        log(this).add(tr("Riprovo tra ", "Retrying in ") + (pause / 1000) + " s")
        Thread {
            Thread.sleep(pause)
            pause = (pause * 2).coerceAtMost(60_000L)
            if (running) connect()
        }.start()
    }

    /** Asks the server whether this phone's access was revoked; no answer means "try again later". */
    private fun confirmedRevoked(): Boolean {
        val pairing = Store.load(this) ?: return false
        return try {
            val connection = java.net.URL(pairing.server + "/api/webhooks/righaven-agent/status").openConnection() as java.net.HttpURLConnection
            connection.connectTimeout = 15_000
            connection.readTimeout = 15_000
            connection.setRequestProperty(VERSION_HEADER, pairing.token)
            val code = connection.responseCode
            val body = (if (code in 200..299) connection.inputStream else connection.errorStream)?.bufferedReader()?.readText().orEmpty()
            connection.disconnect()
            code == 401 && body.contains("agent_revoked")
        } catch (error: Exception) {
            false
        }
    }

    private fun show(text: String) {
        if (!running) return  // stopped: no notification comes back
        status = text
        getSystemService(NotificationManager::class.java)?.notify(1, notification(text))
    }

    private fun notification(text: String): Notification {
        val manager = getSystemService(NotificationManager::class.java)
        manager?.createNotificationChannel(NotificationChannel("agent", "RigHaven Agent", NotificationManager.IMPORTANCE_LOW))
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        val showLog = PendingIntent.getActivity(this, 1, Intent(this, MainActivity::class.java).putExtra(EXTRA_LOG, true)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val stop = PendingIntent.getService(this, 2, Intent(this, AgentService::class.java).setAction(ACTION_STOP), PendingIntent.FLAG_IMMUTABLE)
        // Always visible while the agent works: its state, the last operation, and how to stop or check it.
        return Notification.Builder(this, "agent").setSmallIcon(R.drawable.ic_righaven).setContentTitle(tr("RigHaven Agent attivo", "RigHaven Agent active"))
            .setContentText(text).setStyle(Notification.BigTextStyle().bigText(text)).setContentIntent(open).setOngoing(true)
            .addAction(Notification.Action.Builder(null as android.graphics.drawable.Icon?, tr("Ferma", "Stop"), stop).build())
            .addAction(Notification.Action.Builder(null as android.graphics.drawable.Icon?, tr("Registro", "Log"), showLog).build())
            .build()
    }
}

object BuildConfigVersion {
    fun name(context: Context): String =
        runCatching { context.packageManager.getPackageInfo(context.packageName, 0).versionName }.getOrNull() ?: ""
}
