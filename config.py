import json
import os
from typing import List
from dotenv import load_dotenv

# Cargar variables de entorno con override inmediato
load_dotenv(override=True)

class BookingTarget:
    """Representa un objetivo/regla de reserva específica (nombre de clase, hora y días)."""
    def __init__(self, name: str, time: str, days: List[int]):
        self.name = name.strip()
        self.time = time.strip()
        self.days = days

    def __repr__(self):
        return f"<BookingTarget name='{self.name}' time='{self.time}' days={self.days}>"

class Config:
    EMAIL: str = (os.getenv("AIMHARDER_EMAIL") or "").strip()
    PASSWORD: str = (os.getenv("AIMHARDER_PASSWORD") or "").strip()
    BOX_URL: str = (os.getenv("BOX_URL") or "https://singularboxgranadaadaada.aimharder.com/").strip().rstrip('/')
    BOX_ID: str = (os.getenv("BOX_ID") or "9221").strip()
    
    TARGET_TIME: str = (os.getenv("TARGET_TIME") or "17:30").strip()
    TARGET_CLASS_NAME: str = (os.getenv("TARGET_CLASS_NAME") or "CrossFit (apta con experiencia)").strip()
    
    _raw_days: str = (os.getenv("TARGET_DAYS") or "0,1,2,3,4").strip()
    TARGET_DAYS: List[int] = [int(d.strip()) for d in _raw_days.split(",") if d.strip().isdigit()]
    DAYS_AHEAD: int = int(os.getenv("DAYS_AHEAD") or "5")
    
    TELEGRAM_BOT_TOKEN: str = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    TELEGRAM_CHAT_ID: str = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()

    @classmethod
    def get_targets(cls) -> List[BookingTarget]:
        """
        Recupera la colección de objetivos de reserva definidos en .env.
        Soporta formato JSON en TARGETS con múltiples clases, horas y días.
        Ejemplo:
        TARGETS=[{"name": "CrossFit (apta con experiencia)", "time": "17:30", "days": [0,1,2,3,4]}]
        """
        raw_json = (os.getenv("TARGETS") or "").strip()
        if raw_json:
            try:
                items = json.loads(raw_json)
                targets = []
                for item in items:
                    name = item.get("name", cls.TARGET_CLASS_NAME)
                    time_val = item.get("time", cls.TARGET_TIME)
                    days = item.get("days", cls.TARGET_DAYS)
                    targets.append(BookingTarget(name, time_val, days))
                if targets:
                    return targets
            except Exception:
                pass

        # Fallback si no hay JSON
        return [BookingTarget(cls.TARGET_CLASS_NAME, cls.TARGET_TIME, cls.TARGET_DAYS)]

    @classmethod
    def validate(cls) -> List[str]:
        """Valida que las credenciales necesarias estén presentes."""
        errors = []
        if not cls.EMAIL or cls.EMAIL == "tu_email@ejemplo.com":
            errors.append("Debes configurar AIMHARDER_EMAIL en el archivo .env o Secrets de GitHub")
        if not cls.PASSWORD or cls.PASSWORD == "tu_contraseña":
            errors.append("Debes configurar AIMHARDER_PASSWORD en el archivo .env o Secrets de GitHub")
        if not cls.BOX_URL:
            errors.append("Debes configurar BOX_URL en el archivo .env o Secrets de GitHub")
        return errors
