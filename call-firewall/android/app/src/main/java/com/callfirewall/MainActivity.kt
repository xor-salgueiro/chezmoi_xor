package com.callfirewall

import android.app.Activity
import android.app.role.RoleManager
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.text.InputType
import android.view.View
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast

/** Single setup screen, built in code to keep the PoC dependency-free. */
class MainActivity : Activity() {
    private lateinit var prefs: Prefs
    private lateinit var status: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = Prefs(this)
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(40, 40, 40, 40) }

        status = TextView(this)
        root.addView(status)

        val enabled = CheckBox(this).apply { text = "Filtro activo"; isChecked = prefs.enabled }
        val server = field(root, "URL del servidor (https://…)", prefs.serverUrl)
        val token = field(root, "Token de la app", prefs.apiToken, InputType.TYPE_TEXT_VARIATION_PASSWORD)
        val country = field(root, "Prefijo por defecto (34 o 351)", prefs.countryCode, InputType.TYPE_CLASS_NUMBER)
        val assistants = field(root, "Números del asistente (separados por coma)", prefs.assistantNumbers.joinToString(","))
        root.addView(enabled)

        button(root, "1. Dar permiso de filtrado de llamadas") { requestScreeningRole() }
        button(root, "2. Guardar y sincronizar lista negra") {
            prefs.enabled = enabled.isChecked
            prefs.serverUrl = server.text.toString()
            prefs.apiToken = token.text.toString()
            prefs.countryCode = country.text.toString()
            prefs.assistantNumbers = assistants.text.split(",").mapNotNull { prefs.normalize(it) }.toSet()
            BlocklistSync.syncAsync(prefs) { r ->
                runOnUiThread {
                    toast(r.fold({ "Lista negra: $it números" }, { "Error: ${it.message}" }))
                    refresh()
                }
            }
        }

        val target = field(root, "Número del asistente para esta SIM (desvío)", "")
        root.addView(TextView(this).apply { text = "3. Desvíos (marcar en la SIM correspondiente):" })
        button(root, "Si ocupado/rechazada → asistente (**67)") { dial("**67*${target.text}#") }
        button(root, "Si no contesto en 15 s → asistente (**61)") { dial("**61*${target.text}**15#") }
        button(root, "Si sin cobertura → asistente (**62)") { dial("**62*${target.text}#") }
        button(root, "Quitar todos los desvíos (##002#)") { dial("##002#") }

        setContentView(ScrollView(this).apply { addView(root) })
        refresh()
    }

    private fun refresh() {
        val rm = getSystemService(RoleManager::class.java)
        val held = rm.isRoleHeld(RoleManager.ROLE_CALL_SCREENING)
        status.text = "Permiso de filtrado: ${if (held) "OK" else "FALTA"}\n" +
            "Lista negra: ${prefs.blocklist.size} números\n"
    }

    private fun requestScreeningRole() {
        val rm = getSystemService(RoleManager::class.java)
        startActivityForResult(rm.createRequestRoleIntent(RoleManager.ROLE_CALL_SCREENING), 1)
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        refresh()
    }

    private fun dial(code: String) = startActivity(Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + Uri.encode(code))))

    private fun toast(msg: String) = Toast.makeText(this, msg, Toast.LENGTH_LONG).show()

    private fun field(root: LinearLayout, hint: String, value: String, type: Int = InputType.TYPE_CLASS_TEXT) =
        EditText(this).apply {
            this.hint = hint
            setText(value)
            inputType = if (type == InputType.TYPE_TEXT_VARIATION_PASSWORD) InputType.TYPE_CLASS_TEXT or type else type
            root.addView(this)
        }

    private fun button(root: LinearLayout, label: String, onClick: (View) -> Unit) =
        root.addView(Button(this).apply { text = label; setOnClickListener(onClick) })
}
