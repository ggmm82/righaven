package org.righaven.agent.android

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.text.InputType
import android.view.Gravity
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.webkit.HttpAuthHandler
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import org.righaven.agent.Pairing as Protocol
import java.net.HttpURLConnection
import java.net.URL

/**
 * The RigHaven app: the server's web interface (chat, projects, connections) and, in the
 * background, RigHaven Agent, which puts the phone's Bluetooth, Wi-Fi and network at the server's
 * disposal. The phone pairs once with a code from Connections → Connected PCs.
 */
class MainActivity : Activity() {
    private var web: WebView? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val pairing = Store.load(this)
        when {
            pairing == null -> showPairing(server = Store.server(this))
            // Only the server's own answer revokes a phone: an outage or a proxy page never does.
            Store.revoked(this) -> showPairing(tr("Il server non riconosce più questo telefono (è stato revocato in PC collegati): genera un nuovo codice e inseriscilo qui.",
                "The server no longer knows this phone (it was revoked in Connected PCs): create a new code and type it here."), pairing.server)
            else -> showWeb(pairing)
        }
        if (intent?.getBooleanExtra(AgentService.EXTRA_LOG, false) == true) showLog()
    }

    // NFC is read only by the app on screen: while the server waits for a tag, this activity listens.
    override fun onResume() {
        super.onResume()
        NfcBus.attach(this)
    }

    override fun onPause() {
        NfcBus.attach(null)
        runCatching { android.nfc.NfcAdapter.getDefaultAdapter(this)?.disableReaderMode(this) }
        super.onPause()
    }

    // «Log» in the agent's notification while the app is already open.
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        if (intent.getBooleanExtra(AgentService.EXTRA_LOG, false)) showLog()
    }

    private fun showPairing(message: String = "", server: String = "") {
        val padding = (16 * resources.displayMetrics.density).toInt()
        val layout = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(padding, padding * 2, padding, padding) }
        layout.addView(TextView(this).apply { text = "RigHaven"; textSize = 26f })
        layout.addView(TextView(this).apply {
            text = tr("Collega questo telefono al tuo server RigHaven. Nel server apri Connessioni → PC collegati, scrivi un nome (per esempio «Telefono») e premi «Collega un PC»: copia qui indirizzo e codice.",
                "Connect this phone to your RigHaven server. On the server open Connections → Connected PCs, type a name (for example “Phone”) and press “Connect a PC”: copy the address and the code here.")
            setPadding(0, padding, 0, padding)
        })
        val known = server
        val server = EditText(this).apply { hint = tr("Indirizzo del server (https://…)", "Server address (https://…)"); inputType = InputType.TYPE_TEXT_VARIATION_URI; setText(known) }
        val code = EditText(this).apply { hint = tr("Codice di abbinamento", "Pairing code"); inputType = InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS }
        val status = TextView(this).apply { text = message; setTextColor(Color.rgb(160, 30, 30)) }
        val button = Button(this).apply { text = tr("Collega", "Connect") }
        button.setOnClickListener {
            button.isEnabled = false
            status.text = tr("Collegamento…", "Connecting…")
            val address = Protocol.server(server.text.toString())
            val typed = code.text.toString()
            Thread {
                val outcome = runCatching { pair(address, typed) }
                runOnUiThread {
                    outcome.onSuccess { pairing ->
                        Store.save(this, pairing)
                        askPermissions()
                        AgentService.start(this)
                        showWeb(pairing)
                    }.onFailure {
                        button.isEnabled = true
                        status.text = it.message ?: tr("Abbinamento non riuscito", "Pairing failed")
                    }
                }
            }.start()
        }
        listOf(server, code, button, status).forEach { layout.addView(it, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT)) }
        setContentView(layout)
    }

    private fun pair(server: String, code: String): Pairing {
        val body = Protocol.request(code, BuildConfigVersion.name(this))
        val connection = URL("$server/api/webhooks/righaven-agent/pair").openConnection() as HttpURLConnection
        connection.requestMethod = "POST"
        connection.doOutput = true
        connection.connectTimeout = 20_000
        connection.readTimeout = 30_000
        connection.setRequestProperty("Content-Type", "application/json")
        connection.outputStream.use { it.write(body.toByteArray()) }
        val status = connection.responseCode
        val answer = (if (status in 200..299) connection.inputStream else connection.errorStream)?.bufferedReader()?.readText().orEmpty()
        if (status !in 200..299) throw IllegalStateException(tr("Il server ha rifiutato l’abbinamento (HTTP $status)", "The server refused the pairing (HTTP $status)"))
        val paired = Protocol.answer(answer)
        return Pairing(server, paired.token, paired.agent, paired.name)
    }

    private fun showWeb(pairing: Pairing) {
        if (Store.agentEnabled(this)) AgentService.start(this)
        val layout = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val bar = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL; setBackgroundColor(Color.rgb(31, 58, 95)) }
        val title = TextView(this).apply { text = "RigHaven · " + pairing.name; setTextColor(Color.WHITE); setPadding(24, 0, 0, 0) }
        val menu = Button(this).apply { text = tr("Agente", "Agent") }
        menu.setOnClickListener { agentMenu(pairing) }
        bar.addView(title, LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f))
        bar.addView(menu)
        val view = WebView(this)
        view.settings.javaScriptEnabled = true
        view.settings.domStorageEnabled = true
        view.webViewClient = object : WebViewClient() {
            // Links to other sites open in the browser; the server stays in the app.
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                if (request.url.host == Uri.parse(pairing.server).host) return false
                startActivity(Intent(Intent.ACTION_VIEW, request.url))
                return true
            }
            // The site password of the portable release (Caddy) is asked like in a browser.
            override fun onReceivedHttpAuthRequest(view: WebView, handler: HttpAuthHandler, host: String, realm: String) {
                val user = EditText(this@MainActivity).apply { hint = tr("Utente", "User") }
                val password = EditText(this@MainActivity).apply { hint = "Password"; inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD }
                val fields = LinearLayout(this@MainActivity).apply { orientation = LinearLayout.VERTICAL; addView(user); addView(password) }
                AlertDialog.Builder(this@MainActivity).setTitle(host).setView(fields)
                    .setPositiveButton("OK") { _, _ -> handler.proceed(user.text.toString(), password.text.toString()) }
                    .setNegativeButton(tr("Annulla", "Cancel")) { _, _ -> handler.cancel() }.show()
            }
        }
        view.loadUrl(pairing.server)
        web = view
        layout.addView(bar, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
        layout.addView(view, LinearLayout.LayoutParams(MATCH_PARENT, 0, 1f))
        setContentView(layout)
    }

    private fun agentMenu(pairing: Pairing) {
        val on = Store.agentEnabled(this)
        val items = arrayOf(
            if (on) tr("Ferma l’agente su questo telefono", "Stop the agent on this phone") else tr("Avvia l’agente su questo telefono", "Start the agent on this phone"),
            tr("Permessi (Bluetooth, posizione, notifiche)", "Permissions (Bluetooth, location, notifications)"),
            tr("Batteria: lascia lavorare l’agente in background", "Battery: let the agent work in the background"),
            tr("Registro delle operazioni", "Activity log"),
            tr("Scollega questo telefono dal server", "Disconnect this phone from the server"))
        AlertDialog.Builder(this).setTitle(AgentService.status.ifEmpty { pairing.server }).setItems(items) { _, which ->
            when (which) {
                0 -> if (on) AgentService.stop(this) else AgentService.start(this)
                1 -> askPermissions()
                2 -> startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
                3 -> showLog()
                4 -> {
                    AgentService.stop(this)
                    Store.clear(this)
                    showPairing(tr("Telefono scollegato. Per revocarlo anche sul server usa «Revoca» in PC collegati.", "Phone disconnected. To revoke it on the server too use “Revoke” in Connected PCs."))
                }
            }
        }.show()
    }

    /** What the agent did on this phone, newest first: readable even when the server does not answer. */
    private fun showLog() {
        val log = AgentService.log(this)
        val lines = log.lines()
        val padding = (12 * resources.displayMetrics.density).toInt()
        val text = TextView(this).apply {
            text = if (lines.isEmpty()) tr("Nessuna operazione registrata.", "Nothing recorded yet.") else lines.joinToString("\n")
            typeface = android.graphics.Typeface.MONOSPACE
            textSize = 12f
            setTextIsSelectable(true)
            setPadding(padding, padding, padding, padding)
        }
        AlertDialog.Builder(this).setTitle(AgentService.status.ifEmpty { tr("Registro delle operazioni", "Activity log") })
            .setView(android.widget.ScrollView(this).apply { addView(text) })
            .setPositiveButton("OK", null)
            .setNeutralButton(tr("Svuota", "Clear")) { _, _ -> log.clear() }
            .show()
    }

    private fun askPermissions() {
        val wanted = mutableListOf(Manifest.permission.ACCESS_FINE_LOCATION)
        if (Build.VERSION.SDK_INT >= 31) wanted += listOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
        if (Build.VERSION.SDK_INT >= 33) wanted += Manifest.permission.POST_NOTIFICATIONS
        requestPermissions(wanted.toTypedArray(), 1)
    }

    @Deprecated("Activity back navigation")
    override fun onBackPressed() {
        val view = web
        if (view != null && view.canGoBack()) view.goBack() else @Suppress("DEPRECATION") super.onBackPressed()
    }
}
