# Call Firewall: asistente IA de llamadas (PoC)

Filtra todas las llamadas de tus líneas Digi (ES y PT). Un asistente IA contesta, hace el triage y te avisa por Telegram.

## Reglas de triage

| # | Quién llama | Tu estado | Resultado |
|---|---|---|---|
| R1 | Contacto | Libre | Suena directo en tu móvil. Sin IA |
| R2 | Contacto | Ocupado (Google Calendar u horas de silencio) | La IA dice que estás ocupado y pregunta el motivo. Te pasa la llamada con aviso previo ("pulse 1"). Si no aceptas, toma el recado |
| R3 | Desconocido u oculto | Cualquiera | La IA pregunta nombre, motivo y número de contacto. Te lo envía por Telegram. Promete devolver la llamada |
| R4 | Desconocido | Silencio, robot, venta o se niega a identificarse | Cuelga y lo añade a la lista negra |
| R5 | En lista negra | Cualquiera | Rechazo inmediato, sin IA |

Si un contacto llama, estás libre y no contestas, la IA toma el recado.

## Arquitectura

```
Llamada ──► Tu línea Digi ──► Móvil Android
                                 │
     ┌───────────────────────────┼─────────────────────────────┐
     │ Contacto                  │ Desconocido / lista negra   │
     │  libre: suena (R1)        │  la app la RECHAZA          │
     │  ocupado: No Molestar     │                             │
     │  → no contestas (15 s)    │                             │
     ▼                           ▼                             │
 Desvío **61 (no contesta)   Desvío **67 (ocupado)             │
     └──────────────┬────────────┘                             │
                    ▼                                          │
     Número del asistente (Twilio, uno por país)               │
                    ▼                                          │
     Servidor callfw ── Google Contacts + Calendar             │
        │  triage (triage.py)                                  │
        │  voz: Twilio ConversationRelay (STT + TTS)           │
        │  cerebro: Claude Haiku 5.5                           │
        ├─► Telegram: recado / bloqueo                         │
        └─► R2: te llama desde el número del asistente ◄───────┘
                (la app lo deja pasar siempre)
```

## Por qué hace falta un número del asistente

Pediste resolverlo todo con tus líneas, sin un número de terceros. **Con una app de Android normal no es posible.**

- Android no deja a una app de terceros leer ni inyectar el audio de una llamada. La fuente `VOICE_CALL` está reservada a apps de sistema desde Android 10. Por eso Google solo lo ofrece en Pixel.
- Sin acceso al audio, la IA no puede hablar dentro de tu llamada. Alguien tiene que contestar fuera del móvil.

| Alternativa | ¿Sin número de terceros? | Problema |
|---|---|---|
| Altavoz + micrófono (la app "habla" al aire) | Sí | Mala calidad y eco. Todos a tu alrededor oyen la llamada. No es un producto |
| Móvil rooteado / ROM propia | Sí | Rompe la seguridad del móvil y las apps bancarias. Inviable para otros usuarios |
| **Pasarela propia:** una SIM Digi extra en una Raspberry Pi con módem 4G y Asterisk | Sí: **todos los números son tuyos** | ~80-120 € de hardware, más una línea Digi extra por país. Más mantenimiento |
| **Twilio (PoC actual)** | No | Depende de un proveedor. Es lo más rápido para validar la idea |

**Decisión:** el PoC usa Twilio para validar la idea en días. La telefonía está aislada en `server/callfw/main.py` y `twiml.py`. La fase 2 puede cambiarla por la pasarela propia sin tocar el triage, la IA ni Telegram.

La IA y la voz (Anthropic, Twilio y Google) siempre son servicios en la nube. Ninguna opción lo evita sin hardware potente en casa.

## Componentes

- `server/`: Python (FastAPI).
  - `triage.py`: reglas puras, con pruebas.
  - `agent.py`: conversación con Claude Haiku 5.5. Salida JSON validada con esquema. Razonamiento desactivado y `effort: low` para reducir la latencia.
  - `main.py`: webhooks de Twilio, WebSocket de ConversationRelay, transferencia con aviso previo y API de la lista negra para la app.
  - `google_api.py`: contactos (People API) y ocupado/libre (Calendar).
  - `telegram.py`: avisos.
  - `store.py`: SQLite (lista negra y registro de llamadas).
- `android/`: app Kotlin, sin dependencias externas.
  - `FirewallScreeningService`: rechaza desconocidos y números de la lista negra para que salten al asistente.
  - Pantalla de configuración: permiso de filtrado, servidor, sincronización y botones que marcan los códigos de desvío.

## Puesta en marcha

1. **Prueba de desvío en Digi** (gratis, antes de pagar nada). En cada SIM:
   - Marca `**67*<móvil de un amigo>#`. Llámate desde otro móvil y **rechaza**. ¿Suena en el de tu amigo?
   - Comprueba que tu amigo ve **el número de quien llamaba**, no el tuyo.
   - Desactiva con `##002#`.
2. **Twilio:** crea la cuenta y compra un número español (+34) y otro portugués (+351). Hay que presentar documentación regulatoria (dirección e identificación).
3. **Google:** sigue `server/scripts/google_auth.py`. Obtendrás el *refresh token* para contactos y calendario (solo lectura).
4. **Telegram:** habla con @BotFather y crea el bot. Envíale un mensaje y obtén tu `chat_id`.
5. **Servidor:** copia `server/.env.example` a `.env` y rellénalo. Despliega con el `Dockerfile` en un VPS con HTTPS (Caddy o un túnel de Cloudflare).
6. En Twilio, configura cada número: *A call comes in* → Webhook `POST https://<tu-servidor>/twilio/voice`.
7. **Móvil:**
   - Instala la app (abre `android/` en Android Studio).
   - Dale el permiso de filtrado y rellena la configuración.
   - Guarda los dos números del asistente como **contacto favorito** "Asistente".
   - Activa **No Molestar → Programación → Evento** (calendario de Google). Permite llamadas de **favoritos** para tus VIP y para el asistente.
   - Activa en cada SIM los desvíos `**67`, `**61` (15 s) y `**62` hacia el número del asistente de su país.

## Coste estimado (PoC)

| Concepto | €/mes | Estado |
|---|---|---|
| 2 números Twilio (ES + PT) | 2-30 | No verificado: depende del tipo de número |
| Voz (ConversationRelay + minutos), ~30 min | ~3-5 | Estimación |
| Claude Haiku 5.5 | < 0,20 | 0,10 $ / 0,50 $ por millón de tokens |
| VPS | 0-5 | |

## Riesgos y verificaciones pendientes

- [ ] Digi ES/PT: ¿el rechazo activa el desvío `**67`? ¿Se conserva el número original al desviar?
- [ ] Coste de los desvíos en Digi hacia números nacionales.
- [ ] Twilio: disponibilidad y precio de números +34/+351 y de ConversationRelay en es-ES/pt-PT.
- [ ] El temporizador de transferencia (`TRANSFER_RING_S=12`) debe ser menor que el de `**61` (15 s), para evitar bucles. Hay además una protección en el servidor: rechaza llamadas que vienen del propio número del asistente.
- [ ] La despedida de la IA usa `<Say>` de Twilio. Su voz puede no coincidir con la de ConversationRelay.
- [ ] La app Android no se ha compilado en el entorno de desarrollo (no había Android SDK).
- [ ] Legal: el saludo declara que es una IA (AI Act, art. 50). No se graba audio: solo se guarda el resumen.

## Pruebas

```
cd server && python -m venv .venv && .venv/bin/pip install -e '.[dev]' && .venv/bin/pytest
```
