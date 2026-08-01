import logging
import time
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import pytz
import requests

from config import Config, BookingTarget
from notifier import TelegramNotifier
from aimharder_client import AimharderClient

logger = logging.getLogger(__name__)
LOCAL_TZ = pytz.timezone("Europe/Madrid")

DAY_NAMES_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
DAY_SHORT_ES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

class TelegramBotListener:
    """Escuchador de Telegram guiado por Botones (Inline Keyboards)."""

    def __init__(self):
        self.token = Config.TELEGRAM_BOT_TOKEN
        self.allowed_chat_id = Config.TELEGRAM_CHAT_ID
        self.notifier = TelegramNotifier(self.token, self.allowed_chat_id)
        self.last_update_id = 0
        self.running = False
        self.drafts: Dict[str, Dict] = {}

    @property
    def is_configured(self) -> bool:
        return bool(self.token and self.allowed_chat_id)

    def start(self):
        """Inicia el bucle de escucha (Long Polling)."""
        if not self.is_configured:
            logger.error("No se puede iniciar el bot de Telegram: Token o Chat ID no configurados.")
            return

        logger.info("Iniciando bot interactivo de Telegram basado en botones...")
        self.running = True

        self.send_main_menu()

        while self.running:
            try:
                self.poll_updates()
            except Exception as e:
                logger.error(f"Excepcion en bucle de Telegram Bot: {e}")
                time.sleep(5)

    def stop(self):
        self.running = False

    def poll_updates(self):
        """Obtiene actualizaciones de Telegram."""
        url = f"https://api.telegram.org/bot{self.token}/getUpdates"
        params = {
            "offset": self.last_update_id + 1,
            "timeout": 20
        }

        try:
            resp = requests.get(url, params=params, timeout=25)
            if resp.status_code != 200:
                time.sleep(3)
                return

            data = resp.json()
            if not data.get("ok"):
                return

            updates = data.get("result", [])
            for update in updates:
                self.last_update_id = update["update_id"]
                self.process_update(update)

        except requests.exceptions.Timeout:
            pass
        except Exception as e:
            logger.error(f"Error en poll_updates: {e}")
            time.sleep(3)

    def process_update(self, update: dict):
        """Procesa mensajes de texto y clics de botones (callback_queries)."""
        if "callback_query" in update:
            cb = update["callback_query"]
            cb_id = cb["id"]
            chat_id = str(cb["message"]["chat"]["id"])
            message_id = cb["message"]["message_id"]
            data = cb.get("data", "")

            if chat_id != str(self.allowed_chat_id):
                self.notifier.answer_callback_query(cb_id, "Acceso no autorizado", show_alert=True)
                return

            self.notifier.answer_callback_query(cb_id)
            self.handle_callback(chat_id, message_id, data)
            return

        if "message" in update:
            message = update["message"]
            chat_id = str(message.get("chat", {}).get("id", ""))
            if chat_id != str(self.allowed_chat_id):
                return
            
            self.send_main_menu()

    def send_main_menu(self):
        """Envía un nuevo mensaje con el Menú Principal de botones."""
        text = "🏋️‍♂️ *Bot Aimharder - Menú Principal*\nSelecciona una opción en los botones:"
        keyboard = self.build_main_keyboard()
        self.notifier.send_message(text, reply_markup=keyboard)

    def edit_main_menu(self, message_id: int):
        """Edita un mensaje existente para mostrar el Menú Principal."""
        text = "🏋️‍♂️ *Bot Aimharder - Menú Principal*\nSelecciona una opción en los botones:"
        keyboard = self.build_main_keyboard()
        self.notifier.edit_message(message_id, text, reply_markup=keyboard)

    def build_main_keyboard(self) -> dict:
        return {
            "inline_keyboard": [
                [
                    {"text": "📋 Mis Horarios", "callback_data": "menu:targets"},
                    {"text": "➕ Añadir Horario", "callback_data": "add:step1"}
                ],
                [
                    {"text": "🗑️ Borrar Horario", "callback_data": "menu:del"},
                    {"text": "📅 Ver Parrilla", "callback_data": "menu:ver"}
                ],
                [
                    {"text": "⚡ Reservar Ahora", "callback_data": "menu:book"},
                    {"text": "📊 Estado Bot", "callback_data": "menu:status"}
                ]
            ]
        }

    def handle_callback(self, chat_id: str, message_id: int, data: str):
        logger.info(f"Callback recibido: '{data}'")

        if data in ("menu:main", "main"):
            self.edit_main_menu(message_id)

        elif data == "menu:targets":
            targets = Config.get_targets()
            if not targets:
                text = "⚠️ *No tienes horarios configurados actualmente.*"
            else:
                lines = ["📋 *Tus Clases Objetivo Configuradas:*\n"]
                for idx, t in enumerate(targets, 1):
                    days_str = ", ".join([DAY_NAMES_ES[d] for d in sorted(t.days)])
                    lines.append(f"*{idx}.* 🏋️‍♂️ *{t.name}* a las `{t.time}`h\n    📅 _{days_str}_")
                text = "\n".join(lines)

            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "➕ Añadir Horario", "callback_data": "add:step1"},
                        {"text": "🗑️ Borrar Horario", "callback_data": "menu:del"}
                    ],
                    [{"text": "🔙 Menú Principal", "callback_data": "menu:main"}]
                ]
            }
            self.notifier.edit_message(message_id, text, reply_markup=keyboard)

        elif data == "add:step1":
            self.drafts[chat_id] = {"name": "", "time": "", "days": [0, 1, 2, 3, 4]}
            self.notifier.edit_message(message_id, "⏳ *Consultando en Aimharder las clases ofertadas en tu Box...*")

            client = AimharderClient()
            class_names = client.get_available_class_types()

            text = f"➕ *Paso 1/3: Selecciona una clase de {client.box_name}:*"
            rows = []
            row = []
            for name in class_names:
                row.append({"text": f"🏋️‍♂️ {name}", "callback_data": f"add:name:{name}"})
                if len(row) == 2:
                    rows.append(row)
                    row = []
            if row:
                rows.append(row)
            rows.append([{"text": "❌ Cancelar", "callback_data": "menu:main"}])

            keyboard = {"inline_keyboard": rows}
            self.notifier.edit_message(message_id, text, reply_markup=keyboard)

        elif data.startswith("add:name:"):
            cname = data.split("add:name:")[1]
            if chat_id not in self.drafts:
                self.drafts[chat_id] = {"days": [0, 1, 2, 3, 4]}
            self.drafts[chat_id]["name"] = cname

            self.notifier.edit_message(message_id, f"⏳ *Consultando horarios en Aimharder para '{cname}'...*")
            client = AimharderClient()
            time_slots = client.get_available_times_for_class(cname)

            text = f"🏋️‍♂️ Clase: *{cname}*\n\n⏰ *Paso 2/3: Selecciona la hora de la clase:*"
            rows = []
            row = []
            for tslot in time_slots:
                row.append({"text": f"⏰ {tslot}", "callback_data": f"add:time:{tslot}"})
                if len(row) == 4:
                    rows.append(row)
                    row = []
            if row:
                rows.append(row)
            rows.append([{"text": "❌ Cancelar", "callback_data": "menu:main"}])

            keyboard = {"inline_keyboard": rows}
            self.notifier.edit_message(message_id, text, reply_markup=keyboard)

        elif data.startswith("add:time:") or data.startswith("add:toggle:") or data.startswith("add:preset:"):
            if data.startswith("add:time:"):
                ctime = data.split("add:time:")[1]
                self.drafts[chat_id]["time"] = ctime

            elif data.startswith("add:toggle:"):
                day_idx = int(data.split("add:toggle:")[1])
                current_days = self.drafts.get(chat_id, {}).get("days", [])
                if day_idx in current_days:
                    current_days.remove(day_idx)
                else:
                    current_days.append(day_idx)
                self.drafts[chat_id]["days"] = sorted(current_days)

            elif data.startswith("add:preset:"):
                preset = data.split("add:preset:")[1]
                if preset == "l-v":
                    self.drafts[chat_id]["days"] = [0, 1, 2, 3, 4]
                elif preset == "all":
                    self.drafts[chat_id]["days"] = [0, 1, 2, 3, 4, 5, 6]

            draft = self.drafts.get(chat_id, {"name": "CrossFit", "time": "18:30", "days": [0,1,2,3,4]})
            selected_days = draft.get("days", [])

            text = (
                f"🏋️‍♂️ Clase: *{draft.get('name')}*\n"
                f"⏰ Hora: *{draft.get('time')}h*\n\n"
                f"📅 *Paso 3/3: Selecciona los días tocando los botones:*"
            )

            row1 = []
            for d in range(5):
                icon = "✅" if d in selected_days else "⚪"
                row1.append({"text": f"{icon} {DAY_SHORT_ES[d]}", "callback_data": f"add:toggle:{d}"})

            row2 = []
            for d in range(5, 7):
                icon = "✅" if d in selected_days else "⚪"
                row2.append({"text": f"{icon} {DAY_SHORT_ES[d]}", "callback_data": f"add:toggle:{d}"})

            keyboard = {
                "inline_keyboard": [
                    row1,
                    row2,
                    [
                        {"text": "📅 Lunes a Viernes", "callback_data": "add:preset:l-v"},
                        {"text": "📆 Todos los días", "callback_data": "add:preset:all"}
                    ],
                    [{"text": "💾 GUARDAR HORARIO", "callback_data": "add:save"}],
                    [{"text": "❌ Cancelar", "callback_data": "menu:main"}]
                ]
            }
            self.notifier.edit_message(message_id, text, reply_markup=keyboard)

        elif data == "add:save":
            draft = self.drafts.get(chat_id)
            if not draft or not draft.get("days"):
                self.notifier.edit_message(message_id, "⚠️ *Debes seleccionar al menos 1 día.*", reply_markup={
                    "inline_keyboard": [[{"text": "🔙 Volver a selección de días", "callback_data": "add:time:" + draft.get("time", "18:30")}]]
                })
                return

            new_target = BookingTarget(name=draft["name"], time=draft["time"], days=draft["days"])
            Config.add_target(new_target)

            days_str = ", ".join([DAY_NAMES_ES[d] for d in sorted(draft["days"])])
            text = (
                f"✅ *¡Horario Objetivo Guardado con Éxito!*\n\n"
                f"🏋️‍♂️ *Clase:* {draft['name']}\n"
                f"⏰ *Hora:* {draft['time']}h\n"
                f"📅 *Días:* {days_str}"
            )
            keyboard = {
                "inline_keyboard": [
                    [{"text": "📋 Ver todos mis horarios", "callback_data": "menu:targets"}],
                    [{"text": "🔙 Menú Principal", "callback_data": "menu:main"}]
                ]
            }
            self.notifier.edit_message(message_id, text, reply_markup=keyboard)

        elif data == "menu:del":
            targets = Config.get_targets()
            if not targets:
                text = "⚠️ No hay horarios configurados para borrar."
                keyboard = {"inline_keyboard": [[{"text": "🔙 Menú Principal", "callback_data": "menu:main"}]]}
            else:
                text = "🗑️ *Toca la clase que deseas eliminar:*"
                rows = []
                for idx, t in enumerate(targets):
                    days_short = "".join([DAY_SHORT_ES[d][0] for d in sorted(t.days)])
                    label = f"❌ {t.name} {t.time}h ({days_short})"
                    rows.append([{"text": label, "callback_data": f"del:confirm:{idx}"}])
                rows.append([{"text": "🔙 Volver al Menú", "callback_data": "menu:main"}])
                keyboard = {"inline_keyboard": rows}

            self.notifier.edit_message(message_id, text, reply_markup=keyboard)

        elif data.startswith("del:confirm:"):
            idx = int(data.split("del:confirm:")[1])
            targets = Config.get_targets()
            if 0 <= idx < len(targets):
                target_del = targets[idx]
                Config.delete_target_at(idx)
                text = f"🗑️ *Horario Eliminado:* '{target_del.name}' a las {target_del.time}h."
            else:
                text = "⚠️ No se pudo encontrar el horario especificado."

            keyboard = {
                "inline_keyboard": [
                    [{"text": "📋 Ver Horarios Restantes", "callback_data": "menu:targets"}],
                    [{"text": "🔙 Menú Principal", "callback_data": "menu:main"}]
                ]
            }
            self.notifier.edit_message(message_id, text, reply_markup=keyboard)

        elif data == "menu:ver":
            text = "📅 *Selecciona qué día deseas consultar en Aimharder:*"
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "📅 Hoy", "callback_data": "ver:date:hoy"},
                        {"text": "📅 Mañana", "callback_data": "ver:date:manana"}
                    ],
                    [
                        {"text": "📆 Lunes", "callback_data": "ver:date:lunes"},
                        {"text": "📆 Martes", "callback_data": "ver:date:martes"},
                        {"text": "📆 Miércoles", "callback_data": "ver:date:miercoles"}
                    ],
                    [
                        {"text": "📆 Jueves", "callback_data": "ver:date:jueves"},
                        {"text": "📆 Viernes", "callback_data": "ver:date:viernes"}
                    ],
                    [{"text": "🔙 Menú Principal", "callback_data": "menu:main"}]
                ]
            }
            self.notifier.edit_message(message_id, text, reply_markup=keyboard)

        elif data.startswith("ver:date:"):
            date_key = data.split("ver:date:")[1]
            now = datetime.now(LOCAL_TZ)

            if date_key == "hoy":
                target_date = now
            elif date_key == "manana":
                target_date = now + timedelta(days=1)
            else:
                day_map = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4}
                t_day = day_map.get(date_key, 0)
                days_ahead = (t_day - now.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7
                target_date = now + timedelta(days=days_ahead)

            self.notifier.edit_message(message_id, f"⏳ *Consultando parrilla de Aimharder para el {target_date.strftime('%d/%m/%Y')}...*")
            client = AimharderClient()
            msg_text = client.get_formatted_day_schedule(target_date)

            keyboard = {
                "inline_keyboard": [
                    [{"text": "⚡ Reservar Mis Objetivos de Este Día", "callback_data": f"book:run:date:{target_date.strftime('%Y-%m-%d')}"}],
                    [{"text": "📅 Consultar Otro Día", "callback_data": "menu:ver"}],
                    [{"text": "🔙 Menú Principal", "callback_data": "menu:main"}]
                ]
            }
            self.notifier.edit_message(message_id, msg_text, reply_markup=keyboard)

        elif data == "menu:book":
            text = "⚡ *Menú de Reserva Directa Inmediata:*\n¿Qué deseas reservar ahora?"
            keyboard = {
                "inline_keyboard": [
                    [{"text": "⚡ Reservar Objetivos de Hoy", "callback_data": "book:run:hoy"}],
                    [{"text": "⚡ Reservar Objetivos de Mañana", "callback_data": "book:run:manana"}],
                    [{"text": "📆 Reservar Toda la Semana Completa", "callback_data": "book:run:semana"}],
                    [{"text": "🔙 Menú Principal", "callback_data": "menu:main"}]
                ]
            }
            self.notifier.edit_message(message_id, text, reply_markup=keyboard)

        elif data.startswith("book:run:"):
            run_type = data.split("book:run:")[1]
            now = datetime.now(LOCAL_TZ)

            if run_type == "hoy":
                self.notifier.edit_message(message_id, "⏳ *Ejecutando reserva de objetivos para Hoy...*")
                client = AimharderClient()
                targets = Config.get_targets()
                process_targets_for_date(client, now, targets, dry_run=False)

            elif run_type == "manana":
                target_date = now + timedelta(days=1)
                self.notifier.edit_message(message_id, f"⏳ *Ejecutando reserva de objetivos para Mañana ({target_date.strftime('%d/%m/%Y')})...*")
                client = AimharderClient()
                targets = Config.get_targets()
                process_targets_for_date(client, target_date, targets, dry_run=False)

            elif run_type.startswith("date:"):
                d_str = run_type.split("date:")[1]
                target_date = datetime.strptime(d_str, "%Y-%m-%d")
                self.notifier.edit_message(message_id, f"⏳ *Ejecutando reserva para el {target_date.strftime('%d/%m/%Y')}...*")
                client = AimharderClient()
                targets = Config.get_targets()
                process_targets_for_date(client, target_date, targets, dry_run=False)

            elif run_type == "semana":
                self.notifier.edit_message(message_id, "⏳ *Ejecutando reserva semanal completa (Lunes a Viernes)...*")
                handle_week(Config.get_targets(), dry_run=False)

            keyboard = {
                "inline_keyboard": [
                    [{"text": "🔙 Menú Principal", "callback_data": "menu:main"}]
                ]
            }
            self.notifier.send_message("✅ *Proceso de reserva finalizado.*", reply_markup=keyboard)

        elif data == "menu:status":
            self.notifier.edit_message(message_id, "⏳ *Comprobando conexión con Aimharder...*")
            client = AimharderClient()
            ok = client.login()

            if ok:
                status_text = (
                    f"✅ *Estado del Bot: ONLINE*\n\n"
                    f"👤 *Usuario:* {client.user_name}\n"
                    f"🏋️‍♂️ *Box:* {client.box_name} (ID: {client.box_id})\n"
                    f"🎯 *Horarios activos:* {len(Config.get_targets())}\n"
                    f"📡 *API Aimharder:* Conectado y Autenticado"
                )
            else:
                status_text = (
                    f"❌ *Estado del Bot: ERROR DE SESIÓN*\n\n"
                    f"No se pudo iniciar sesión en Aimharder. Comprueba las credenciales en `.env`."
                )

            keyboard = {
                "inline_keyboard": [
                    [{"text": "🔄 Recomprobar", "callback_data": "menu:status"}],
                    [{"text": "🔙 Menú Principal", "callback_data": "menu:main"}]
                ]
            }
            self.notifier.edit_message(message_id, status_text, reply_markup=keyboard)

def process_targets_for_date(client: AimharderClient, target_date: datetime, targets: List[BookingTarget], dry_run: bool = False):
    date_weekday = target_date.weekday()
    for target in targets:
        if date_weekday in target.days:
            client.book_target(target, target_date=target_date, dry_run=dry_run)
            time.sleep(0.5)

def handle_week(targets: List[BookingTarget], dry_run: bool = False):
    today = datetime.now(LOCAL_TZ)
    days_ahead = (0 - today.weekday()) % 7
    if days_ahead == 0 and today.hour >= 18:
        days_ahead = 7
    monday = today + timedelta(days=days_ahead)

    client = AimharderClient()
    for day_offset in range(5):
        target_date = monday + timedelta(days=day_offset)
        process_targets_for_date(client, target_date, targets, dry_run=dry_run)
        time.sleep(0.5)
