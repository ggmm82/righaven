package org.righaven.agent

/** NDEF records read from an NFC tag, in readable form: text, link, MIME data, or raw bytes. */
object Ndef {
    private val URI_PREFIXES = listOf("", "http://www.", "https://www.", "http://", "https://", "tel:", "mailto:", "ftp://anonymous:anonymous@",
        "ftp://ftp.", "ftps://", "sftp://", "smb://", "nfs://", "ftp://", "dav://", "news:", "telnet://", "imap:", "rtsp://", "urn:", "pop:", "sip:",
        "sips:", "tftp:", "btspp://", "btl2cap://", "btgoep://", "tcpobex://", "irdaobex://", "file://", "urn:epc:id:", "urn:epc:tag:", "urn:epc:pat:",
        "urn:epc:raw:", "urn:epc:", "urn:nfc:")

    /** One record: TNF (3 bits), type and payload as NDEF defines them. */
    fun record(tnf: Int, type: ByteArray, payload: ByteArray): Map<String, Any?> {
        val typeText = String(type, Charsets.US_ASCII)
        return when {
            tnf == 1 && typeText == "T" && payload.isNotEmpty() -> {
                val status = payload[0].toInt() and 0xff
                val languageLength = status and 0x3f
                val charset = if (status and 0x80 != 0) Charsets.UTF_16 else Charsets.UTF_8
                val start = (1 + languageLength).coerceAtMost(payload.size)
                mapOf("kind" to "text", "language" to String(payload, 1, languageLength.coerceAtMost(payload.size - 1), Charsets.US_ASCII),
                    "text" to String(payload, start, payload.size - start, charset))
            }
            tnf == 1 && typeText == "U" && payload.isNotEmpty() ->
                mapOf("kind" to "uri", "uri" to URI_PREFIXES.getOrElse(payload[0].toInt() and 0xff) { "" } + String(payload, 1, payload.size - 1, Charsets.UTF_8))
            tnf == 2 -> mapOf("kind" to "mime", "type" to typeText, "size" to payload.size,
                "text" to (if (typeText.startsWith("text/") || typeText.endsWith("json")) String(payload, Charsets.UTF_8).take(2000) else null))
            tnf == 3 -> mapOf("kind" to "uri", "uri" to typeText)
            tnf == 4 -> mapOf("kind" to "external", "type" to typeText, "data" to hex(payload).take(512))
            else -> mapOf("kind" to "other", "tnf" to tnf, "type" to typeText, "data" to hex(payload).take(512))
        }
    }

    fun hex(bytes: ByteArray) = bytes.joinToString("") { "%02x".format(it) }
}
