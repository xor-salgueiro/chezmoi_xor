package com.callfirewall

import android.telecom.Call
import android.telecom.CallScreeningService
import android.util.Log

/**
 * Android only calls this service for numbers that are NOT in the user's contacts
 * (when the app holds ROLE_CALL_SCREENING but is not the default dialer).
 *
 * - Blocklisted  -> reject silently. The carrier treats it as busy; the server rejects it again.
 * - Unknown/hidden -> reject so the carrier's "forward when busy" (**67) sends it to the AI assistant.
 * - Assistant numbers -> allow (transfers from the assistant must ring).
 */
class FirewallScreeningService : CallScreeningService() {

    override fun onScreenCall(details: Call.Details) {
        val prefs = Prefs(this)
        if (details.callDirection != Call.Details.DIRECTION_INCOMING || !prefs.enabled) {
            respondToCall(details, allow())
            return
        }
        if (prefs.blocklistAgeMs > BlocklistSync.MAX_AGE_MS) BlocklistSync.syncAsync(prefs)

        val number = prefs.normalize(details.handle?.schemeSpecificPart)
        val response = when {
            number != null && number in prefs.assistantNumbers -> allow()
            number != null && number in prefs.blocklist -> reject()
            else -> reject() // unknown or hidden -> AI assistant via busy-forward
        }
        Log.i("CallFirewall", "screened $number")
        respondToCall(details, response)
    }

    private fun allow() = CallResponse.Builder().build()

    private fun reject() = CallResponse.Builder()
        .setDisallowCall(true)
        .setRejectCall(true)
        .setSkipNotification(true)
        .setSkipCallLog(false)
        .build()
}
