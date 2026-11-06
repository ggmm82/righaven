package org.righaven.agent.android

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import java.util.Locale
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** The pairing of this phone: server, agent and its token, kept encrypted with a key of the Android Keystore. */
data class Pairing(val server: String, val token: String, val agent: String, val name: String)

object Store {
    private const val FILE = "righaven-agent"
    private const val ALIAS = "righaven-agent-token"

    fun load(context: Context): Pairing? {
        val preferences = context.getSharedPreferences(FILE, Context.MODE_PRIVATE)
        val server = preferences.getString("server", null) ?: return null
        val sealed = preferences.getString("token", null) ?: return null
        val token = runCatching { open(sealed) }.getOrNull() ?: return null
        return Pairing(server, token, preferences.getString("agent", "") ?: "", preferences.getString("name", "") ?: "")
    }

    fun save(context: Context, pairing: Pairing) {
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE).edit()
            .putString("server", pairing.server).putString("token", seal(pairing.token))
            .putString("agent", pairing.agent).putString("name", pairing.name).apply()
    }

    fun clear(context: Context) {
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE).edit().clear().apply()
    }

    fun agentEnabled(context: Context) = context.getSharedPreferences(FILE, Context.MODE_PRIVATE).getBoolean("agent_on", true)

    fun setAgentEnabled(context: Context, on: Boolean) {
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE).edit().putBoolean("agent_on", on).apply()
    }

    private fun key(): SecretKey {
        val keystore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (keystore.getKey(ALIAS, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        return generator.generateKey()
    }

    private fun seal(text: String): String {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        return Base64.encodeToString(cipher.iv, Base64.NO_WRAP) + ":" + Base64.encodeToString(cipher.doFinal(text.toByteArray()), Base64.NO_WRAP)
    }

    private fun open(value: String): String {
        val (iv, data) = value.split(":").map { Base64.decode(it, Base64.NO_WRAP) }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, iv))
        return String(cipher.doFinal(data))
    }
}

/** Italian or English, as the phone. */
fun tr(italian: String, english: String) = if (Locale.getDefault().language == "it") italian else english
