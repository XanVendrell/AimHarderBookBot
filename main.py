import argparse
import logging
import sys
import time
import threading
from datetime import datetime, timedelta
from typing import List
import pytz
import schedule

from config import Config, BookingTarget
from notifier import TelegramNotifier
from aimharder_client import AimharderClient
from telegram_bot import TelegramBotListener

LOCAL_TZ = pytz.timezone("Europe/Madrid")

def setup_logging():
    """Configura el sistema de registro de eventos (stdout y archivo bot_reservas.log)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("bot_reservas.log", encoding="utf-8")
        ]
    )

logger = logging.getLogger("Main")

def get_target_date_for_booking(days_ahead: int = 5) -> datetime:
    """Calcula la fecha objetivo con la antelación configurada."""
    now_local = datetime.now(LOCAL_TZ)
    return now_local + timedelta(days=days_ahead)

def process_targets_for_date(client: AimharderClient, target_date: datetime, targets: List[BookingTarget], dry_run: bool = False):
    """Procesa la colección de objetivos de reserva para una fecha específica."""
    date_weekday = target_date.weekday()
    date_str = target_date.strftime("%d/%m/%Y (%A)")

    for target in targets:
        if date_weekday in target.days:
            logger.info(f"Aplicando objetivo: '{target.name}' a las {target.time} para el {date_str}")
            client.book_target(target, target_date=target_date, dry_run=dry_run)
            time.sleep(0.5)

def run_scheduled_booking():
    """Función invocada diariamente a las 17:30:01h por el planificador daemon."""
    target_date = get_target_date_for_booking(Config.DAYS_AHEAD)
    date_str = target_date.strftime("%Y-%m-%d (%A)")

    logger.info(f"Ejecutando reserva automatica programada. Objetivo: {date_str}")
    targets = Config.get_targets()

    notifier = TelegramNotifier()
    notifier.send_message(f"⏰ *Bot Aimharder:* Procesando reservas programadas para el *{target_date.strftime('%d/%m/%Y')}*...")

    client = AimharderClient()
    process_targets_for_date(client, target_date, targets, dry_run=False)

def handle_week(targets: List[BookingTarget], dry_run: bool = False):
    """Procesa en lote todas las clases de la semana de Lunes a Viernes para la colección de objetivos."""
    logger.info("--- MODO RESERVA SEMANAL ---")
    today = datetime.now(LOCAL_TZ)
    
    notifier = TelegramNotifier()
    notifier.send_message("🤖 *Bot Aimharder:* Iniciando el proceso de reserva semanal de clases...")

    days_ahead = (0 - today.weekday()) % 7
    if days_ahead == 0 and today.hour >= 18:
        days_ahead = 7
    monday = today + timedelta(days=days_ahead)

    client = AimharderClient()

    for day_offset in range(5):
        target_date = monday + timedelta(days=day_offset)
        logger.info(f"--- Procesando {target_date.strftime('%A %d/%m/%Y')} ---")
        process_targets_for_date(client, target_date, targets, dry_run=dry_run)
        time.sleep(1)

def main():
    setup_logging()

    parser = argparse.ArgumentParser(description="Bot Agnostico de Reserva Automatica de Clases en Aimharder")
    parser.add_argument("--test", action="store_true", help="Realiza una simulacion (Dry Run) sin realizar la reserva real")
    parser.add_argument("--book", action="store_true", help="Realiza la reserva real para los objetivos configurados")
    parser.add_argument("--week", action="store_true", help="Reserva toda la semana (Lunes a Viernes) para los objetivos configurados")
    parser.add_argument("--date", type=str, help="Reserva una fecha especifica en formato YYYY-MM-DD (ej: 2026-08-06)")
    parser.add_argument("--daemon", action="store_true", help="Ejecuta en segundo plano (programador diario 17:30h + bot de Telegram interactivo)")
    parser.add_argument("--bot", action="store_true", help="Ejecuta unicamente el servidor interactivo de comandos de Telegram")
    parser.add_argument("--test-telegram", action="store_true", help="Envia un mensaje de prueba al chat de Telegram")

    args = parser.parse_args()

    if not args.test_telegram:
        errors = Config.validate()
        if errors:
            logger.error("Se encontraron errores en la configuracion:")
            for err in errors:
                logger.error(f" - {err}")
            logger.info("Edita el archivo .env antes de continuar.")
            sys.exit(1)

    if args.test_telegram:
        logger.info("Probando notificacion de Telegram...")
        notifier = TelegramNotifier()
        if not notifier.is_configured:
            logger.error("TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no estan configurados en .env")
            sys.exit(1)
        ok = notifier.send_message("🤖 *Bot Aimharder:* ¡Notificaciones de Telegram configuradas correctamente!")
        if ok:
            logger.info("Mensaje enviado con exito a Telegram.")
        else:
            logger.error("Fallo al enviar mensaje a Telegram.")
        return

    if args.bot:
        logger.info("--- MODO BOT INTERACTIVO TELEGRAM ---")
        listener = TelegramBotListener()
        if not listener.is_configured:
            logger.error("TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no configurados.")
            sys.exit(1)
        listener.start()
        return

    targets = Config.get_targets()
    logger.info(f"Objetivos a procesar: {targets}")

    if args.week:
        handle_week(targets, dry_run=args.test)
        return

    if args.test:
        logger.info("--- MODO SIMULACION (DRY RUN) ---")
        target_date = get_target_date_for_booking(Config.DAYS_AHEAD)
        if args.date:
            target_date = datetime.strptime(args.date, "%Y-%m-%d")
        client = AimharderClient()
        process_targets_for_date(client, target_date, targets, dry_run=True)
        return

    if args.date or args.book:
        logger.info("--- MODO RESERVA REAL ---")
        if args.date:
            target_date = datetime.strptime(args.date, "%Y-%m-%d")
        else:
            target_date = get_target_date_for_booking(Config.DAYS_AHEAD)
        client = AimharderClient()
        process_targets_for_date(client, target_date, targets, dry_run=False)
        return

    if args.daemon:
        logger.info("--- MODO DAEMON COMPLETO (PROGRAMADOR + BOT INTERACTIVO) ---")
        logger.info("El bot esperara diariamente a las 17:30:01h para realizar reservas y escuchara comandos por Telegram.")

        listener = TelegramBotListener()
        if listener.is_configured:
            bot_thread = threading.Thread(target=listener.start, daemon=True)
            bot_thread.start()
            logger.info("Hilo de bot de Telegram iniciado con exito.")
        else:
            logger.warning("Notificaciones o Token de Telegram no configurados. Se omitira el escuchador interactivo.")

        schedule.every().day.at("17:30:01").do(run_scheduled_booking)

        notifier = TelegramNotifier()
        notifier.send_message(
            "🤖 *Bot Aimharder Activado en Modo Daemon*\n"
            "• Programador diario activo para las 17:30h.\n"
            "• Escuchador interactivo listo para recibir comandos."
        )

        while True:
            schedule.run_pending()
            time.sleep(1)

    parser.print_help()

if __name__ == "__main__":
    main()
