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
)
from webdriver_manager.chrome import ChromeDriverManager

# Ajusta el import según dónde hayas dejado la carpeta token_web/
from selenium_utils import cerrar_modales_bloqueantes
from componentes_comunes import (LectorArchivos, 
    RUTAS_CONFIG)
import telegram_2fa

URL_LOGIN = "https://bancaempresas.pichincha.com/"
# IMPORTANTE: no uses la URL completa de "authorize?..." capturada de una sesión
# del navegador. Esa URL trae un nonce/state/code_challenge de un solo uso,
# generado por MSAL.js y atado al sessionStorage de esa sesión puntual.
# Reusarla en una sesión de Selenium nueva puede dejar el flujo OAuth en un
# estado inconsistente (el formulario carga pero el estado interno está roto).
# Deja que la propia página redirija y genere su flujo OAuth fresco, igual que
# hace un usuario real al entrar a la home del banco.

TIMEOUT_ELEMENTO = 20  # segundos de espera para cada elemento


def crear_driver(headless=False, ruta_descargas=None):
    """Crea el driver de Chrome con opciones anti-detección básicas."""
    opciones = Options()

    if headless:
        opciones.add_argument("--headless=new")

    opciones.add_argument("--disable-blink-features=AutomationControlled")
    opciones.add_argument("--disable-dev-shm-usage")  # evita crashes de renderer por memoria compartida limitada
    opciones.add_argument("--no-sandbox")  # Chrome se niega a iniciar corriendo como root sin esto
    opciones.add_argument("--start-maximized")
    opciones.add_argument("--disable-infobars")
    opciones.add_experimental_option("excludeSwitches", ["enable-automation"])
    opciones.add_experimental_option("useAutomationExtension", False)

    # Habilita la captura de logs de red (CDP) — la app del banco cifra su
    # access token dentro de sessionStorage (no usa el cache estándar de
    # MSAL), así que la única forma limpia de conseguirlo es leyéndolo del
    # header Authorization real que la propia app manda en sus peticiones
    # — lo mismo que verías a mano en DevTools > Network.
    opciones.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    if ruta_descargas:
        opciones.add_experimental_option("prefs", {
            "download.default_directory": ruta_descargas,
            "download.prompt_for_download": False,
        })

    servicio = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=servicio, options=opciones)

    # Habilita el dominio Network de CDP para poder leer después los headers
    # reales (incluyendo Authorization) de las peticiones que la app haga.
    driver.execute_cdp_cmd("Network.enable", {})

    # Oculta navigator.webdriver, igual que hacías en Playwright con add_init_script
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
        elemento = WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((by, selector))
        )
        return elemento
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
    """
    Escribe en un campo de forma robusta para apps React/Angular donde el
    tipeo carácter por carácter (send_keys) pierde teclas por la velocidad
    del re-render del framework.

    En vez de simular teclas, escribe el valor DIRECTO usando el setter nativo
    del <input> (bypassea el tracking interno de React) y dispara 'input' +
    'change' manualmente — es exactamente lo que hace Playwright.fill() por
    debajo, y es atómico: no hay carrera con el framework.

    Luego verifica que el valor se mantenga estable (por si hay validación
    async que lo limpia en el blur) y reintenta si hace falta.
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

    for intento in range(1, max_intentos + 1):
        elemento = esperar_y_obtener(driver, by, selector, timeout, descripcion)
        elemento.click()  # asegura foco real, algunos widgets lo necesitan

        driver.execute_script(JS_SET_VALUE, elemento, texto)

        time.sleep(espera_estabilidad)
        valor_actual = elemento.get_attribute("value")

        if valor_actual == texto:
            return
        else:
            print(f"  Aviso: '{descripcion}' quedó como '{valor_actual}', "
                  f"reintentando ({intento}/{max_intentos})...")

    raise Exception(
        f"El campo '{descripcion}' no mantiene el valor correcto tras {max_intentos} intentos "
        f"(quedó como '{valor_actual}'). Revisar si hay una máscara/formato especial en el campo."
    )


def login_pichincha(driver, usuario, password, id_ejecucion=0):
    """
    Realiza el login completo: usuario/contraseña + espera manual del código 2FA
    a través de la web local (token_web).
    """
    print("Navegando a la home del banco (dejamos que redirija sola al login)...")
    driver.get(URL_LOGIN)

    # La home hace un par de redirecciones (home -> authorize de Azure B2C) antes
    # de que el formulario de usuario/contraseña esté realmente listo. Esperamos
    # a que el campo sea VISIBLE (no solo que exista en el DOM).
    print("Esperando a que cargue el formulario de login...")
    WebDriverWait(driver, TIMEOUT_ELEMENTO).until(
        EC.visibility_of_element_located((By.ID, "signInName"))
    )

    print("Ingresando usuario y contraseña...")
    escribir_seguro(driver, By.ID, "signInName", usuario, descripcion="usuario")
    escribir_seguro(driver, By.ID, "password", password, descripcion="password")

    # Revalidación final: el 'blur' de usuario (al enfocar contraseña) puede
    # disparar la validación async que lo vacía DESPUÉS de que ya lo verificamos.
    # Si pasó, lo reescribimos justo antes de enviar.
    campo_usuario = esperar_y_obtener(driver, By.ID, "signInName", descripcion="usuario (revalidación)")
    if campo_usuario.get_attribute("value") != usuario:
        print("  El campo usuario se vació tras pasar a contraseña, reescribiendo antes de enviar...")
        escribir_seguro(driver, By.ID, "signInName", usuario, descripcion="usuario", espera_estabilidad=0.3)

    # IMPORTANTE: el sitio usa reCAPTCHA Enterprise y solo lo dispara con
    # eventos 'keyup' reales en los campos (o al hacer clic en Ingresar, como
    # respaldo). Como escribimos los campos por JS (sin keyup), el token nunca
    # se generaba al escribir. Lo disparamos manualmente aquí y ESPERAMOS a
    # que el token exista antes del primer clic — así no dependemos de que un
    # clic anterior haya dejado un token cacheado.
    print("Generando token de reCAPTCHA...")
    driver.execute_script("if (typeof generateCaptcha === 'function') { generateCaptcha(); }")
    try:
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script(
                "return document.getElementById('g-recaptcha-response-toms')?.value?.length > 0;"
            )
        )
        print("  Token de reCAPTCHA listo.")
    except TimeoutException:
        print("  Aviso: el token de reCAPTCHA no se generó en 15s, se continúa igual "
              "(el clic en Ingresar también lo dispara como respaldo).")

    # Espera a que el botón esté realmente HABILITADO (no solo presente/clickeable
    # en el DOM). Muchos formularios lo deshabilitan mientras corre una validación
    # interna tras rellenar los campos, y dar clic antes de que se habilite
    # produce un error de submit.
    print("Esperando a que el botón 'Ingresar' esté habilitado...")
    WebDriverWait(driver, TIMEOUT_ELEMENTO).until(
        lambda d: d.find_element(By.ID, "continue").get_attribute("disabled") is None
    )
    time.sleep(1.5)  # margen extra de seguridad tras habilitarse

    # Reintentos de clic: a veces el primer clic no "prende" (overlay, foco,
    # timing del framework). El botón "#continue" se REUTILIZA en todos los
    # pasos del wizard de Azure B2C (login, código, etc.) — es el mismo ID en
    # todo el flujo, así que su desaparición NO es una señal confiable de
    # progreso. Lo que sí es confiable es la aparición de las casillas del
    # código (#oneDigit, etc.), que solo existen en el paso del token.
    IDS_DIGITOS = ["oneDigit", "twoDigit", "threeDigit", "fourDigit", "fiveDigit", "sixDigit"]

    MAX_INTENTOS_LOGIN = 3
    pantalla_2fa_cargo = False

    for intento_login in range(1, MAX_INTENTOS_LOGIN + 1):
        # ¿Ya estamos en la pantalla del token? (quizás el clic anterior sí
        # funcionó y solo tardó en reflejarse)
        casillas = driver.find_elements(By.ID, "oneDigit")
        if casillas and casillas[0].is_displayed():
            pantalla_2fa_cargo = True
            break

        print(f"Clic en 'Ingresar' (intento {intento_login}/{MAX_INTENTOS_LOGIN})...")
        click_seguro(driver, By.ID, "continue", descripcion="botón login",
                     timeout=5, opcional=True)

        try:
            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.ID, "oneDigit"))
            )
            pantalla_2fa_cargo = True
            break
        except TimeoutException:
            # Antes de reintentar, revisa si el banco mostró su propio mensaje
            # de error real (ej. "Usuario o contraseña incorrecta") — si es así,
            # no tiene sentido seguir reintentando el clic.
            alerta_error = driver.find_elements(By.ID, "warning")
            if alerta_error:
                clases = alerta_error[0].get_attribute("class") or ""
                if "hiden" not in clases:
                    texto_error = alerta_error[0].text.strip()
                    raise Exception(
                        f"El banco rechazó el login con el mensaje: '{texto_error}'. "
                        "Revisa las credenciales."
                    )

            if intento_login < MAX_INTENTOS_LOGIN:
                print("  La pantalla del token no cargó todavía, reintentando...")
                time.sleep(1.5)
                continue

    if not pantalla_2fa_cargo:
        raise Exception(
            f"No apareció la pantalla del token de seguridad tras {MAX_INTENTOS_LOGIN} intentos. "
            "Es probable que usuario/contraseña sí estén siendo rechazados por el banco "
            "(revisa manualmente esas credenciales) o que haya un captcha/bloqueo adicional."
        )

    print("Pantalla del token confirmada. Enviando aviso por Telegram y "
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

    print("Código recibido, ingresándolo en las 6 casillas del Pichincha Token...")
    # El código no va en un solo campo: son 6 casillas de un dígito cada una
    # (id="oneDigit" ... id="sixDigit"), generadas por la app Pichincha Token.
    for id_casilla, digito in zip(IDS_DIGITOS, codigo):
        escribir_seguro(driver, By.ID, id_casilla, digito, descripcion=f"dígito ({id_casilla})",
                        espera_estabilidad=0.3)

    # El botón "continue" se habilita solo cuando las 6 casillas están completas.
    print("Esperando a que el botón 'Ingresar' se habilite tras completar el código...")
    WebDriverWait(driver, TIMEOUT_ELEMENTO).until(
        lambda d: d.find_element(By.ID, "continue").get_attribute("disabled") is None
    )
    time.sleep(1)

    click_seguro(driver, By.ID, "continue", descripcion="botón validar código")

    # Señal de éxito confiable: la URL deja de estar en el dominio de login
    # (login.empresas.pichincha.com) y vuelve al dominio de la app
    # (bancaempresas.pichincha.com) con la sesión ya iniciada.
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

    # Cierra cualquier modal bloqueante que pueda aparecer justo tras el
    # login (el "¿Qué hay de nuevo?", diálogos de sesión, tour guiado...).
    # Si no se cierra, la app puede interpretar la falta de interacción real
    # como inactividad/comportamiento anómalo y cortar la sesión.
    print("Verificando y cerrando modales bloqueantes si aparecen...")
    cerrar_modales_bloqueantes(driver, timeout=15)

    print("Login completado.")
    return True


if __name__ == "__main__":
    # --- Datos de prueba: reemplaza por la lectura real de tus credenciales ---

    # Leer credenciales del banco
    credenciales_banco = LectorArchivos.leerCSV(
        RUTAS_CONFIG['credenciales_banco'],
        filtro_columna=0,
        valor_filtro="Banco Pichincha"
    )

    USUARIO = credenciales_banco[0][1]
    PASSWORD = credenciales_banco[0][2]

    print(USUARIO, PASSWORD)

    # Carpeta local donde se van a guardar los CSVs descargados
    RUTA_DESCARGAS = os.path.join(os.getcwd(), "descargas_pichincha")
    os.makedirs(RUTA_DESCARGAS, exist_ok=True)

    driver = crear_driver(headless=False, ruta_descargas=RUTA_DESCARGAS)
    try:
        login_pichincha(driver, USUARIO, PASSWORD, id_ejecucion=999)
        print("Login OK. Iniciando descarga de movimientos de las 4 empresas...")

        # Opción A: por API directa (recomendado — más rápido y estable,
        # sin depender de selectores de UI que puedan cambiar).
        from download_by_api import descargar_todas_las_empresas_api
        descargar_todas_las_empresas_api(driver, RUTA_DESCARGAS)

        # Opción B: clickeando la UI (respaldo si el endpoint cambia)
        # from descargar_movimientos import descargar_todas_las_empresas
        # descargar_todas_las_empresas(driver, RUTA_DESCARGAS)

        input("Proceso terminado. Presiona Enter para cerrar el navegador...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()