package com.callfirewall

import android.util.Log
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

/** Pulls the blocklist from the server. Runs off the main thread. */
object BlocklistSync {
    private const val TAG = "CallFirewall"
    const val MAX_AGE_MS = 15 * 60 * 1000L

    fun syncAsync(prefs: Prefs, onDone: ((Result<Int>) -> Unit)? = null) {
        thread(name = "blocklist-sync") {
            val result = runCatching { fetch(prefs) }
            result.onFailure { Log.w(TAG, "blocklist sync failed", it) }
            onDone?.invoke(result)
        }
    }

    private fun fetch(prefs: Prefs): Int {
        require(prefs.serverUrl.startsWith("https://")) { "server URL must be https" }
        val conn = URL("${prefs.serverUrl}/api/blocklist").openConnection() as HttpURLConnection
        try {
            conn.connectTimeout = 5000
            conn.readTimeout = 5000
            conn.setRequestProperty("Authorization", "Bearer ${prefs.apiToken}")
            check(conn.responseCode == 200) { "HTTP ${conn.responseCode}" }
            val body = conn.inputStream.bufferedReader().use { it.readText() }
            val arr = JSONObject(body).getJSONArray("numbers")
            val set = (0 until arr.length()).map { arr.getString(it) }.toSet()
            prefs.blocklist = set
            return set.size
        } finally {
            conn.disconnect()
        }
    }
}
