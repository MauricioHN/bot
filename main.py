"""Bot de comandos para telegram"""
import re
import logging as log
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_INBOUND = 'https://layer-api-inbound-reservation-service'
API_CORE = 'https://layer-api-core-service.tysonprod.com/v1'
API_MULTIMEDIA = 'https://layer-api-multimedia-service.tysonprod.com/v1'
API_WEB = 'https://layer-api-web-service.tysonprod.com/v1'
EVENT_HANDLER = 'https://layer-api-event-handler-service.tysonprod.com/v1'
EVENT_BUS = 'https://layer-api-event-bus-service.tysonprod.com/v1'

VERSION = "1.20.1.26"
NOTA_VERSION = "Probar error en desbloqueo de correo"


if not TOKEN:
    raise RuntimeError("❌ TELEGRAM_TOKEN no está definido")

# Funciones genericas


def extract_uuid(text: str) -> str | None:
    pattern = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    match = re.search(pattern, text)
    return match.group(0) if match else None


def extract_hex_id(text: str) -> str | None:
    match = re.search(r"\b[a-fA-F0-9]{20,40}\b", text)
    return match.group(0) if match else None


def extract_email(text: str) -> str | None:
    match = re.search(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.(com|com\.mx)", text
    )
    return match.group(0) if match else None


def safe_get(url: str, **kwargs):
    response = requests.get(url, timeout=60, **kwargs)
    response.raise_for_status()
    return response.json()


def safe_post(url: str, **kwargs):
    response = requests.post(url, timeout=60, **kwargs)
    response.raise_for_status()
    return response.json()


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """hola"""
    print("🤖 Bot iniciado correctamente")
    log.info("Bot iniciado correctamente")
    await update.message.reply_text(VERSION + " " + NOTA_VERSION)


async def get_liga(update: Update, context: ContextTypes.DEFAULT_TYPE):
    argumento = extract_hex_id(update.message.text)
    if not argumento:
        await update.message.reply_text("No se encontró ID de solicitud.")
        return

    try:
        tareas = safe_post(
            f"{API_INBOUND}.tysonprod.com/v1/api/videocallReservationByIdSolicitud",
            json={"idSolicitud": argumento}
        )
        url = tareas.get("url") or tareas.get("message")

        tasks = safe_get(
            f"{API_CORE}/api/get_task_results_manager",
            params={
                "pageNumber": 0,
                "itemsPerPage": 1000,
                "period": "ALL",
                "idSolicitud": argumento
            }
        ).get("list", [])

        for task in tasks:
            if task["task_identifier"] == "videollamada":
                uuid = task["task_request_uuid"]
                task_data = safe_get(
                    f"{API_CORE}/api/get_task_request", params={"uuid": uuid})
                if task_data["data"]["taskId"] == "VERIDENTIVIDEOCOA":
                    url += "&typecall=muted"
                break

        await update.message.reply_text(url)
    except Exception:
        await update.message.reply_text("Error al generar la liga.")


async def desbloquear_correo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    correo = extract_email(update.message.text)
    if not correo:
        await update.message.reply_text("Correo no válido.")
        return

    try:
        uuid_data = safe_get(f"{API_WEB}/api/get_worker_id_by_email/{correo}")
        worker_uuid = uuid_data["uuid"]
        print(worker_uuid)

        worker_info = safe_get(f"{API_WEB}/api/get_worker/{worker_uuid}")
        payload = {
            "worker_uuid": worker_uuid,
            "session_id": worker_info["session_id"]
        }
        print(worker_info.json())

        respuesta = safe_post(f"{API_WEB}/api/logout_worker", json=payload)
        print(respuesta.json())
        mensaje = "Correo desbloqueado correctamente."
    except Exception:
        mensaje = "Error al desbloquear el correo. "

    await update.message.reply_text(mensaje)


async def republicar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uuid = extract_uuid(update.message.text)
    if not uuid:
        await update.message.reply_text("No se encontró UUID.")
        return

    try:
        task_data = safe_get(
            f"{API_CORE}/api/get_task_results_manager",
            params={
                "pageNumber": 0,
                "itemsPerPage": 5,
                "taskId": uuid,
                "period": "ALL"
            }
        )
        task_type = task_data["list"][0]["task_identifier"]

        safe_post(
            f"{EVENT_BUS}/redis/setTaskEstatusFake",
            json={"taskId": f"s-1-{uuid}"}
        )

        payload_base = {
            "uuid": f"s-1-{uuid}",
            "segment": 1,
            "priority": 3,
            "deadline": 15,
            "requested_at": 1.626798221209E9,
            "data": {},
            "forManagerReview": False,
        }

        if task_type == "VERIDISPERSION":
            payload_base.update({
                "task_identifier": "veridispersion",
                "role": "veridispersion",
                "stage": {"stage_list": "stage=32"},
            })
        elif task_type == "captura":
            payload_base.update({
                "task_identifier": "captura",
                "role": "captura",
                "stage": {"stage_list": "stage=9"},
            })
        else:
            raise ValueError("Tipo de tarea no soportado")

        safe_post(
            f"{EVENT_HANDLER}/redis/publishTask",
            json={"message": payload_base}
        )

        mensaje = "Tarea republicada correctamente."
    except Exception:
        mensaje = "No se pudo republicar la tarea."

    await update.message.reply_text(mensaje)


async def imagenes_ine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uuid = extract_uuid(update.message.text)
    if not uuid:
        await update.message.reply_text("No se encontró UUID.")
        return

    mensaje = f"INE_ANVERSO  =  {API_MULTIMEDIA}/api/view/{uuid}/INE_ANVERSO \n INE_REVERSO  =  {API_MULTIMEDIA}/api/view/{uuid}/INE_REVERSO \n SELFIE  =  {API_MULTIMEDIA}/api/view/{uuid}/SELFIE"

    await update.message.reply_text(mensaje)


application = ApplicationBuilder().token(
    TOKEN).build()
application.add_handler(CommandHandler("echo", echo))
application.add_handler(CommandHandler("getliga", get_liga))
application.add_handler(CommandHandler("rep", republicar))
application.add_handler(CommandHandler("des", desbloquear_correo))
application.add_handler(CommandHandler("ine", imagenes_ine))
application.run_polling(allowed_updates=Update.ALL_TYPES)
application.run_polling(allowed_updates=Update.ALL_TYPES)

# push prueba s
