# -*- coding: utf-8 -*-
"""
telegram_2fa.py

Reemplaza la web local (token_web/app.py) para ingresar el código de doble
factor: en vez de abrir http://localhost:5050, el bot de Telegram te avisa
por chat cuando se necesita el código, y tú simplemente le respondes en ese
mismo chat con los 6 dígitos.

Requiere:
    pip install requests --break-system-packages
    (ya lo tienes instalado de antes)

Configuración (.env):
    TELEGRAM_BOT_TOKEN=123456:ABC-DEF...   (te lo da @BotFather)
    TELEGRAM_CHAT_ID=987654321             (tu chat_id, ver instrucciones abajo)

Cómo crear el bot y conseguir el chat_id:
    1. En Telegram, habla con @BotFather -> /newbot -> sigue los pasos.
        Te va a dar un token tipo "123456789:AAExxxxxxxxxxxxxxxxxxxxxxx".
    2. Busca tu bot recién creado y mándale cualquier mensaje (ej. "hola")
       para que quede un chat abierto con él.
    3. Corre esto una vez para sacar tu chat_id:
        python -c "import requests, os; from dotenv import load_dotenv; \
        load_dotenv(); print(requests.get( \
        f'https://api.telegram.org/bot{os.environ[\"TELEGRAM_BOT_TOKEN\"]}/getUpdates' \
        ).json())"
       Busca en la respuesta "chat":{"id": ...} y ese es tu TELEGRAM_CHAT_ID.
"""
import os
import re
import time
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()


def _url_api(metodo):
    return f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{metodo}"


def _validar_config():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        raise Exception(
            "Faltan TELEGRAM_BOT_TOKEN y/o TELEGRAM_CHAT_ID en el .env — "
            "ver instrucciones en el docstring de telegram_2fa.py."
        )


def enviar_mensaje(texto):
    _validar_config()
    resp = requests.post(
        _url_api("sendMessage"),
        json={"chat_id": TELEGRAM_CHAT_ID, "text": texto},
        timeout=15,
    )
    resp.raise_for_status()


def _limpiar_actualizaciones_pendientes():
    """
    Descarta cualquier mensaje viejo que haya quedado pendiente en el bot
    (ej. de una corrida anterior), para no confundirlo con el código nuevo
    que vamos a pedir ahora.
    """
    try:
        resp = requests.get(_url_api("getUpdates"), params={"timeout": 0}, timeout=10)
        resultados = resp.json().get("result", [])
        if resultados:
            ultimo_id = resultados[-1]["update_id"]
            requests.get(
                _url_api("getUpdates"),
                params={"offset": ultimo_id + 1, "timeout": 0},
                timeout=10,
            )
    except Exception:
        pass  # si falla la limpieza, seguimos igual — no es crítico


def esperar_codigo(id_ejecucion=None, banco="Banco Pichincha", timeout_segundos=300, intervalo=2):
    """
    Envía el aviso por Telegram y espera (long polling) a que respondas en
    el mismo chat con un código de 6 dígitos. Misma firma que
    token_store.esperar_codigo() del sistema anterior, para que sea un
    reemplazo directo en login_pichincha_selenium.py.
    """
    _validar_config()
    _limpiar_actualizaciones_pendientes()

    minutos = timeout_segundos // 60
    texto_aviso = (
        f"🔐 {banco}: se necesita el código de doble factor"
        + (f" (ejecución #{id_ejecucion})" if id_ejecucion else "")
        + f".\nResponde en este chat con los 6 dígitos dentro de los próximos {minutos} minutos."
    )
    enviar_mensaje(texto_aviso)
    print(f"Aviso enviado por Telegram. Esperando respuesta con el código (timeout {minutos} min)...")

    offset = None
    inicio = time.time()

    while time.time() - inicio < timeout_segundos:
        params = {"timeout": 20}
        if offset is not None:
            params["offset"] = offset

        try:
            resp = requests.get(_url_api("getUpdates"), params=params, timeout=25)
            resp.raise_for_status()
            resultados = resp.json().get("result", [])
        except Exception as e:
            print(f"  Aviso: error consultando Telegram ({e}), reintentando...")
            time.sleep(intervalo)
            continue

        for update in resultados:
            offset = update["update_id"] + 1
            mensaje = update.get("message", {})
            chat_id_recibido = str(mensaje.get("chat", {}).get("id", ""))
            texto_recibido = (mensaje.get("text") or "").strip()

            if chat_id_recibido != str(TELEGRAM_CHAT_ID):
                continue  # ignora mensajes de cualquier otro chat

            if re.fullmatch(r"\d{6}", texto_recibido):
                enviar_mensaje("✅ Código recibido, continuando con el login...")
                return texto_recibido

        time.sleep(intervalo)

    enviar_mensaje("⏰ Se agotó el tiempo esperando el código de seguridad.")
    return None