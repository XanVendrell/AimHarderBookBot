# 🏋️‍♂️ Bot de Reservas Automáticas de CrossFit en Aimharder

Bot en Python optimizado mediante la **API REST nativa de Aimharder** para automatizar la reserva de clases en **Singular Box Granada**.

---

## 🎯 Características
- ⚡ **Ultra Rápido:** API REST nativa (tiempos de respuesta < 1.5 segundos).
- 🪶 **Sin Navegador:** Ligero, no requiere Chrome, Playwright ni interfaz gráfica.
- 🎯 **Colección de Clases:** Configura múltiples clases, horarios y días en formato JSON.
- 📱 **Telegram Bot:** Notificaciones instantáneas de reserva confirmada, ocupación y alertas.
- ☁️ **GitHub Actions Native:** Despliegue automático en la nube sin necesidad de tener el ordenador encendido.

---

## ☁️ Despliegue en GitHub Actions (Nube Gratuita)

El bot está preparado para ejecutarse automáticamente todos los días a las **17:30:00h** en la nube de GitHub Actions sin coste.

### 1. Subir el Proyecto a GitHub (Repositorio Privado)
Por seguridad, crea un repositorio **PRIVADO** en GitHub y sube tu código:

```bash
git init
git add .
git commit -m "Initial commit - Bot Reservas Aimharder"
git branch -M main
git remote add origin https://github.com/tu_usuario/bot-reservas.git
git push -u origin main
```

### 2. Configurar los Secretos en GitHub (Secrets)
Ve a tu repositorio en GitHub:
👉 **Settings -> Secrets and variables -> Actions -> New repository secret**

Añade los siguientes secretos:

| Nombre del Secret | Valor | Ejemplo |
| :--- | :--- | :--- |
| `AIMHARDER_EMAIL` | Tu email de Aimharder | `tu_email@gmail.com` |
| `AIMHARDER_PASSWORD` | Tu contraseña de Aimharder | `TuPassword123` |
| `TELEGRAM_BOT_TOKEN` | Token del Bot de Telegram | `8838968513:AAEH...` |
| `TELEGRAM_CHAT_ID` | Tu ID de chat en Telegram | `500758526` |
| `TARGETS` *(opcional)* | Colección JSON de objetivos | `[{"name": "CrossFit (apta con experiencia)", "time": "17:30"}]` |

### 3. Ejecución Manual o Automática
- **Automático:** Correrá solo de **Domingo a Jueves a las 17:30h** (hora de España), reservando las clases a 5 días vista (Lunes a Viernes).
- **Manual:** Ve a la pestaña **Actions** en GitHub, selecciona **Bot de Reservas Aimharder**, pulsa en **Run workflow** y elige los argumentos (`--book`, `--week`, `--test`).

---

## ⚙️ Configuración Local (`.env`)

Para ejecutarlo en tu ordenador localmente, edita el archivo `.env`:

```env
# Credenciales de Aimharder
AIMHARDER_EMAIL=xelavendrell@gmail.com
AIMHARDER_PASSWORD=tu_contraseña

# Configuración del Box
BOX_URL=https://singularboxgranadaadaada.aimharder.com/
BOX_ID=9221

# Colección de Objetivos en JSON
TARGETS=[{"name": "CrossFit (apta con experiencia)", "time": "17:30", "days": [0,1,2,3,4]}]

# Configuración de Telegram
TELEGRAM_BOT_TOKEN=8838968513:AAEH...
TELEGRAM_CHAT_ID=500758526
```

---

## 💻 Uso Local del CLI (`main.py`)

```powershell
# 1. Probar notificación de Telegram
python main.py --test-telegram

# 2. Simulación sin reservar (Dry Run)
python main.py --week --test

# 3. Realizar reserva real de toda la semana (Lunes a Viernes)
python main.py --week

# 4. Realizar reserva real a 5 días vista
python main.py --book

# 5. Ejecución continua local (Daemon)
python main.py --daemon
```
