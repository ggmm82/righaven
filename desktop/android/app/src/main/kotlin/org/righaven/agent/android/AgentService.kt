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
        @Volatile var status: String = ""
            private set

        fun start(context: Context) {
            Store.setAgentEnabled(context, true)
            context.startForegroundService(Intent(context, AgentService::class.java))
        }

        fun stop(context: Context) {
            Store.setAgentEnabled(context, false)
            context.stopService(Intent(context, AgentService::class.java))
        }
    }

    private val client = OkHttpClient.Builder().pingInterval(25, TimeUnit.SECONDS).readTimeout(0, TimeUnit.MILLISECONDS).build()
    @Volatile private var running = false
    @Volatile private var socket: WebSocket? = null
    @Volatile private var session: AgentSession? = null
    private var pause = 2000L

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val notification = notification(tr("Collegamento al server…", "Connecting to the server…"))
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
        socket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                pause = 2000L
                val actions = Actions(this@AgentService)
                val channel = object : Channel {
                    override fun sendText(text: String) = webSocket.send(text)
                    override fun sendBinary(data: ByteArray) = webSocket.send(data.toByteString())
                    override fun close(code: Int, reason: String) { webSocket.close(code, reason) }
                }
                session = AgentSession(channel, "android", BuildConfigVersion.name(this@AgentService), actions.names, actions::networks, actions::handle,
                    openStream = { target ->
                        val tcp = HomeDial().open(target)
                        object : Stream {
                            override val input: InputStream = tcp.getInputStream()
                            override val output: OutputStream = tcp.getOutputStream()
                            override fun close() = tcp.close()
                        }
                    }).also { it.hello() }
                show(tr("Collegato a ", "Connected to ") + pairing.server)
            }

            override fun onMessage(webSocket: WebSocket, text: String) { session?.onText(text) }
            override fun onMessage(webSocket: WebSocket, bytes: ByteString) { session?.onBinary(bytes.toByteArray()) }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) { ended(code == 4001 || code == 4401) }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                ended((response?.code ?: 0) in setOf(401, 403, 404))
            }
        })
    }

    private fun ended(revoked: Boolean) {
        session?.closeAll()
        session = null
        if (!running) return
        if (revoked) {
            show(tr("Il server non riconosce più questo telefono: abbinalo di nuovo dall’app", "The server no longer recognizes this phone: pair it again from the app"))
            Store.clear(this)
            running = false
            stopSelf()
            return
        }
        show(tr("Server non raggiungibile: riprovo", "Server not reachable: retrying"))
        Thread {
            Thread.sleep(pause)
            pause = (pause * 2).coerceAtMost(60_000L)
            if (running) connect()
        }.start()
    }

    private fun show(text: String) {
        status = text
        getSystemService(NotificationManager::class.java)?.notify(1, notification(text))
    }

    private fun notification(text: String): Notification {
        val manager = getSystemService(NotificationManager::class.java)
        manager?.createNotificationChannel(NotificationChannel("agent", "RigHaven Agent", NotificationManager.IMPORTANCE_LOW))
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        return Notification.Builder(this, "agent").setSmallIcon(R.drawable.ic_righaven).setContentTitle("RigHaven Agent")
            .setContentText(text).setContentIntent(open).setOngoing(true).build()
    }
}

object BuildConfigVersion {
    fun name(context: Context): String =
        runCatching { context.packageManager.getPackageInfo(context.packageName, 0).versionName }.getOrNull() ?: ""
}
