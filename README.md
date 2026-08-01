# 🏋️‍♂️ Bot Agnóstico de Reservas Automáticas de CrossFit en Aimharder

Bot genérico y ligero escrito en Python optimizado mediante la **API REST privada de Aimharder** para automatizar la reserva de clases en cualquier centro deportivo o box de CrossFit.

---

## 🎯 Características Principales
- ⚡ **Ultra Rápido:** Conexión directa a la API REST de Aimharder (tiempos de respuesta < 1.5 segundos).
- 🪶 **Sin Navegador:** No requiere Chrome, Selenium ni Playwright. 100% ligero e inmune a cambios visuales de interfaz.
- 🧩 **100% Agnóstico:** Funciona para **cualquier box**, **cualquier usuario** y **cualquier colección de clases**.
- 📅 **Colección de Objetivos (JSON):** Define múltiples clases, horarios y días de la semana.
- 📱 **Alertas por Telegram:** Notificaciones instantáneas de reserva confirmada, ocupación y avisos de apertura.
- ☁️ **GitHub Actions Native:** Ejecución programada gratuita en la nube sin necesidad de tener un servidor ni el PC encendido.

---

## ☁️ Despliegue en GitHub Actions (Nube Gratuita)

### 1. Clonar o Forkear este Repositorio
Crea una copia del repositorio en tu cuenta de GitHub (recomendado como **Repositorio Privado** por seguridad).

### 2. Configurar los Secretos en GitHub (Secrets)
En tu repositorio de GitHub, dirígete a:  
👉 **Settings -> Secrets and variables -> Actions -> New repository secret**

Añade los secretos con tus credenciales personales:

| Secret Name | Descripción | Ejemplo |
| :--- | :--- | :--- |
| `AIMHARDER_EMAIL` | Tu correo registrado en Aimharder | `tu_email@ejemplo.com` |
| `AIMHARDER_PASSWORD` | Tu contraseña de Aimharder | `TuPassword123` |
| `TELEGRAM_BOT_TOKEN` | Token del Bot de Telegram | `123456789:ABC...` |
| `TELEGRAM_CHAT_ID` | Tu ID de chat de Telegram | `987654321` |
| `BOX_URL` *(opcional)* | URL del Box en Aimharder | `https://tubox.aimharder.com/` |
| `BOX_ID` *(opcional)* | ID numérico del Box | `9221` |
| `TARGETS` *(opcional)* | Colección JSON de clases y horarios | `[{"name": "CrossFit", "time": "17:30", "days": [0,1,2,3,4]}]` |

---

## ⚙️ Configuración Local (`.env`)

Para ejecutarlo localmente en tu ordenador, crea un archivo `.env` basado en `.env.example`:

```env
# Credenciales de Aimharder
AIMHARDER_EMAIL=tu_email@ejemplo.com
AIMHARDER_PASSWORD=tu_contraseña

# Configuración del Box
BOX_URL=https://tubox.aimharder.com/
BOX_ID=9221

# Colección de Objetivos en JSON (0=Lunes, 1=Martes, ..., 4=Viernes)
TARGETS=[{"name": "CrossFit", "time": "17:30", "days": [0,1,2,3,4]}]

# Configuración de Telegram
TELEGRAM_BOT_TOKEN=tu_bot_token
TELEGRAM_CHAT_ID=tu_chat_id
```

---

## 💻 Uso Local del CLI (`main.py`)

```powershell
# 1. Probar notificaciones de Telegram
python main.py --test-telegram

# 2. Simulación de la semana (Dry Run sin reservar)
python main.py --week --test

# 3. Reserva REAL de la semana completa (Lunes a Viernes)
python main.py --week

# 4. Reserva REAL a 5 días vista
python main.py --book

# 5. Ejecución continua en segundo plano (Daemon)
python main.py --daemon
```
