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
    BOX_URL: str = (os.getenv("BOX_URL") or "https://aimharder.com").strip().rstrip('/')
    BOX_ID: str = (os.getenv("BOX_ID") or "9221").strip()
    BOX_NAME: str = (os.getenv("BOX_NAME") or "CrossFit Box").strip()
    
    TARGET_TIME: str = (os.getenv("TARGET_TIME") or "17:30").strip()
    TARGET_CLASS_NAME: str = (os.getenv("TARGET_CLASS_NAME") or "CrossFit").strip()
    
    _raw_days: str = (os.getenv("TARGET_DAYS") or "0,1,2,3,4").strip()
    TARGET_DAYS: List[int] = [int(d.strip()) for d in _raw_days.split(",") if d.strip().isdigit()]
    DAYS_AHEAD: int = int(os.getenv("DAYS_AHEAD") or "5")
    
    TARGETS_FILE: str = "targets.json"
    TELEGRAM_BOT_TOKEN: str = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    TELEGRAM_CHAT_ID: str = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()

    @classmethod
    def get_targets(cls) -> List[BookingTarget]:
        """
        Recupera la colección de objetivos de reserva.
        Tiene prioridad el archivo local 'targets.json' si existe.
        Sino, intenta leer del entorno 'TARGETS' en formato JSON.
        """
        # 1. Intentar cargar desde targets.json si existe
        if os.path.exists(cls.TARGETS_FILE):
            try:
                with open(cls.TARGETS_FILE, "r", encoding="utf-8") as f:
                    items = json.load(f)
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

        # 2. Intentar cargar desde variable de entorno TARGETS
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
    def save_targets(cls, targets: List[BookingTarget]) -> bool:
        """Guarda la lista de objetivos en el archivo targets.json."""
        try:
            data = [{"name": t.name, "time": t.time, "days": t.days} for t in targets]
            with open(cls.TARGETS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    @classmethod
    def add_target(cls, target: BookingTarget) -> List[BookingTarget]:
        """Añade un nuevo objetivo y lo guarda."""
        current = cls.get_targets()
        current.append(target)
        cls.save_targets(current)
        return current

    @classmethod
    def delete_target_at(cls, index: int) -> bool:
        """Elimina un objetivo por su índice 0-based y guarda el resultado."""
        current = cls.get_targets()
        if 0 <= index < len(current):
            current.pop(index)
            cls.save_targets(current)
            return True
        return False

    @classmethod
    def validate(cls) -> List[str]:
        """Valida que las credenciales mínimas estén configuradas."""
        errors = []
        if not cls.EMAIL or cls.EMAIL == "tu_email@ejemplo.com":
            errors.append("Debes configurar AIMHARDER_EMAIL en el archivo .env o Secrets de GitHub")
        if not cls.PASSWORD or cls.PASSWORD == "tu_contraseña":
            errors.append("Debes configurar AIMHARDER_PASSWORD en el archivo .env o Secrets de GitHub")
        if not cls.BOX_URL:
            errors.append("Debes configurar BOX_URL en el archivo .env o Secrets de GitHub")
        return errors

