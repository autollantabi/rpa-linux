# -*- coding: utf-8 -*-
"""
login_pichincha_selenium.py

RPA con Selenium para iniciar sesión en Banco Pichincha Empresas.
Usa los mismos selectores que ya validaste en tu versión Playwright.

Requisitos:
    pip install selenium webdriver-manager --break-system-packages

El 2FA se resuelve por Telegram (ver telegram_2fa.py): el script envía un
aviso al chat configurado y espera a que respondas ahí mismo con los 6
dígitos — ya no depende de abrir http://localhost:5050.
"""
import re
import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
)
from webdriver_manager.chrome import ChromeDriverManager

# Ajusta el import según dónde hayas dejado la carpeta token_web/
from selenium_utils import cerrar_modales_bloqueantes
from componentes_comunes import (LectorArchivos, 
    RUTAS_CONFIG, LogManager)
import telegram_2fa

URL_LOGIN = "https://bancaempresas.pichincha.com/"
TIMEOUT_ELEMENTO = 20  # segundos de espera para cada elemento


def crear_driver(headless=False, ruta_descargas=None):
    """Crea el driver de Chrome con opciones anti-detección básicas."""
    opciones = Options()

    if headless:
        opciones.add_argument("--headless=new")

    opciones.add_argument("--disable-blink-features=AutomationControlled")
    opciones.add_argument("--disable-dev-shm-usage")
    opciones.add_argument("--no-sandbox")
    # Cada refresco de token recarga la página completa (incluyendo el
    # widget de reCAPTCHA), y ya vimos advertencias de "too many active
    # WebGL contexts" en versiones anteriores — --disable-gpu fuerza
    # renderizado por software, evitando que se agoten esos contextos y
    # el navegador termine cerrándose solo tras varias recargas.
    opciones.add_argument("--disable-gpu")
    opciones.add_argument("--start-maximized")
    opciones.add_argument("--disable-infobars")
    opciones.add_experimental_option("excludeSwitches", ["enable-automation"])
    opciones.add_experimental_option("useAutomationExtension", False)
    opciones.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    if ruta_descargas:
        opciones.add_experimental_option("prefs", {
            "download.default_directory": ruta_descargas,
            "download.prompt_for_download": False,
        })

    servicio = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=servicio, options=opciones)
    driver.execute_cdp_cmd("Network.enable", {})
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', { get: () => ['es-ES', 'es', 'en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        """
    })
    return driver


def esperar_y_obtener(driver, by, selector, timeout=TIMEOUT_ELEMENTO, descripcion=""):
    try:
        return WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((by, selector))
        )
    except TimeoutException:
        raise Exception(f"No se encontró/visible el elemento '{descripcion or selector}' tras {timeout}s")


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
                     max_intentos=3, espera_estabilidad=0.8):
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
    for intento in range(1, max_intentos + 1):
        elemento = esperar_y_obtener(driver, by, selector, timeout, descripcion)
        elemento.click()
        driver.execute_script(JS_SET_VALUE, elemento, texto)
        time.sleep(espera_estabilidad)
        valor_actual = elemento.get_attribute("value")
        if valor_actual == texto:
            return
        else:
            LogManager.escribir_log("WARNING", f"'{descripcion}' quedó como '{valor_actual}', "
                  f"reintentando ({intento}/{max_intentos})...")
    raise Exception(
        f"El campo '{descripcion}' no mantiene el valor correcto tras {max_intentos} intentos "
        f"(quedó como '{valor_actual}'). Revisar si hay una máscara/formato especial en el campo."
    )


def login_pichincha(driver, usuario, password, id_ejecucion=0):
    """Realiza el login completo: usuario/contraseña + espera del código 2FA por Telegram."""
    LogManager.escribir_log("INFO", "Navegando a la home del banco (dejamos que redirija sola al login)...")
    driver.get(URL_LOGIN)

    LogManager.escribir_log("INFO", "Esperando a que cargue el formulario de login...")
    WebDriverWait(driver, TIMEOUT_ELEMENTO).until(
        EC.visibility_of_element_located((By.ID, "signInName"))
    )

    # El banco agregó un modal de "Por su seguridad" (#securityModal) que
    # puede aparecer justo al cargar esta pantalla, tapando el formulario.
    # Lo cerramos ANTES de intentar escribir usuario/contraseña, si no, el
    # clic para enfocar esos campos puede quedar interceptado por el
    # overlay del modal.
    cerrar_modales_bloqueantes(driver, timeout=10)

    LogManager.escribir_log("INFO", "Ingresando usuario y contraseña...")
    escribir_seguro(driver, By.ID, "signInName", usuario, descripcion="usuario")
    escribir_seguro(driver, By.ID, "password", password, descripcion="password")

    campo_usuario = esperar_y_obtener(driver, By.ID, "signInName", descripcion="usuario (revalidación)")
    if campo_usuario.get_attribute("value") != usuario:
        LogManager.escribir_log("WARNING", "El campo usuario se vació tras pasar a contraseña, reescribiendo antes de enviar...")
        escribir_seguro(driver, By.ID, "signInName", usuario, descripcion="usuario", espera_estabilidad=0.3)

    LogManager.escribir_log("INFO", "Generando token de reCAPTCHA...")
    driver.execute_script("if (typeof generateCaptcha === 'function') { generateCaptcha(); }")
    try:
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script(
                "return document.getElementById('g-recaptcha-response-toms')?.value?.length > 0;"
            )
        )
        LogManager.escribir_log("SUCCESS", "Token de reCAPTCHA listo.")
    except TimeoutException:
        LogManager.escribir_log("WARNING", "El token de reCAPTCHA no se generó en 15s, se continúa igual "
              "(el clic en Ingresar también lo dispara como respaldo).")

    LogManager.escribir_log("INFO", "Esperando a que el botón 'Ingresar' esté habilitado...")
    WebDriverWait(driver, TIMEOUT_ELEMENTO).until(
        lambda d: d.find_element(By.ID, "continue").get_attribute("disabled") is None
    )
    time.sleep(1.5)

    IDS_DIGITOS = ["oneDigit", "twoDigit", "threeDigit", "fourDigit", "fiveDigit", "sixDigit"]

    # Mensajes del banco que sí son FATALES (no tiene caso reintentar). Todo
    # lo demás que aparezca en #warning se trata como transitorio/genérico
    # (ej. "Ha ocurrido un error, intente de nuevo más tarde") y se reintenta.
    PATRONES_FATALES = [
        "contraseña incorrecta",
        "usuario o contraseña",
        "límite de intentos",
        "supera el límite",
        "cuenta bloqueada",
        "usuario bloqueado",
    ]

    MAX_INTENTOS_LOGIN = 3
    pantalla_2fa_cargo = False

    for intento_login in range(1, MAX_INTENTOS_LOGIN + 1):
        casillas = driver.find_elements(By.ID, "oneDigit")
        if casillas and casillas[0].is_displayed():
            pantalla_2fa_cargo = True
            break

        LogManager.escribir_log("INFO", f"Clic en 'Ingresar' (intento {intento_login}/{MAX_INTENTOS_LOGIN})...")
        click_seguro(driver, By.ID, "continue", descripcion="botón login",
                     timeout=5, opcional=True)

        try:
            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.ID, "oneDigit"))
            )
            pantalla_2fa_cargo = True
            break
        except TimeoutException:
            # Antes de reintentar, revisa si el banco mostró un mensaje de
            # error real, y si es FATAL (credenciales/bloqueo) o solo
            # transitorio/genérico (en cuyo caso sí vale la pena reintentar).
            #
            # Envuelto en try/except porque justo aquí la página puede estar
            # en pleno cambio de pantalla — el elemento puede volverse
            # "stale" entre una línea y la siguiente, lo cual normalmente es
            # BUENA señal (la navegación sí está avanzando).
            try:
                alerta_error = driver.find_elements(By.ID, "warning")
                if alerta_error:
                    clases = alerta_error[0].get_attribute("class") or ""
                    if "hiden" not in clases:
                        texto_error = alerta_error[0].text.strip()
                        texto_error_normalizado = texto_error.lower()
                        es_fatal = any(patron in texto_error_normalizado for patron in PATRONES_FATALES)

                        if es_fatal:
                            raise Exception(
                                f"El banco rechazó el login con el mensaje: '{texto_error}'. "
                                "Revisa las credenciales."
                            )
                        else:
                            LogManager.escribir_log(
                                "WARNING",
                                f"El banco mostró un mensaje genérico/transitorio: '{texto_error}' — "
                                "se reintenta en vez de abortar."
                            )
            except StaleElementReferenceException:
                LogManager.escribir_log(
                    "INFO", "La página cambió de pantalla justo al verificar errores (buena señal), continuando...")

            if intento_login < MAX_INTENTOS_LOGIN:
                LogManager.escribir_log("WARNING", "La pantalla del token no cargó todavía, reintentando...")
                time.sleep(1.5)
                continue

    if not pantalla_2fa_cargo:
        raise Exception(
            f"No apareció la pantalla del token de seguridad tras {MAX_INTENTOS_LOGIN} intentos. "
            "Es probable que usuario/contraseña sí estén siendo rechazados por el banco "
            "(revisa manualmente esas credenciales) o que haya un captcha/bloqueo adicional."
        )

    LogManager.escribir_log("INFO", "Pantalla del token confirmada. Enviando aviso por Telegram y "
          f"esperando el código (ejecución #{id_ejecucion})...")

    codigo = telegram_2fa.esperar_codigo(
        id_ejecucion=id_ejecucion,
        banco="Banco Pichincha",
        timeout_segundos=300,
        intervalo=2,
    )

    if not codigo:
        raise Exception("No se ingresó el código de seguridad a tiempo (timeout de 5 min)")

    if not re.fullmatch(r"^\d{6}$", codigo):
        raise Exception(f"Código con formato inválido recibido: '{codigo}'")

    LogManager.escribir_log("INFO", "Código recibido, ingresándolo en las 6 casillas del Pichincha Token...")
    for id_casilla, digito in zip(IDS_DIGITOS, codigo):
        escribir_seguro(driver, By.ID, id_casilla, digito, descripcion=f"dígito ({id_casilla})",
                        espera_estabilidad=0.3)

    LogManager.escribir_log("INFO", "Esperando a que el botón 'Ingresar' se habilite tras completar el código...")
    WebDriverWait(driver, TIMEOUT_ELEMENTO).until(
        lambda d: d.find_element(By.ID, "continue").get_attribute("disabled") is None
    )
    time.sleep(1)

    click_seguro(driver, By.ID, "continue", descripcion="botón validar código")

    try:
        WebDriverWait(driver, 20).until(
            lambda d: "login.empresas.pichincha.com" not in d.current_url
        )
    except TimeoutException:
        raise Exception(
            "El código fue enviado pero la página no salió de la pantalla de login tras 20s. "
            "Puede que el código esté incorrecto/expirado (el token dura ~30s) o que haya "
            "un mensaje de error en pantalla — revisa manualmente."
        )

    LogManager.escribir_log("INFO", "Verificando y cerrando modales bloqueantes si aparecen...")
    cerrar_modales_bloqueantes(driver, timeout=15)

    LogManager.escribir_log("SUCCESS", "Login completado.")
    return True


if __name__ == "__main__":
    credenciales_banco = LectorArchivos.leerCSV(
        RUTAS_CONFIG['credenciales_banco'],
        filtro_columna=0,
        valor_filtro="Banco Pichincha"
    )
    USUARIO = credenciales_banco[0][1]
    PASSWORD = credenciales_banco[0][2]

    RUTA_DESCARGAS = os.path.join(os.getcwd(), "descargas_pichincha")
    os.makedirs(RUTA_DESCARGAS, exist_ok=True)

    driver = crear_driver(headless=False, ruta_descargas=RUTA_DESCARGAS)
    try:
        login_pichincha(driver, USUARIO, PASSWORD, id_ejecucion=999)
        LogManager.escribir_log("SUCCESS", "Login OK. Iniciando descarga de movimientos de las 4 empresas...")
        from download_by_api import descargar_todas_las_empresas_api
        descargar_todas_las_empresas_api(driver, RUTA_DESCARGAS)
        input("Proceso terminado. Presiona Enter para cerrar el navegador...")
    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error: {e}")
    finally:
        driver.quit()