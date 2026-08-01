import logging
from typing import Optional
import requests
from config import Config

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """Módulo de envío de notificaciones y alertas a través del Bot API de Telegram."""
    
    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        self.token = token or Config.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or Config.TELEGRAM_CHAT_ID

    @property
    def is_configured(self) -> bool:
        return bool(self.token and self.chat_id)

    def send_message(self, text: str, reply_markup: Optional[dict] = None) -> bool:
        """Envía un mensaje de texto formateado en Markdown a Telegram con botones opcionales."""
        if not self.is_configured:
            logger.debug("Telegram no está configurado. Se omite el envío.")
            return False

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            response = requests.post(url, json=payload, timeout=10)
            res_json = response.json()
            if response.status_code == 200 and res_json.get("ok"):
                logger.info("Notificación de Telegram enviada con éxito.")
                return True
            else:
                logger.error(f"Error al enviar mensaje a Telegram: {res_json}")
                return False
        except Exception as e:
            logger.error(f"Excepción enviando notificación por Telegram: {e}")
            return False

    def edit_message(self, message_id: int, text: str, reply_markup: Optional[dict] = None) -> bool:
        """Edita un mensaje existente en Telegram con nuevo texto y/o botones."""
        if not self.is_configured:
            return False

        url = f"https://api.telegram.org/bot{self.token}/editMessageText"
        payload = {
            "chat_id": self.chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup

        try:
            response = requests.post(url, json=payload, timeout=10)
            res_json = response.json()
            return response.status_code == 200 and res_json.get("ok", False)
        except Exception as e:
            logger.error(f"Excepción editando mensaje en Telegram: {e}")
            return False

    def answer_callback_query(self, callback_query_id: str, text: str = "", show_alert: bool = False) -> bool:
        """Responde a un callback_query para quitar el icono de carga del botón."""
        if not self.is_configured:
            return False

        url = f"https://api.telegram.org/bot{self.token}/answerCallbackQuery"
        payload = {
            "callback_query_id": callback_query_id,
            "text": text,
            "show_alert": show_alert
        }
        try:
            response = requests.post(url, json=payload, timeout=5)
            return response.status_code == 200
        except Exception:
            return False


    def send_photo(self, photo_path: str, caption: str = "") -> bool:
        """Envía una foto/comprobante a Telegram."""
        if not self.is_configured:
            return False

        url = f"https://api.telegram.org/bot{self.token}/sendPhoto"
        try:
            with open(photo_path, "rb") as photo_file:
                files = {"photo": photo_file}
                data = {
                    "chat_id": self.chat_id,
                    "caption": caption,
                    "parse_mode": "Markdown"
                }
                response = requests.post(url, data=data, files=files, timeout=15)
                res_json = response.json()
                if response.status_code == 200 and res_json.get("ok"):
                    logger.info("Imagen enviada a Telegram con éxito.")
                    return True
                else:
                    logger.error(f"Error enviando imagen a Telegram: {res_json}")
                    return False
        except Exception as e:
            logger.error(f"Excepción enviando foto a Telegram: {e}")
            return False
