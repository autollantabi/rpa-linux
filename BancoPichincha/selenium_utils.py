# -*- coding: utf-8 -*-
"""
selenium_utils.py

Helpers compartidos por login_pichincha_selenium.py, descargar_movimientos.py
y sesion_persistente.py: clics/esperas robustas, y un cierre de modales
bloqueantes que atraviesa shadow DOM (los componentes del banco son web
components, así que un clic normal de Selenium no siempre llega al botón
real).
"""
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException

TIMEOUT_DEFECTO = 20


def click_seguro(driver, by, selector, timeout=TIMEOUT_DEFECTO, descripcion="", opcional=False):
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


def esperar_visible(driver, by, selector, timeout=TIMEOUT_DEFECTO, descripcion=""):
    try:
        return WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((by, selector))
        )
    except TimeoutException:
        raise Exception(f"No se encontró/visible '{descripcion or selector}' tras {timeout}s")


# JS que busca un elemento por texto exacto ATRAVESANDO shadow DOM (recursivo
# por cada shadowRoot que encuentre) y le dispara un evento de clic real.
# Devuelve true si encontró y clickeó algo.
_JS_BUSCAR_Y_CLICKEAR = """
    function buscarEnRoot(root, textos) {
        const candidatos = root.querySelectorAll('*');
        for (const el of candidatos) {
            const texto = (el.textContent || '').trim();
            for (const t of textos) {
                if (texto === t) {
                    el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                    return true;
                }
            }
            if (el.shadowRoot) {
                if (buscarEnRoot(el.shadowRoot, textos)) return true;
            }
        }
        return false;
    }
    return buscarEnRoot(document, arguments[0]);
"""

_JS_HAY_MODAL = """
    return document.querySelector('.modal.wrapper, .modal__background, ngx-guided-tour .tour-step') !== null;
"""

_JS_OCULTAR_MODAL_FORZADO = """
    document.querySelectorAll('.modal.wrapper, .modal__background').forEach(el => {
        el.style.display = 'none';
        el.style.pointerEvents = 'none';
    });
    document.querySelectorAll('ngx-guided-tour').forEach(el => el.remove());
"""


def cerrar_modales_bloqueantes(driver, timeout=15, intervalo=1.5,
                                textos_botones=None):
    """
    Cierra modales bloqueantes (ej. "¿Qué hay de nuevo?", tour guiado,
    diálogos de sesión) que puedan aparecer sobre la pantalla.

    Reintenta durante `timeout` segundos buscando un botón con alguno de
    `textos_botones` — la búsqueda atraviesa shadow DOM, así que encuentra
    botones aunque estén dentro de web components (pichincha-old-button,
    etc.), donde un `.click()` normal de Selenium a veces no llega al
    control real.

    Si después del timeout el modal sigue ahí (no se encontró ningún botón
    reconocible), lo oculta por la fuerza vía JS como último recurso, para
    que no siga bloqueando el resto de la automatización.
    """
    if textos_botones is None:
        textos_botones = ["Entendido", "Aceptar", "OK", "Cancelar", "Cerrar", "Continuar"]

    inicio = time.time()
    algo_cerrado = False

    while time.time() - inicio < timeout:
        hay_modal = driver.execute_script(_JS_HAY_MODAL)
        if not hay_modal:
            break

        clickeado = driver.execute_script(_JS_BUSCAR_Y_CLICKEAR, textos_botones)
        if clickeado:
            algo_cerrado = True
            print("  Modal cerrado (botón encontrado por texto).")
            time.sleep(1)
        else:
            time.sleep(intervalo)

    sigue_bloqueado = driver.execute_script(_JS_HAY_MODAL)
    if sigue_bloqueado:
        print("  Aviso: el modal no se pudo cerrar con clic, ocultándolo por JS como respaldo...")
        driver.execute_script(_JS_OCULTAR_MODAL_FORZADO)

    return algo_cerrado