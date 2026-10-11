package com.callfirewall

import android.content.Context
import android.content.SharedPreferences

/** Settings and cached blocklist, shared by the activity and the screening service. */
class Prefs(context: Context) {
    private val sp: SharedPreferences = context.getSharedPreferences("callfw", Context.MODE_PRIVATE)

    var enabled: Boolean
        get() = sp.getBoolean("enabled", true)
        set(v) = sp.edit().putBoolean("enabled", v).apply()

    var serverUrl: String
        get() = sp.getString("server_url", "") ?: ""
        set(v) = sp.edit().putString("server_url", v.trimEnd('/')).apply()

    var apiToken: String
        get() = sp.getString("api_token", "") ?: ""
        set(v) = sp.edit().putString("api_token", v.trim()).apply()

    /** Default country code for numbers without prefix, e.g. "34". */
    var countryCode: String
        get() = sp.getString("country_code", "34") ?: "34"
        set(v) = sp.edit().putString("country_code", v.trim().trimStart('+')).apply()

    /** Assistant (Twilio) numbers: always allowed, they carry transfers. */
    var assistantNumbers: Set<String>
        get() = sp.getStringSet("assistant_numbers", emptySet()) ?: emptySet()
        set(v) = sp.edit().putStringSet("assistant_numbers", v).apply()

    var blocklist: Set<String>
        get() = sp.getStringSet("blocklist", emptySet()) ?: emptySet()
        set(v) = sp.edit().putStringSet("blocklist", v).putLong("blocklist_at", System.currentTimeMillis()).apply()

    val blocklistAgeMs: Long
        get() = System.currentTimeMillis() - sp.getLong("blocklist_at", 0)

    /** Best-effort E.164: enough to compare with the server blocklist. */
    fun normalize(raw: String?): String? {
        if (raw.isNullOrBlank()) return null
        val plus = raw.trim().startsWith("+")
        var digits = raw.filter { it.isDigit() }
        if (digits.isEmpty()) return null
        return when {
            plus -> "+$digits"
            digits.startsWith("00") -> "+" + digits.drop(2)
            else -> { digits = digits.trimStart('0'); "+$countryCode$digits" }
        }
    }
}
