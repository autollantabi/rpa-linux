# -*- coding: utf-8 -*-
"""
login_bolivariano_selenium.py

RPA con Selenium para iniciar sesión en Banco Bolivariano (Banca Digital de
Empresas). El flujo tiene 3 pasos, cada uno con su propia URL, y se avanza
de uno al siguiente dando clic en "Continuar":

    1) https://www13.bolivariano.com/            -> usuario
    2) https://www13.bolivariano.com/loginStep2   -> contraseña
    3) https://www13.bolivariano.com/loginStep3   -> código OTP (correo)

El código OTP del paso 3 se lee automáticamente del correo con
CorreoManager.obtener_codigo_correo (componentes_comunes.py), usando las
credenciales del buzón que están en
/home/administrador/configBancos/config/credencialesCorreo.csv (el mismo
archivo central que usan los demás bancos).

Requisitos (ya instalados en el venv del proyecto):
    selenium, webdriver-manager, python-dotenv
"""
import os
import re
import time
from datetime import datetime, timezone, timedelta

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import (
    TimeoutException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
)
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv

from componentes_comunes import CorreoManager

load_dotenv()

URL_LOGIN = "https://www13.bolivariano.com/"

TIMEOUT_ELEMENTO = 20  # segundos de espera para cada elemento

# Carpeta donde se guardan capturas de pantalla de depuración en cada paso
# (se puede sobreescribir con la variable de entorno BOLIVARIANO_CAPTURAS).
RUTA_CAPTURAS = os.environ.get(
    "BOLIVARIANO_CAPTURAS", os.path.join(os.getcwd(), "capturas_bolivariano")
)

_contador_capturas = 0


def guardar_captura(driver, nombre):
    """
    Guarda una captura de pantalla en RUTA_CAPTURAS con un prefijo numérico
    y de hora, para poder ver en qué paso se quedó el RPA sin depender de
    tener el navegador visible (útil en el servidor, donde corre headless).
    Nunca lanza excepción: si falla el guardado, solo lo avisa por consola.
    """
    global _contador_capturas
    try:
        os.makedirs(RUTA_CAPTURAS, exist_ok=True)
        _contador_capturas += 1
        marca = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"{_contador_capturas:02d}_{marca}_{nombre}.png"
        ruta = os.path.join(RUTA_CAPTURAS, nombre_archivo)
        driver.save_screenshot(ruta)
        print(f"  📸 Captura guardada: {ruta}")
    except Exception as e:
        print(f"  Aviso: no se pudo guardar la captura '{nombre}': {e}")


def crear_driver(headless=False, ruta_descargas=None):
    """
    Crea el driver de Chrome con opciones anti-detección básicas.

    IMPORTANTE: `headless=True` (--headless=new) es detectado por el banco,
    que responde con la pantalla "Navegador no soportado" en vez del login
    (mismo comportamiento ya observado con Banco Pichincha/Akamai). En el
    servidor SIN pantalla física, la forma correcta de correr esto es con
    `headless=False` pero apuntando DISPLAY a un Xvfb ("headless real": el
    navegador cree que tiene una pantalla real, solo que es virtual) — ver
    bashPichincha.sh como referencia de ese patrón. No usar headless=True
    aquí salvo para pruebas rápidas donde no importe que el banco bloquee.
    """
    opciones = Options()

    if headless:
        opciones.add_argument("--headless=new")
        # "--start-maximized" no tiene efecto en headless (la ventana queda
        # en 800x600 por defecto), lo que puede dejar elementos fuera de
        # vista/no clickeables: se fija un tamaño de escritorio explícito.
        opciones.add_argument("--window-size=1920,1080")
    else:
        opciones.add_argument("--start-maximized")

    opciones.add_argument("--disable-blink-features=AutomationControlled")
    opciones.add_argument("--disable-dev-shm-usage")
    opciones.add_argument("--no-sandbox")
    opciones.add_argument("--disable-infobars")
    opciones.add_experimental_option("excludeSwitches", ["enable-automation"])
    opciones.add_experimental_option("useAutomationExtension", False)

    if ruta_descargas:
        opciones.add_experimental_option("prefs", {
            "download.default_directory": ruta_descargas,
            "download.prompt_for_download": False,
        })

    servicio = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=servicio, options=opciones)

    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', { get: () => ['es-ES', 'es', 'en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        """
    })

    return driver


def esperar_visible(driver, by, selector, timeout=TIMEOUT_ELEMENTO, descripcion=""):
    try:
        return WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((by, selector))
        )
    except TimeoutException:
        raise Exception(f"No se encontró/visible '{descripcion or selector}' tras {timeout}s")


def click_seguro(driver, by, selector, timeout=TIMEOUT_ELEMENTO, descripcion="", opcional=False):
    try:
        elemento = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((by, selector))
        )
        try:
            elemento.click()
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", elemento)
        return True
    except TimeoutException:
        if opcional:
            return False
        raise Exception(f"No se pudo hacer clic en '{descripcion or selector}' tras {timeout}s")


def escribir_seguro(driver, by, selector, texto, timeout=TIMEOUT_ELEMENTO, descripcion="",
                     max_intentos=3, espera_estabilidad=0.6):
    """
    Escribe en un campo de forma robusta para apps React (el sitio usa
    styled-components/React) escribiendo el valor directo con el setter
    nativo del <input> y disparando 'input'/'change' manualmente, en vez de
    send_keys carácter por carácter (que puede perder teclas por el
    re-render del framework).
    """
    JS_SET_VALUE = """
        const el = arguments[0];
        const valor = arguments[1];
        const proto = Object.getPrototypeOf(el);
        const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
        if (descriptor && descriptor.set) {
            descriptor.set.call(el, valor);
        } else {
            el.value = valor;
        }
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
    """

    valor_actual = None
    for intento in range(1, max_intentos + 1):
        try:
            esperar_visible(driver, by, selector, timeout, descripcion)

            # El campo de usuario arranca "disabled" mientras la SPA termina
            # de hidratar/precargar el valor recordado ("Recordar usuario").
            # Re-consulta el elemento en CADA verificación (no una
            # referencia cacheada): si React reemplaza el nodo del campo al
            # pasar de disabled a habilitado, una referencia tomada de
            # antemano queda "stale" (StaleElementReferenceException).
            WebDriverWait(driver, timeout).until(
                lambda d: d.find_element(by, selector).get_attribute("disabled") is None
            )

            # Vuelve a tomar el elemento fresco justo antes de interactuar,
            # por la misma razón.
            elemento = driver.find_element(by, selector)
            elemento.click()
            driver.execute_script(JS_SET_VALUE, elemento, texto)
            time.sleep(espera_estabilidad)
            valor_actual = driver.find_element(by, selector).get_attribute("value")

            if valor_actual == texto:
                return
            print(f"  Aviso: '{descripcion}' quedó como '{valor_actual}', "
                  f"reintentando ({intento}/{max_intentos})...")
        except StaleElementReferenceException:
            valor_actual = "(elemento obsoleto/stale)"
            print(f"  Aviso: el campo '{descripcion}' quedó obsoleto (stale) mientras se escribía, "
                  f"reintentando ({intento}/{max_intentos})...")
            time.sleep(0.3)

    raise Exception(
        f"El campo '{descripcion}' no mantiene el valor correcto tras {max_intentos} intentos "
        f"(quedó como '{valor_actual}')."
    )


def _esperar_url(driver, predicado, timeout=TIMEOUT_ELEMENTO, descripcion=""):
    """
    Espera a que la URL actual cumpla `predicado(url)`, tolerando errores
    transitorios de chromedriver que pueden salir al consultar `current_url`
    justo durante una navegación de dominio completo (ej. al salir de
    www13.bolivariano.com hacia el portal ya autenticado) — sin esto, un
    error pasajero de ese tipo aborta la espera en vez de solo reintentar.
    """
    def _condicion(d):
        try:
            return predicado(d.current_url)
        except Exception:
            return False

    try:
        WebDriverWait(driver, timeout).until(_condicion)
    except TimeoutException:
        raise Exception(f"No se confirmó '{descripcion or 'la navegación esperada'}' tras {timeout}s")


def _click_continuar(driver, descripcion=""):
    """
    El botón "Continuar" de cada paso es un <button type="submit"> dentro del
    <form> del login, sin id propio. Se espera a que se habilite (no basta
    con que sea clickeable: la SPA lo deja disabled hasta validar el campo)
    y luego se hace clic.
    """
    selector = "form button[type='submit']"

    WebDriverWait(driver, TIMEOUT_ELEMENTO).until(
        lambda d: d.find_element(By.CSS_SELECTOR, selector).get_attribute("disabled") is None
    )
    time.sleep(0.5)  # margen tras habilitarse, igual que en Pichincha
    click_seguro(driver, By.CSS_SELECTOR, selector, descripcion=descripcion or "botón Continuar")


def login_paso1_usuario(driver, usuario):
    """Paso 1: pantalla de usuario (https://www13.bolivariano.com/)."""
    print("Navegando a la home de Banco Bolivariano...")
    driver.get(URL_LOGIN)
    guardar_captura(driver, "paso1_home")

    print("Esperando el formulario de usuario...")
    esperar_visible(driver, By.ID, "usernamefield", descripcion="campo usuario")

    print("Ingresando usuario...")
    escribir_seguro(driver, By.ID, "usernamefield", usuario, descripcion="usuario")
    guardar_captura(driver, "paso1_usuario_ingresado")

    print("Clic en 'Continuar' (paso usuario)...")
    _click_continuar(driver, descripcion="Continuar (usuario)")

    _esperar_url(driver, lambda url: "loginStep2" in url, descripcion="avance a loginStep2")
    print("Paso 1 completado: avanzó a loginStep2.")
    guardar_captura(driver, "paso1_completado")


def login_paso2_password(driver, password):
    """Paso 2: pantalla de contraseña (https://www13.bolivariano.com/loginStep2)."""
    print("Esperando el formulario de contraseña...")
    esperar_visible(driver, By.ID, "passwordfield", descripcion="campo contraseña")

    print("Ingresando contraseña...")
    escribir_seguro(driver, By.ID, "passwordfield", password, descripcion="contraseña")
    guardar_captura(driver, "paso2_password_ingresada")

    print("Clic en 'Continuar' (paso contraseña)...")
    _click_continuar(driver, descripcion="Continuar (contraseña)")

    _esperar_url(driver, lambda url: "loginStep3" in url, descripcion="avance a loginStep3")
    print("Paso 2 completado: avanzó a loginStep3 (pantalla de OTP).")
    guardar_captura(driver, "paso2_completado")


def login_usuario_password(driver, usuario, password):
    """
    Resuelve los pasos 1 y 2 (usuario + contraseña) y deja el navegador en
    la pantalla del OTP (paso 3).

    Devuelve el instante (datetime UTC) en que se confirmó la pantalla de
    OTP, útil como referencia de "no aceptar correos anteriores a esto" al
    leer el código del correo.
    """
    login_paso1_usuario(driver, usuario)
    login_paso2_password(driver, password)

    esperar_visible(driver, By.ID, "pin_0", descripcion="primera casilla del OTP")
    momento_pantalla_otp = datetime.now(timezone.utc)
    print("Pantalla de OTP confirmada (loginStep3).")
    guardar_captura(driver, "paso3_pantalla_otp")
    return momento_pantalla_otp


def login_paso3_otp(driver, codigo):
    """Paso 3: ingresa el código OTP (https://www13.bolivariano.com/loginStep3)."""
    if not re.fullmatch(r"\d{6}", codigo):
        raise Exception(f"Código OTP con formato inválido: '{codigo}'")

    print("Ingresando el código OTP en las 6 casillas...")
    for indice, digito in enumerate(codigo):
        escribir_seguro(driver, By.ID, f"pin_{indice}", digito,
                         descripcion=f"dígito OTP #{indice}", espera_estabilidad=0.3)
    guardar_captura(driver, "paso3_otp_ingresado")

    print("Clic en 'Continuar' (paso OTP)...")
    _click_continuar(driver, descripcion="Continuar (OTP)")

    # Timeout más largo que en los pasos anteriores: aquí el sitio suele
    # hacer una navegación de dominio completo hacia el portal ya
    # autenticado (no solo un cambio de ruta dentro de la misma SPA).
    _esperar_url(driver, lambda url: "loginStep3" not in url, timeout=30,
                 descripcion="salida de loginStep3 tras validar el OTP")
    print("Paso 3 completado: login finalizado, sesión iniciada.")
    guardar_captura(driver, "paso3_login_finalizado")


def login_completo(driver, usuario, password, timeout_otp_segundos=180, margen_seguridad_segundos=30):
    """
    Encadena los 3 pasos: usuario, contraseña y OTP (leído automáticamente
    del correo vía CorreoManager, el mismo componente compartido que usan
    los demás bancos, con credenciales tomadas de
    RUTAS_CONFIG['credenciales_correo'] en vez de un .env propio).
    """
    momento_pantalla_otp = login_usuario_password(driver, usuario, password)

    print("Esperando el correo con el código OTP...")
    codigo = CorreoManager.obtener_codigo_correo(
        asunto="Tu código temporal es...",
        intentos=timeout_otp_segundos,
        espera=1,
        timestamp_inicio=momento_pantalla_otp - timedelta(seconds=margen_seguridad_segundos),
    )
    if not codigo:
        guardar_captura(driver, "error_sin_codigo_otp")
        raise Exception("No llegó el código OTP por correo a tiempo.")

    login_paso3_otp(driver, codigo)
    return True


# ==================== NAVEGACIÓN A LA CUENTA Y DESCARGA ====================

SELECTOR_TARJETA_CUENTA = "div.prod-item.prod-accounts a.prod-item-link"
SELECTOR_BOTON_DESCARGAR = "button.btn-download"


def obtener_enlaces_cuentas(driver, timeout=TIMEOUT_ELEMENTO):
    """
    Devuelve los enlaces (elementos <a class="prod-item-link">) de las
    tarjetas de cuenta en la pantalla 'Mis cuentas' (home tras el login).
    """
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, SELECTOR_TARJETA_CUENTA)) > 0
        )
    except TimeoutException:
        raise Exception("No se encontraron tarjetas de cuenta en 'Mis cuentas' tras {}s".format(timeout))
    return driver.find_elements(By.CSS_SELECTOR, SELECTOR_TARJETA_CUENTA)


def seleccionar_cuenta(driver, indice=0):
    """
    En la pantalla 'Mis cuentas' (post-login), hace clic en la tarjeta de la
    cuenta indicada por `indice` (0 = primera) y espera a que cargue la
    pantalla de detalle de esa cuenta (con el botón 'Descargar' visible).
    """
    print(f"Buscando tarjetas de cuenta en 'Mis cuentas' (índice a elegir: {indice})...")
    enlaces = obtener_enlaces_cuentas(driver)
    if indice >= len(enlaces):
        raise Exception(f"Se pidió la cuenta #{indice} pero solo hay {len(enlaces)} disponible(s)")

    guardar_captura(driver, "cuentas_antes_de_clic")

    url_actual = driver.current_url
    print(f"Clic en la tarjeta de la cuenta #{indice}...")
    try:
        enlaces[indice].click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", enlaces[indice])

    _esperar_url(
        driver,
        lambda url: url != url_actual and "/accounts/" in url,
        descripcion="navegación al detalle de la cuenta",
    )
    esperar_visible(
        driver, By.CSS_SELECTOR, SELECTOR_BOTON_DESCARGAR,
        descripcion="botón 'Descargar' en el detalle de cuenta",
    )
    print("Detalle de cuenta cargado.")
    guardar_captura(driver, "detalle_cuenta_cargado")


def _clic_opcion_formato(driver, formato, timeout):
    """
    Hace clic en la opción de formato (ej. 'txt') dentro del menú que se
    abre al dar clic en 'Descargar'. El menú no existe en el DOM hasta que
    se abre, así que primero intenta ubicarlo dentro del contenedor
    '.dropdown' del botón (donde debería renderizarse) y, si no aparece ahí
    a tiempo, cae a una búsqueda global por texto exacto como respaldo.
    """
    xpath_dentro_dropdown = (
        f"//button[contains(@class,'btn-download')]/ancestor::div[contains(@class,'dropdown')][1]"
        f"//*[normalize-space(text())='{formato}']"
    )
    xpath_global = f"//*[normalize-space(text())='{formato}']"

    for xpath, espera in ((xpath_dentro_dropdown, min(5, timeout)), (xpath_global, timeout)):
        try:
            opcion = WebDriverWait(driver, espera).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            try:
                opcion.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", opcion)
            return
        except TimeoutException:
            continue

    guardar_captura(driver, f"error_opcion_formato_{formato}_no_encontrada")
    raise Exception(f"No se encontró la opción de formato '{formato}' en el menú 'Descargar'")


def _archivo_descarga_listo(ruta_descargas, momento_inicio, extension):
    """
    Busca en `ruta_descargas` un archivo con `extension` modificado después
    de `momento_inicio`, siempre que no haya ninguna descarga ".crdownload"
    en curso (Chrome usa ese sufijo temporal mientras descarga).
    Devuelve la ruta completa si está lista, o None si todavía no.
    """
    nombres = os.listdir(ruta_descargas)

    if any(nombre.lower().endswith(".crdownload") for nombre in nombres):
        return None

    candidatos = [
        os.path.join(ruta_descargas, nombre)
        for nombre in nombres
        if nombre.lower().endswith(extension.lower())
    ]
    candidatos_nuevos = [
        ruta for ruta in candidatos if os.path.getmtime(ruta) >= momento_inicio
    ]
    if not candidatos_nuevos:
        return None

    return max(candidatos_nuevos, key=os.path.getmtime)


def descargar_movimientos(driver, ruta_descargas, formato="txt",
                           timeout_menu=TIMEOUT_ELEMENTO, timeout_descarga=60):
    """
    En la pantalla de detalle de cuenta, hace clic en 'Descargar' y elige el
    formato indicado ('txt' por defecto). Espera a que el archivo termine de
    descargarse en `ruta_descargas` (sin '.crdownload' pendiente) y devuelve
    su ruta completa.
    """
    os.makedirs(ruta_descargas, exist_ok=True)

    print("Clic en 'Descargar'...")
    click_seguro(driver, By.CSS_SELECTOR, SELECTOR_BOTON_DESCARGAR, descripcion="botón Descargar")
    guardar_captura(driver, "menu_descargar_abierto")

    print(f"Seleccionando el formato '{formato}' en el menú...")
    momento_click = time.time()
    _clic_opcion_formato(driver, formato, timeout_menu)
    guardar_captura(driver, f"formato_{formato}_seleccionado")

    print(f"Esperando a que se complete la descarga del archivo .{formato}...")
    inicio_espera = time.time()
    while time.time() - inicio_espera < timeout_descarga:
        ruta_archivo = _archivo_descarga_listo(ruta_descargas, momento_click, f".{formato}")
        if ruta_archivo:
            print(f"Archivo descargado: {os.path.basename(ruta_archivo)}")
            return ruta_archivo
        time.sleep(1)

    guardar_captura(driver, f"error_descarga_{formato}_no_detectada")
    raise Exception(f"No se detectó la descarga del archivo .{formato} tras {timeout_descarga}s")


def login_y_descargar_movimientos(driver, usuario, password, ruta_descargas,
                                   indice_cuenta=0, formato="txt"):
    """
    Flujo completo: login (usuario + contraseña + OTP), clic en la cuenta
    en 'Mis cuentas' y descarga de movimientos en el formato indicado.
    Devuelve la ruta del archivo descargado.

    Ante cualquier error en el camino, guarda una captura de pantalla del
    estado en que se quedó el navegador antes de relanzar la excepción,
    para poder diagnosticar en qué paso falló sin tener el navegador visible
    (ej. corriendo headless en el servidor).
    """
    try:
        login_completo(driver, usuario, password)
        seleccionar_cuenta(driver, indice=indice_cuenta)
        return descargar_movimientos(driver, ruta_descargas, formato=formato)
    except Exception:
        guardar_captura(driver, "error_fatal_flujo")
        raise


if __name__ == "__main__":
    USUARIO = os.environ.get("BOLIVARIANO_USERNAME", "").strip()
    PASSWORD = os.environ.get("BOLIVARIANO_PASSWORD", "").strip()

    if not USUARIO or not PASSWORD:
        raise SystemExit(
            "Faltan BOLIVARIANO_USERNAME y/o BOLIVARIANO_PASSWORD en el .env "
            "(ver .env.example en esta misma carpeta)."
        )

    RUTA_DESCARGAS = os.path.join(os.getcwd(), "descargas_bolivariano")
    os.makedirs(RUTA_DESCARGAS, exist_ok=True)

    # OJO: headless=True es detectado por el banco ("Navegador no soportado").
    # En el servidor sin pantalla física, corre esto bajo Xvfb (ver
    # bashPichincha.sh) dejando BOLIVARIANO_HEADLESS=false (el valor por
    # defecto); solo usar "true" para pruebas rápidas sin banco real.
    HEADLESS = os.environ.get("BOLIVARIANO_HEADLESS", "false").strip().lower() not in ("false", "0", "no")

    driver = crear_driver(headless=HEADLESS, ruta_descargas=RUTA_DESCARGAS)
    try:
        ruta_archivo = login_y_descargar_movimientos(driver, USUARIO, PASSWORD, RUTA_DESCARGAS)
        print(f"Login y descarga completados. Archivo: {ruta_archivo}")
        try:
            input("Presiona Enter para cerrar el navegador...")
        except EOFError:
            # Corrida no interactiva (sin terminal para leer el Enter):
            # deja el navegador abierto un rato para poder revisarlo antes
            # de cerrarlo solo.
            print("Sesión no interactiva: dejo el navegador abierto 60s para revisión visual...")
            time.sleep(60)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()
