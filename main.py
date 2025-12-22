"""Bot de comandos para telegram"""
import re
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes


API_INBOUND = 'https://layer-api-inbound-reservation-service'
API_CORE = 'https://layer-api-core-service'
API_WEB = 'https://layer-api-web-service.tysonprod.com/v1'


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """hola"""
    await update.message.reply_text(update.message.text)


async def prop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    argumento = update.message.text.split(maxsplit=1)[1]
    print(argumento)
    segment = requests.get(
        API_CORE + '.tysonprod.com/v1/api/get_task_segment?task_segment_id=' + argumento, timeout=70)
    segmento = segment.json()
    segmento = segmento['status']
    print(segmento)
    await update.message.reply_text(segmento)


async def get_liga(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """genera la liga de una videollamada"""
    # argumento = update.message.text.split(maxsplit=1)[1]
    argumento = update.message.text
    print(argumento)
    # separa el mensaje completo y desecha todo menos el id
    match = re.search(r"\b([a-fA-F0-9]{20,40})\b", argumento)
    if match:
        argumento = match.group(1)
        print(argumento)

    url_get_tareas = API_INBOUND + \
        '.tysonprod.com/v1/api/videocallReservationByIdSolicitud'
    url_get_request = API_CORE + '.tysonprod.com/v1/api/get_task_request?uuid='
    url_get_crowd_task = API_CORE + \
        '.tysonprod.com/v1/api/get_task_results_manager?pageNumber=0&itemsPerPage=1000&period=ALL&idSolicitud='

    response_get_traeas = requests.post(
        url_get_tareas, json={"idSolicitud": argumento}, timeout=60)
    get_tareas = response_get_traeas.json()
    crowd_task = requests.get(url_get_crowd_task + argumento, timeout=60)
    tasks = crowd_task.json()
    print("========================================")
    print(response_get_traeas.status_code)
    print(get_tareas)
    try:
        url = get_tareas['url']
    except:
        url = get_tareas['message']

    if response_get_traeas.status_code == 200:
        tasks = tasks['list']
        for task in tasks:
            task_identifier = task['task_identifier']
            if task_identifier == 'videollamada':
                uuid = task['task_request_uuid']
                get_request = requests.get(url_get_request + uuid, timeout=60)
                task_id = get_request.json()
                task_id = task_id['data']['taskId']
                if task_id == 'VERIDENTIVIDEOCOA':
                    url = url + '&typecall=muted'
                break
    await update.message.reply_text(url)


async def desbloquear_correo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Desbloequear correos de crowd"""
    argumento = update.message.text
    # separa el mensaje completo y desecha todo menos el id
    print(argumento)
    match = re.search(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.com", argumento)
    matchmx = re.search(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.com.mx", argumento)
    if matchmx:
        correo = matchmx.group(0)
        print(correo)
    else:
        correo = match.group(0)
        print(correo)

    url_obtener_uuid = f"{API_WEB}/api/get_worker_id_by_email/{correo}"
    response_uuid = requests.get(url_obtener_uuid, timeout=60)
    if not response_uuid.ok:
        mensaje = 'No se encontró UUID para este correo.'

    uuid_data = response_uuid.json()
    worker_uuid = uuid_data.get('uuid')
    url_info_worker = f"{API_WEB}/api/get_worker/{worker_uuid}"
    response_info_worker = requests.get(url_info_worker, timeout=60)
    if not response_info_worker.ok:
        mensaje = 'No se pudo obtener la información del trabajador.'
    worker_info = response_info_worker.json()
    session_id = worker_info.get('session_id')

    url_desbloqueo = f"{API_WEB}/api/logout_worker"
    payload = {
        "worker_uuid": worker_uuid,
        "session_id": session_id,
    }
    response_desbloqueo = requests.post(
        url_desbloqueo, json=payload, timeout=60)

    if response_desbloqueo.ok:
        mensaje = "Correo desbloqueado correctamente."
    else:
        mensaje = "Error al desbloquear el correo."

    await update.message.reply_text(mensaje)

application = ApplicationBuilder().token(
    "7988722624:AAGqIlwSc8sDHbI7WHbShSNEmqnTrxH9c9E").build()
application.add_handler(CommandHandler("echo", echo))
application.add_handler(CommandHandler("getliga", get_liga))

application.add_handler(CommandHandler("desbloquear", desbloquear_correo))
application.run_polling(allowed_updates=Update.ALL_TYPES)
