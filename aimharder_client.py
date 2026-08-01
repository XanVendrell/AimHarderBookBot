import logging
from datetime import datetime
from typing import Dict, List, Optional
import requests

from config import Config, BookingTarget
from notifier import TelegramNotifier

logger = logging.getLogger(__name__)

class AimharderClient:
    """Cliente HTTP optimizado para interactuar con la API REST privada de Aimharder."""

    LOGIN_URL = "https://aimharder.com/api/login"
    
    def __init__(self):
        self.box_url = Config.BOX_URL
        self.box_id = Config.BOX_ID
        self.email = Config.EMAIL
        self.password = Config.PASSWORD
        self.notifier = TelegramNotifier()
        self.session = requests.Session()
        
        # Headers estándar de navegador
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://aimharder.com",
            "Referer": "https://aimharder.com/login"
        })
        self.user_name: Optional[str] = None

    def login(self) -> bool:
        """Autentica contra la API REST de Aimharder y recupera las cookies de sesión."""
        logger.info("Iniciando sesión en la API de Aimharder...")
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
                logger.error(f"Error de autenticación: {err_msg}")
                self.notifier.send_message(f"❌ *Bot Aimharder:* Error de autenticación en la API ({err_msg}). Revisa .env.")
                return False

            user_data = data.get("data", {}).get("userData", {})
            self.user_name = user_data.get("name", "Atleta")
            logger.info(f"¡Sesión iniciada con éxito! Atleta: {self.user_name}, Box ID: {self.box_id}")
            return True

        except Exception as e:
            logger.error(f"Excepción durante el login en API: {e}", exc_info=True)
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
            logger.error(f"Excepción al obtener clases para {day_str}: {e}")
            return []

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
        """
        Ejecuta el flujo completo de consulta y reserva para una fecha, hora y clase determinadas.
        """
        target_time = target_time or Config.TARGET_TIME
        class_filter = target_class_name or Config.TARGET_CLASS_NAME
        date_str = target_date.strftime("%d/%m/%Y")
        day_compact = target_date.strftime("%Y%m%d")
        
        logger.info(f"Procesando reserva API: '{class_filter}' a las {target_time} el {date_str} (Dry run: {dry_run})...")

        # 1. Login (si no se ha iniciado sesión previamente)
        if not self.user_name:
            if not self.login():
                return False

        # 2. Obtener parrilla del día
        bookings = self.get_day_bookings(target_date)
        if not bookings:
            logger.warning(f"No se recibieron clases del servidor para el día {date_str}.")
            return False

        # 3. Filtrar la clase objetivo
        target_booking = self.find_target_class(bookings, target_time, class_filter)
        if not target_booking:
            msg = f"ℹ️ La clase '{class_filter}' a las {target_time} no está programada para el día {date_str}."
            logger.info(msg)
            return False

        booking_id = target_booking.get("id")
        class_name = target_booking.get("className")
        coach_name = target_booking.get("coachName", "Sin asignar")
        ocupation = target_booking.get("ocupation", 0)
        capacity = target_booking.get("limit", 18)
        book_state = target_booking.get("bookState")

        logger.info(f"Clase localizada: ID {booking_id} | '{class_name}' {target_time} (Coach: {coach_name}, Plazas: {ocupation}/{capacity})")

        # Verificar si ya está reservada previamente por el usuario
        if book_state in ("booked", "reserved", 1):
            msg = f"ℹ️ La clase de las {target_time} el {date_str} ('{class_name}') ya estaba reservada previamente."
            logger.info(msg)
            self.notifier.send_message(f"ℹ️ *Bot Aimharder:* {msg}")
            return True

        if dry_run:
            msg = (f"🧪 *[SIMULACIÓN (DRY RUN)]*\n\n"
                   f"🏋️‍♂️ *Clase:* {class_name}\n"
                   f"📅 *Fecha:* {date_str} a las {target_time}\n"
                   f"👤 *Atleta:* {self.user_name}\n"
                   f"👨‍🏫 *Entrenador:* {coach_name}\n"
                   f"📊 *Ocupación:* {ocupation}/{capacity}\n"
                   f"🆔 *ID Sesión:* {booking_id}")
            logger.info(msg.replace("*", ""))
            self.notifier.send_message(msg)
            return True

        # 4. Solicitud de Reserva REAL (POST /api/book)
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
                    ticket_id = res_data.get("id", "N/A")
                    success_msg = (f"✅ *¡Reserva Confirmada!*\n\n"
                                   f"🏋️‍♂️ *Clase:* {class_name}\n"
                                   f"📅 *Fecha:* {date_str} a las {target_time}\n"
                                   f"👤 *Atleta:* {self.user_name}\n"
                                   f"📍 *Box:* Singular Box Granada\n"
                                   f"🎟️ *Ticket ID:* {ticket_id}")
                    logger.info(success_msg.replace("*", ""))
                    self.notifier.send_message(success_msg)
                    return True
                elif state == -1:
                    msg = f"⚠️ La clase '{class_name}' a las {target_time} el {date_str} está completa."
                    logger.warning(msg)
                    self.notifier.send_message(f"⚠️ *Bot Aimharder:* {msg}")
                    return False
                elif state == -2:
                    msg = f"⚠️ Has agotado tus reservas permitidas para el {date_str}."
                    logger.warning(msg)
                    self.notifier.send_message(f"⚠️ *Bot Aimharder:* {msg}")
                    return False
                elif state == -12:
                    msg = f"⏳ La reserva para el {date_str} a las {target_time} aún no está abierta (antelación máxima de 5 días / 120h)."
                    logger.info(msg)
                    self.notifier.send_message(f"⏳ *Bot Aimharder:* {msg}")
                    return False
                else:
                    msg = f"⚠️ Estado de respuesta no esperado: {res_data}"
                    logger.warning(msg)
                    self.notifier.send_message(f"⚠️ *Bot Aimharder:* {msg}")
                    return False
            else:
                logger.error(f"Error HTTP en reserva: {resp.status_code} - {resp.text}")
                self.notifier.send_message(f"❌ *Bot Aimharder Error:* Error al reservar clase {date_str} (HTTP {resp.status_code}).")
                return False
        except Exception as e:
            logger.error(f"Excepción enviando reserva: {e}", exc_info=True)
            self.notifier.send_message(f"❌ *Bot Aimharder Error:* {e}")
            return False
