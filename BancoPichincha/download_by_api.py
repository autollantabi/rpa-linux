# -*- coding: utf-8 -*-
"""
download_by_api.py

Descarga los CSVs de movimientos de todas las empresas usando directamente
los endpoints internos del banco, en vez de clickear la UI.

Los fetch() corren DENTRO del navegador que ya logueaste con Selenium
(login_pichincha_selenium.py) — así los cookies de Akamai/Dynatrace y el
token de sesión viajan automáticamente, sin tener que falsificar nada.

Uso:
    from download_by_api import descargar_todas_las_empresas_api
    descargar_todas_las_empresas_api(driver, "C:/BancosRPA/descargas")
"""
import os
import base64
import json
import time
from datetime import date, timedelta
from selenium_utils import cerrar_modales_bloqueantes

BASE_URL = "https://bancaempresas.pichincha.com/api/channel/business-banking/v1"
CLIENT_ID = "08d3b5d8-82d3-4098-9eaf-ec7c430ac63c"

MAPEO_ARCHIVOS = {
    "IKONIX CIA LTDA": "ikonix.csv",
    "MAXXIMUNDO CIA LTDA": "maxximundo.csv",
    "STOX CIA LTDA": "stox.csv",
    "AUTOLLANTA C LTDA": "autollanta.csv",
}

# Headers estáticos confirmados en las peticiones reales del banco
X_API_KEY = "e16a55a4b0b74231936413427b0c46a9"
X_APP = "00738"
X_CHANNEL = "10"
X_MEDIUM = "100001"
APP_NAME = "bussines-banking"


# ==================== Obtener token real desde el tráfico de red ====================
#
# La app NO usa el cache estándar de MSAL para el access token de la API
# (queda vacío en sessionStorage) — lo guarda cifrado con su propia lógica.
# En vez de descifrar eso, lo capturamos directamente del header
# Authorization que la app manda en sus propias peticiones reales — lo
# mismo que verías a mano en DevTools > Network > (una request) > Headers.
# Requiere que crear_driver() haya habilitado "goog:loggingPrefs" y
# Network.enable (ya lo hace login_pichincha_selenium.crear_driver).

URL_BASE = "https://bancaempresas.pichincha.com/"
RUTA_API_PARA_DETECTAR = "/api/channel/business-banking/v1"


def _extraer_token_de_logs_red(driver):
    """
    Revisa el buffer de logs de performance/red acumulado hasta ahora y
    devuelve el primer Authorization: Bearer ... que encuentre en una
    petición hacia la API del banco.
    """
    try:
        entradas = driver.get_log("performance")
    except Exception:
        return None

    for entrada in entradas:
        try:
            mensaje = json.loads(entrada["message"])["message"]
        except Exception:
            continue

        if mensaje.get("method") != "Network.requestWillBeSent":
            continue

        params = mensaje.get("params", {})
        request = params.get("request", {})
        url = request.get("url", "")
        if RUTA_API_PARA_DETECTAR not in url:
            continue

        headers = request.get("headers", {})
        auth = headers.get("Authorization") or headers.get("authorization")
        if auth and auth.lower().startswith("bearer "):
            return auth[7:].strip()

    return None


def obtener_sesion_api(driver, timeout=20, intervalo=1.5, forzar_navegacion=True):
    """
    Obtiene el access token vigente capturándolo del tráfico de red real.

    IMPORTANTE: driver.get_log("performance") VACÍA el buffer en cada
    llamada — solo devuelve eventos nuevos desde la última vez que se leyó.
    Por eso, si no forzamos una navegación fresca aquí, una llamada
    posterior a esta función (ej. la que hace descargar_todas_las_empresas_api
    después de que sesion_persistente ya leyó el buffer una vez) se
    encuentra con un buffer vacío y nunca detecta nada, aunque la sesión
    siga perfectamente válida.

    forzar_navegacion=True (por defecto) recarga la home antes de leer los
    logs, para garantizar que se dispare una petición nueva y haya algo
    fresco que capturar. Pásalo en False solo si ya sabes que acabas de
    navegar/recargar justo antes de llamar a esta función.
    """
    if forzar_navegacion:
        print("  Disparando una petición fresca a la API (recargando la página)...")
        driver.get(URL_BASE)
        time.sleep(3)
        cerrar_modales_bloqueantes(driver, timeout=8)

    inicio = time.time()
    while time.time() - inicio < timeout:
        token = _extraer_token_de_logs_red(driver)
        if token:
            uuid_sesion = _decodificar_uuid_del_token(token)
            return token, uuid_sesion
        time.sleep(intervalo)

    raise Exception(
        "No se capturó ningún Authorization: Bearer en el tráfico de red hacia "
        f"{RUTA_API_PARA_DETECTAR} tras {timeout}s. Verifica que el navegador "
        "haya llegado a una pantalla que dispare una llamada real a la API "
        "(ej. Posición Consolidada)."
    )


def _decodificar_uuid_del_token(token):
    """Decodifica el payload del JWT para sacar el claim 'uuid' (se usa como
    x-auth-token/x-session en las llamadas a la API)."""
    payload_b64 = token.split(".")[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    return payload["uuid"]


# ==================== JS: fetch genérico dentro del navegador ====================

JS_FETCH_JSON = """
    const [url, method, token, uuid, extraHeadersJson, bodyJson] = arguments;
    const callback = arguments[arguments.length - 1];
    const extraHeaders = JSON.parse(extraHeadersJson || '{}');

    const headers = Object.assign({
        'accept': 'application/json, text/plain, */*',
        'app-name': '%s',
        'authorization': 'Bearer ' + token,
        'x-api-key': '%s',
        'x-app': '%s',
        'x-channel': '%s',
        'x-device': navigator.userAgent,
        'x-medium': '%s',
        'x-language': 'es',
        'x-guid': crypto.randomUUID(),
        'x-auth-token': uuid,
        'x-session': uuid,
        'caller-name': crypto.randomUUID(),
    }, extraHeaders);

    const opciones = { method: method, headers: headers, credentials: 'include' };
    if (bodyJson) {
        opciones.body = bodyJson;
        headers['content-type'] = 'application/json';
    }

    fetch(url, opciones)
        .then(async (resp) => {
            if (!resp.ok) {
                const texto = await resp.text();
                callback({error: `HTTP ${resp.status}: ${texto}`});
                return;
            }
            const data = await resp.json();
            callback({data: data});
        })
        .catch(e => callback({error: e.toString()}));
""" % (APP_NAME, X_API_KEY, X_APP, X_CHANNEL, X_MEDIUM)


JS_FETCH_ARCHIVO = """
    const [url, method, token, uuid, bodyJson] = arguments;
    const callback = arguments[arguments.length - 1];

    const headers = {
        'accept': 'application/json, text/plain, */*',
        'app-name': '%s',
        'authorization': 'Bearer ' + token,
        'x-api-key': '%s',
        'x-app': '%s',
        'x-channel': '%s',
        'x-device': navigator.userAgent,
        'x-medium': '%s',
        'x-language': 'es',
        'x-guid': crypto.randomUUID(),
        'x-auth-token': uuid,
        'x-session': uuid,
        'caller-name': crypto.randomUUID(),
        'content-type': 'application/json',
        'origin': 'https://bancaempresas.pichincha.com',
    };

    fetch(url, { method: method, headers: headers, credentials: 'include', body: bodyJson })
        .then(async (resp) => {
            if (!resp.ok) {
                const texto = await resp.text();
                callback({error: `HTTP ${resp.status}: ${texto}`});
                return;
            }
            const buffer = await resp.arrayBuffer();
            const bytes = new Uint8Array(buffer);
            let binario = '';
            for (let i = 0; i < bytes.length; i++) binario += String.fromCharCode(bytes[i]);
            callback({base64: btoa(binario)});
        })
        .catch(e => callback({error: e.toString()}));
""" % (APP_NAME, X_API_KEY, X_APP, X_CHANNEL, X_MEDIUM)


# La URL firmada (SAS) de Azure Blob Storage se autentica SOLA con la firma
# que trae en la query string (sv, se, sr, sp, sig). Si además le mandamos
# el header Authorization del banco, Azure la rechaza con
# "InvalidAuthenticationInfo" porque no sabe qué mecanismo de auth usar.
# Por eso esta descarga va SIN ningún header de autenticación propio —
# solo las cookies (credentials: 'include', para que pase Akamai).
JS_FETCH_BLOB = """
    const [url] = arguments;
    const callback = arguments[arguments.length - 1];

    fetch(url, { method: 'GET', credentials: 'include' })
        .then(async (resp) => {
            if (!resp.ok) {
                const texto = await resp.text();
                callback({error: `HTTP ${resp.status}: ${texto}`});
                return;
            }
            const buffer = await resp.arrayBuffer();
            const bytes = new Uint8Array(buffer);
            let binario = '';
            for (let i = 0; i < bytes.length; i++) binario += String.fromCharCode(bytes[i]);
            callback({base64: btoa(binario)});
        })
        .catch(e => callback({error: e.toString()}));
"""


def fetch_json(driver, url, token, uuid, method="GET", extra_headers=None, body=None):
    body_json = json.dumps(body) if body is not None else None
    extra_headers_json = json.dumps(extra_headers or {})
    resultado = driver.execute_async_script(
        JS_FETCH_JSON, url, method, token, uuid, extra_headers_json, body_json
    )
    if resultado.get("error"):
        raise Exception(f"Error en fetch a {url}: {resultado['error']}")
    return resultado["data"]


def fetch_blob(driver, url):
    """Descarga el contenido binario de una URL ya autenticada por sí sola
    (ej. una URL SAS de Azure Blob Storage) — sin headers de auth propios."""
    resultado = driver.execute_async_script(JS_FETCH_BLOB, url)
    if resultado.get("error"):
        raise Exception(f"Error descargando archivo de {url}: {resultado['error']}")
    return base64.b64decode(resultado["base64"])


def fetch_archivo(driver, url, token, uuid, method="POST", body=None):
    body_json = json.dumps(body) if body is not None else None
    resultado = driver.execute_async_script(
        JS_FETCH_ARCHIVO, url, method, token, uuid, body_json
    )
    if resultado.get("error"):
        raise Exception(f"Error descargando archivo de {url}: {resultado['error']}")
    return base64.b64decode(resultado["base64"])


# ==================== Lógica de negocio ====================

def obtener_empresas(driver, token, uuid):
    url = f"{BASE_URL}/companies?claims=POS.CTA.SAL,POS.TC.SAL,POS.CRE.SAL,POS.INV.SAL"
    return fetch_json(driver, url, token, uuid)


def obtener_cuentas(driver, token, uuid, company_id):
    url = f"{BASE_URL}/account-overview/accounts?companyId={company_id}&claim=POS.CTA.SAL"
    return fetch_json(driver, url, token, uuid, extra_headers={"process-code": "POSCO01"})


def solicitar_descarga(driver, token, uuid, company_id, account_id, dias_atras=7):
    """
    Encola la generación del archivo y devuelve el fileId asignado.

    dias_atras = cantidad TOTAL de días del rango, incluyendo hoy. Así,
    dias_atras=7 con hoy=07/08 da como resultado 01/08 -> 07/08 (7 días
    calendario exactos: 1,2,3,4,5,6,7 de agosto) — que es lo que
    intuitivamente se espera al pedir "últimos 7 días".

    (Antes se restaba dias_atras directo a hoy, lo que en realidad daba un
    rango de dias_atras+1 días — ej. con dias_atras=7 salía 31/07 -> 07/08,
    8 días en vez de 7).
    """
    hoy = date.today()
    desde = hoy - timedelta(days=dias_atras - 1)

    payload = {
        "account": {
            "uuid": account_id,
            "transaction": {
                "fromOperationDate": desde.strftime("%d%m%Y"),
                "toOperationDate": hoy.strftime("%d%m%Y"),
            }
        },
        "file": {
            "type": {
                "code": "CSV",
                "columns": ["OFFICE", "DOCUMENT", "CONCEPT", "TYPE", "AMOUNT", "BALANCE", "DATE", "CODE"]
            }
        },
        "companyId": company_id,
    }

    url = f"{BASE_URL}/account-overview/accounts/transactions/download"
    data = fetch_json(driver, url, token, uuid, method="POST", body=payload)
    file_id = data.get("fileId")
    if not file_id:
        raise Exception(f"La respuesta de /download no incluyó fileId: {data}")
    return file_id


def esperar_archivo_listo(driver, token, uuid, file_id, timeout=30, intervalo=1.5):
    """
    Consulta /download/verify hasta que el archivo esté PROCESSED, y
    devuelve la URL firmada (SAS de Azure Blob) desde donde se descarga
    el CSV real.
    """
    url = f"{BASE_URL}/account-overview/accounts/transactions/download/verify"
    inicio = time.time()

    while time.time() - inicio < timeout:
        data = fetch_json(driver, url, token, uuid, method="POST", body={"fileId": file_id})
        estado = data.get("status")

        if estado == "PROCESSED":
            return data["url"], data.get("name")
        if estado in ("FAILED", "ERROR"):
            raise Exception(f"El banco reportó error generando el archivo: {data}")

        time.sleep(intervalo)

    raise Exception(f"El archivo (fileId={file_id}) no terminó de procesarse tras {timeout}s")


def descargar_csv_cuenta(driver, token, uuid, company_id, account_id, dias_atras=7):
    """
    Flujo completo: encola la descarga, espera a que esté lista, y baja el
    contenido real del CSV desde la URL firmada.

    El GET final se ejecuta DENTRO del navegador (misma pestaña autenticada)
    porque esa ruta (transactions-container) está protegida por Akamai Bot
    Manager — un cliente HTTP externo sin la cookie ak_bmsc de un navegador
    real recibe "Access Denied" (403), sin excepción. Al ser fetch() desde
    la misma pestaña/mismo origen, esa cookie viaja sola.
    """
    file_id = solicitar_descarga(driver, token, uuid, company_id, account_id, dias_atras)
    url_archivo, nombre_remoto = esperar_archivo_listo(driver, token, uuid, file_id)
    return fetch_blob(driver, url_archivo)


def descargar_todas_las_empresas_api(driver, ruta_descargas, dias_atras=7):
    """
    Flujo completo por API: obtiene el token de la sesión actual, lista las
    empresas, y para cada una descarga el CSV de movimientos de su(s)
    cuenta(s), guardándolos en ruta_descargas.
    """
    os.makedirs(ruta_descargas, exist_ok=True)

    cerrar_modales_bloqueantes(driver, timeout=8)

    print("Obteniendo token de sesión desde el navegador...")
    token, uuid = obtener_sesion_api(driver)
    print(f"  Token obtenido (uuid de sesión: {uuid})")

    print("Consultando empresas...")
    empresas = obtener_empresas(driver, token, uuid)
    print(f"  {len(empresas)} empresa(s) encontrada(s)")

    resultados = {}

    for empresa in empresas:
        nombre = empresa["name"]
        company_id = empresa["companyId"]

        archivo = MAPEO_ARCHIVOS.get(nombre.strip().upper())
        if not archivo:
            print(f"\n(Se omite '{nombre}': no está en MAPEO_ARCHIVOS)")
            continue

        print(f"\n{'='*80}\n{nombre} (companyId={company_id})\n{'='*80}")

        try:
            cuentas = obtener_cuentas(driver, token, uuid, company_id)
            if not cuentas:
                print("  Sin cuentas visibles para esta empresa, se omite.")
                resultados[nombre] = None
                continue

            # Si hubiera más de una cuenta, se descarga la primera.
            cuenta = cuentas[0]
            account_id = cuenta["accountId"]
            numero = cuenta.get("accountNumber", "")
            print(f"  Cuenta {numero} (accountId={account_id})")

            contenido_csv = descargar_csv_cuenta(driver, token, uuid, company_id, account_id, dias_atras)

            ruta_final = os.path.join(ruta_descargas, archivo)
            with open(ruta_final, "wb") as f:
                f.write(contenido_csv)

            print(f"  Guardado: {ruta_final} ({len(contenido_csv)} bytes)")
            resultados[nombre] = ruta_final

        except Exception as e:
            print(f"  ERROR procesando {nombre}: {e}")
            resultados[nombre] = None

    print("\n" + "=" * 80)
    print("RESUMEN:")
    for nombre, rutas in resultados.items():
        estado = rutas if rutas else "FALLÓ"
        print(f"  {nombre}: {estado}")

    return resultados