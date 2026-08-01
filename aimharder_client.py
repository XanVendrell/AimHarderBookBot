import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests

from config import Config, BookingTarget
from notifier import TelegramNotifier

logger = logging.getLogger(__name__)

DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

class AimharderClient:
    """Cliente HTTP agnóstico para la API REST privada de Aimharder."""

    LOGIN_URL = "https://aimharder.com/api/login"
    
    def __init__(self):
        self.box_url = Config.BOX_URL
        self.box_id = Config.BOX_ID
        self.box_name = Config.BOX_NAME
        self.email = Config.EMAIL
        self.password = Config.PASSWORD
        self.notifier = TelegramNotifier()
        self.session = requests.Session()
        
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://aimharder.com",
            "Referer": "https://aimharder.com/login"
        })
        self.user_name: Optional[str] = None

    def login(self) -> bool:
        """Autentica contra la API REST de Aimharder y recupera la sesión del atleta."""
        logger.info("Iniciando sesion en la API de Aimharder...")
        payload = {
            "username": self.email,
            "password": self.password,
            "fingerprint": "df75ab591aaf5c00a54bb34cbfc5c36b3b703dc3ada55ab808",
            "iniframe": 0
        }

        try:
            resp = self.session.post(self.LOGIN_URL, json=payload, timeout=10)
            if resp.status_code != 200:
                logger.error(f"Error de red en login: HTTP {resp.status_code}")
                return False

            data = resp.json()
            if "error" in data:
                err_msg = data["error"].get("message", "Error desconocido")
                logger.error(f"Error de autenticacion: {err_msg}")
                self.notifier.send_message(f"❌ *Bot Aimharder:* Error de autenticación en la API ({err_msg}). Revisa las credenciales.")
                return False

            user_data = data.get("data", {}).get("userData", {})
            self.user_name = user_data.get("name", "Atleta")
            
            roles = user_data.get("roles", [])
            for r in roles:
                gym = r.get("gym")
                if gym:
                    self.box_name = gym
                    break

            logger.info(f"Sesion iniciada con exito. Atleta: {self.user_name}, Box: {self.box_name} (ID: {self.box_id})")
            return True

        except Exception as e:
            logger.error(f"Excepcion durante el login en API: {e}", exc_info=True)
            return False

    def get_day_bookings(self, target_date: datetime) -> List[Dict]:
        """Obtiene la lista de clases/reservas en formato JSON para la fecha solicitada."""
        day_str = target_date.strftime("%Y%m%d")
        url = f"{self.box_url}/api/bookings"
        params = {
            "day": day_str,
            "familyId": "",
            "box": self.box_id
        }
        headers = {
            "Referer": f"{self.box_url}/schedule?cl"
        }

        try:
            resp = self.session.get(url, params=params, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("bookings", [])
            else:
                logger.error(f"Error consultando clases para {day_str}: HTTP {resp.status_code}")
                return []
        except Exception as e:
            logger.error(f"Excepcion al obtener clases para {day_str}: {e}")
            return []

    def get_formatted_day_schedule(self, target_date: datetime) -> str:
        """Obtiene la parrilla de clases del día y devuelve un resumen formateado para Telegram."""
        if not self.user_name:
            if not self.login():
                return "❌ *Error:* No se pudo iniciar sesión en Aimharder. Revisa las credenciales."

        day_name = DIAS_SEMANA[target_date.weekday()]
        date_str = target_date.strftime("%d/%m/%Y")
        bookings = self.get_day_bookings(target_date)

        if not bookings:
            return f"ℹ️ No hay clases encontradas para el *{day_name} {date_str}*."

        lines = [f"📅 *Parrilla de Clases - {day_name} {date_str}:*\n"]
        for b in bookings:
            time_slot = b.get("time", "??:??")
            cname = b.get("className", "Clase")
            coach = b.get("coachName", "N/A")
            ocupation = b.get("ocupation", 0)
            capacity = b.get("limit", 0)
            book_state = b.get("bookState")

            status_str = "🟢"
            if book_state in ("booked", "reserved", 1):
                status_str = "✅ *(Reservado por ti)*"
            elif capacity > 0 and ocupation >= capacity:
                status_str = "🔴 *(Completo)*"

            lines.append(f"• `{time_slot}` | *{cname}* ({ocupation}/{capacity}) - Coach: {coach} {status_str}")

        return "\n".join(lines)

    def get_available_class_types(self) -> List[str]:
        """Consulta los próximos días en la API de Aimharder y recupera todos los tipos de clases únicos ofertados en el Box."""
        if not self.user_name:
            if not self.login():
                return ["CrossFit", "Open"]

        class_names = set()
        now = datetime.now()
        for offset in range(5):
            target_date = now + timedelta(days=offset)
            bookings = self.get_day_bookings(target_date)
            for b in bookings:
                cname = b.get("className")
                if cname and cname.strip():
                    class_names.add(cname.strip())

        if class_names:
            return sorted(list(class_names))
        return ["CrossFit", "Open"]

    def get_available_times_for_class(self, class_name: str) -> List[str]:
        """Recupera los horarios reales en los que se imparte la clase seleccionada."""
        times = set()
        now = datetime.now()
        for offset in range(5):
            target_date = now + timedelta(days=offset)
            bookings = self.get_day_bookings(target_date)
            for b in bookings:
                cname = b.get("className", "")
                tslot = b.get("time", "")
                if class_name.lower() in cname.lower() or cname.lower() in class_name.lower() or ("crossfit" in class_name.lower() and "crossfit" in cname.lower()):
                    if tslot and tslot.strip():
                        times.add(tslot.strip())

        if times:
            return sorted(list(times))
        return ["07:00", "08:00", "09:00", "10:00", "17:30", "18:30", "19:30", "20:30"]

    def find_target_class(self, bookings: List[Dict], target_time: str, class_name_filter: str) -> Optional[Dict]:
        """Localiza en la lista de reservas la sesión que coincide con la hora y el nombre deseados."""
        for b in bookings:
            time_slot = b.get("time", "")
            cname = b.get("className", "")
            
            if target_time in time_slot:
                if class_name_filter.lower() in cname.lower() or ("crossfit" in class_name_filter.lower() and "crossfit" in cname.lower()):
                    return b
        return None

    def book_target(self, target: BookingTarget, target_date: datetime, dry_run: bool = False) -> bool:
        """Procesa un objetivo/regla de reserva específico (BookingTarget)."""
        return self.book_class(
            target_date=target_date,
            target_time=target.time,
            target_class_name=target.name,
            dry_run=dry_run
        )

    def book_class(self, target_date: datetime, target_time: Optional[str] = None, target_class_name: Optional[str] = None, dry_run: bool = False) -> bool:
        """Ejecuta el flujo completo de consulta y reserva para una fecha, hora y clase determinadas."""
        target_time = target_time or Config.TARGET_TIME
        class_filter = target_class_name or Config.TARGET_CLASS_NAME
        
        day_name = DIAS_SEMANA[target_date.weekday()]
        full_date_str = f"{day_name} {target_date.strftime('%d/%m/%Y')}"
        day_compact = target_date.strftime("%Y%m%d")
        
        logger.info(f"Procesando reserva API: '{class_filter}' a las {target_time} el {full_date_str} (Dry run: {dry_run})...")

        if not self.user_name:
            if not self.login():
                return False

        bookings = self.get_day_bookings(target_date)
        if not bookings:
            logger.warning(f"No se recibieron clases del servidor para el dia {full_date_str}.")
            return False

        target_booking = self.find_target_class(bookings, target_time, class_filter)
        if not target_booking:
            logger.info(f"La clase '{class_filter}' a las {target_time} no esta programada para el dia {full_date_str}.")
            return False

        booking_id = target_booking.get("id")
        class_name = target_booking.get("className")
        coach_name = target_booking.get("coachName", "Sin asignar")
        ocupation = target_booking.get("ocupation", 0)
        capacity = target_booking.get("limit", 18)
        book_state = target_booking.get("bookState")

        logger.info(f"Clase localizada: ID {booking_id} | '{class_name}' {target_time} (Coach: {coach_name}, Plazas: {ocupation}/{capacity})")

        if book_state in ("booked", "reserved", 1):
            logger.info(f"La clase '{class_name}' a las {target_time}h el {full_date_str} ya estaba reservada previamente.")
            self.notifier.send_message(f"ℹ️ *Bot Aimharder:* La clase '{class_name}' a las {target_time}h el {full_date_str} ya estaba reservada previamente.")
            return True

        if dry_run:
            logger.info(f"Simulacion de reserva para {class_name} a las {target_time}h el {full_date_str}.")
            msg = (f"🧪 *[SIMULACIÓN (DRY RUN)]*\n\n"
                   f"🏋️‍♂️ *Clase:* {class_name}\n"
                   f"📅 *Fecha:* {full_date_str} a las {target_time}h\n"
                   f"👨‍🏫 *Entrenador:* {coach_name}\n"
                   f"📊 *Ocupación:* {ocupation}/{capacity}")
            self.notifier.send_message(msg)
            return True

        logger.info(f"Enviando solicitud de reserva REAL (ID {booking_id})...")
        book_url = f"{self.box_url}/api/book"
        headers = {
            "Referer": f"{self.box_url}/schedule?cl",
            "Origin": self.box_url
        }
        payload = {
            "id": booking_id,
            "day": day_compact,
            "insist": 0,
            "familyId": ""
        }

        try:
            resp = self.session.post(book_url, data=payload, headers=headers, timeout=10)
            if resp.status_code == 200:
                res_data = resp.json()
                logger.info(f"Respuesta del servidor Aimharder: {res_data}")
                
                state = res_data.get("bookState")
                if state in (1, 0):
                    logger.info(f"Reserva confirmada para {class_name} el {full_date_str}.")
                    success_msg = (f"✅ *¡Reserva Confirmada!*\n\n"
                                   f"🏋️‍♂️ *Clase:* {class_name}\n"
                                   f"📅 *Fecha:* {full_date_str} a las {target_time}h\n"
                                   f"👨‍🏫 *Entrenador:* {coach_name}")
                    self.notifier.send_message(success_msg)
                    return True
                elif state == -1:
                    logger.warning(f"Clase completa: {class_name} el {full_date_str}.")
                    self.notifier.send_message(f"⚠️ *Bot Aimharder:* La clase '{class_name}' a las {target_time}h el {full_date_str} está completa.")
                    return False
                elif state == -2:
                    logger.warning(f"Limite de reservas alcanzado para {full_date_str}.")
                    self.notifier.send_message(f"⚠️ *Bot Aimharder:* Has agotado tus reservas permitidas para el {full_date_str}.")
                    return False
                elif state == -12:
                    logger.info(f"Reserva aun no abierta para {full_date_str}.")
                    self.notifier.send_message(f"⏳ *Bot Aimharder:* La reserva para el {full_date_str} a las {target_time}h aún no está abierta.")
                    return False
                else:
                    logger.warning(f"Estado de respuesta inesperado: {res_data}")
                    self.notifier.send_message(f"⚠️ *Bot Aimharder:* Estado no esperado: {res_data}")
                    return False
            else:
                logger.error(f"Error HTTP en reserva: {resp.status_code} - {resp.text}")
                self.notifier.send_message(f"❌ *Bot Aimharder Error:* Error al reservar clase {full_date_str} (HTTP {resp.status_code}).")
                return False
        except Exception as e:
            logger.error(f"Excepcion enviando reserva: {e}", exc_info=True)
            self.notifier.send_message(f"❌ *Bot Aimharder Error:* {e}")
            return False
