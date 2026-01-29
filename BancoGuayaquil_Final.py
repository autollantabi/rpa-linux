# -*- coding: utf-8 -*-
"""
BANCO GUAYAQUIL - AUTOMATIZACIÓN COMPLETA OPTIMIZADA
"""
import os
import sys
import time
import json
import threading
import re
import email
import email.utils
import imaplib
from datetime import datetime, date, timedelta, timezone
from functools import wraps
from email.header import decode_header

from componentes_comunes import (
    PlaywrightManager,
    ComponenteInteraccion,
    EsperasInteligentes,
    LectorArchivos,
    LogManager,
    BaseDatos,
    SubprocesoManager,
    CorreoManager,
    ConfiguracionManager,
    RUTAS_CONFIG,
    esperarConLoader,
    esperarConLoaderSimple,
)

# ==================== CONTEXTO DE TIMEOUT ====================


class TimeoutManager:
    """Maneja timeouts globales de manera automática"""

    def __init__(self, timeout_seconds=600):
        self.timeout_seconds = timeout_seconds
        self.start_time = None
        self.timer = None
        self.is_timeout = False

    def start(self):
        """Inicia el timer de timeout"""
        self.start_time = datetime.now()
        self.is_timeout = False
        LogManager.escribir_log(
            "INFO", f"Timeout manager iniciado: {self.timeout_seconds//60} minutos")

        # Configurar timer
        self.timer = threading.Timer(
            self.timeout_seconds, self._timeout_callback)
        self.timer.daemon = True
        self.timer.start()

    def _timeout_callback(self):
        """Callback que se ejecuta cuando se alcanza el timeout"""
        self.is_timeout = True
        tiempo_str = formatear_tiempo_ejecucion(
            datetime.now() - self.start_time)
        LogManager.escribir_log(
            "ERROR", f"TIMEOUT GLOBAL ALCANZADO: {tiempo_str}")

        # Forzar salida del programa
        os._exit(1)

    def check(self):
        """Verifica si se ha alcanzado el timeout"""
        if self.is_timeout:
            tiempo_str = formatear_tiempo_ejecucion(
                datetime.now() - self.start_time)
            raise TimeoutError(
                f"Proceso terminado por timeout global ({tiempo_str})")

    def get_elapsed_time(self):
        """Obtiene el tiempo transcurrido"""
        if self.start_time:
            return datetime.now() - self.start_time
        return timedelta(0)

    def stop(self):
        """Detiene el timer"""
        if self.timer:
            self.timer.cancel()
            self.timer = None


# Instancia global del timeout manager
timeout_manager = TimeoutManager(600)  # 10 minutos


def with_timeout_check(func):
    """Decorator que verifica timeout antes de ejecutar funciones críticas"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        timeout_manager.check()
        return func(*args, **kwargs)
    return wrapper


def formatear_tiempo_ejecucion(tiempo_delta):
    """Formatea un timedelta a string legible"""
    total_seconds = int(tiempo_delta.total_seconds())
    minutos = total_seconds // 60
    segundos = total_seconds % 60
    return f"{minutos}m {segundos}s"

# ==================== CONFIGURACIÓN GLOBAL ====================


# DATABASE = "RegistrosBancosPRUEBA"
# DATABASE_LOGS = "AutomationLogPRUEBA"
# DATABASE_RUNS = "AutomationRunPRUEBA"
DATABASE = "RegistrosBancos"
DATABASE_LOGS = "AutomationLog"
DATABASE_RUNS = "AutomationRun"
NOMBRE_BANCO = "Banco Guayaquil"

URLS = {
    'login': "https://empresas.bancoguayaquil.com/BancaEmpresas/login",
}

# ==================== FUNCIONES DE BASE DE DATOS ====================


def obtenerIDEjecucion():
    """Obtiene el siguiente ID de ejecución de la BD"""
    try:
        sql = f"SELECT MAX(idAutomationRun) FROM {DATABASE_RUNS}"
        resultado = BaseDatos.consultarBD(sql)
        if resultado and resultado[0] and resultado[0][0]:
            return resultado[0][0] + 1
        return 1
    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error obteniendo ID ejecución: {str(e)}")
        return int(time.time())  # Fallback


def datosEjecucion(sql):
    """Ejecuta una consulta en la BD"""
    try:
        BaseDatos.ejecutarSQL(sql)
        return True
    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error ejecutando SQL: {str(e)}")
        return False


def escribirLog(mensaje, id_ejecucion, estado, accion):
    """Escribe un log en la BD"""
    texto_limpio = mensaje.replace("'", "''")
    sql = f"""
        INSERT INTO {DATABASE_LOGS} (idAutomationRun, processName, dateLog, statusLog, action)
        VALUES ({id_ejecucion}, '{texto_limpio}', SYSDATETIME(), '{estado}', '{accion}')
    """
    datosEjecucion(sql)

# ==================== FUNCIONES DE LOGIN ====================


def realizar_login_completo(page, timestamp_inicio=None):
    """Realiza el login completo en Banco Guayaquil"""
    try:
        LogManager.escribir_log("INFO", "Iniciando proceso de login")

        # Leer credenciales
        credenciales = LectorArchivos.leerCSV(
            RUTAS_CONFIG['credenciales_banco'],
            filtro_columna=0,
            valor_filtro="Banco Guayaquil"
        )

        if not credenciales:
            raise Exception(
                "No se pudieron leer las credenciales de Banco Guayaquil")

        credenciales = credenciales[0]
        usuario = credenciales[1]
        password = credenciales[2]

        # Navegar a la página (sin esperar carga completa, solo que esté disponible)
        LogManager.escribir_log("INFO", "Navegando a página de login...")
        page.goto(URLS['login'], wait_until="domcontentloaded", timeout=15000)
        
        # Esperar solo que los campos de login estén disponibles (sin esperar carga completa)
        LogManager.escribir_log("INFO", "Esperando que los campos de login estén disponibles...")
        page.wait_for_selector("input[placeholder=\"Usuario\"], input[id=\"password\"]", timeout=10000, state="visible")

        # Escribir credenciales
        LogManager.escribir_log("INFO", "Escribiendo credenciales...")
        if not ComponenteInteraccion.escribirComponente(
            page,
            "input[placeholder=\"Usuario\"]",
            usuario,
            descripcion="usuario"
        ):
            raise Exception("No se pudo escribir el usuario")

        if not ComponenteInteraccion.escribirComponente(
            page,
            "input[id=\"password\"]",
            password,
            descripcion="password"
        ):
            raise Exception("No se pudo escribir la contraseña")
        
        # Hacer clic en botón Ingresar
        LogManager.escribir_log("INFO", "Haciendo clic en botón 'Ingresar'...")
        if not ComponenteInteraccion.clickComponente(
            page,
            "//button[.//span[contains(text(),'Ingresar')]]",
            descripcion="botón login"
        ):
            raise Exception("No se pudo hacer clic en el botón de login")

        # Esperar un momento breve para que se procese el clic
        esperarConLoaderSimple(2, "Esperando procesamiento del login")
       
        # Buscar el código en el correo inmediatamente después de hacer clic en Ingresar
        asunto_correo = "Código para ingresar a tu Banca Empresas"
        LogManager.escribir_log("INFO", f"Buscando código de seguridad en el correo con asunto: '{asunto_correo}'...")
        if timestamp_inicio:
            LogManager.escribir_log("INFO", f"Usando timestamp de inicio del programa: {timestamp_inicio.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        codigo = CorreoManager.obtener_codigo_correo(
            asunto=asunto_correo,
            timestamp_inicio=timestamp_inicio,
        )

        if codigo and re.fullmatch(r"^\d{6}$", codigo):
            LogManager.escribir_log(
                "SUCCESS", f"Código válido recibido: {codigo}")

            # Escribir cada dígito en su campo correspondiente
            for i, digito in enumerate(codigo):
                selector_input = f"//input[@id='cb-otp__input-{i}-securityCode']"

                ComponenteInteraccion.escribirComponente(
                    page,
                    selector_input,
                    digito,
                    descripcion=f"código seguridad dígito {i+1}"
                )

            # Manejo de diálogos opcionales
            ComponenteInteraccion.clickComponente(
                page,
                "//button[.//span[contains(text(), 'Continuar')]]",
                descripcion="diálogo confirmación",
                intentos=2,
                timeout=3000
            )
            # Manejar diálogos posteriores
            esperarConLoaderSimple(2, "Procesando código de seguridad")

        else:
            raise Exception(
                "No se pudo validar código de seguridad después de todos los intentos")

        # Manejar posibles diálogos o ventanas emergentes
        ComponenteInteraccion.clickComponenteOpcional(
            page,
            "//button[.//span[contains(text(), 'Aceptar')]]",
            descripcion="diálogo de confirmación",
            intentos=2,
            timeout=3000
        )
        # Manejar posibles diálogos o ventanas emergentes
        ComponenteInteraccion.clickComponente(
            page,
            "//button[.//span[contains(text(), 'Ir a mi Resumen')]]",
            descripcion="diálogo de confirmación",
            intentos=2,
            timeout=3000
        )

        LogManager.escribir_log("SUCCESS", "Login completado exitosamente")
        return True

    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error en login: {str(e)}")
        return False

# ==================== FUNCIONES DE NAVEGACIÓN ====================

def cerrar_iframe_inicial(page):
    """Cierra el iframe que aparece antes de buscar el menú Cuentas"""
    try:
        LogManager.escribir_log("INFO", "Buscando iframe inicial (antes de menú Cuentas)...")
        
        # Esperar un momento para que aparezca el iframe
        esperarConLoaderSimple(2, "Esperando aparición del iframe inicial")
        
        # Buscar el iframe con múltiples selectores
        selectores_iframe = [
            "//appcues-container//iframe",
            "//div[contains(@class, 'appcues')]//iframe",
            "//appcues-container[@class*='appcues-fullscreen']//iframe",
            "//iframe[contains(@src, 'about:blank')]",
            "iframe",
        ]
        
        frame_locator = None
        
        for selector_iframe in selectores_iframe:
            try:
                LogManager.escribir_log("INFO", f"Buscando iframe inicial con selector: {selector_iframe}")
                if ComponenteInteraccion.esperarElemento(page, selector_iframe, timeout=5000, descripcion="iframe inicial"):
                    frame_locator = page.frame_locator(selector_iframe).first
                    LogManager.escribir_log("SUCCESS", f"✅ Iframe inicial encontrado con selector: {selector_iframe}")
                    break
            except Exception as e:
                LogManager.escribir_log("DEBUG", f"Selector iframe {selector_iframe} no funcionó: {str(e)}")
                continue
        
        # Si no se encontró el iframe, continuar directamente
        if not frame_locator:
            LogManager.escribir_log("INFO", "No se encontró iframe inicial, continuando con el proceso")
            return True
        
        # Esperar carga completa del iframe
        esperarConLoaderSimple(2, "Esperando carga completa del iframe inicial")
        
        # Buscar el botón X dentro del iframe
        LogManager.escribir_log("INFO", "Buscando botón X dentro del iframe inicial...")
        
        selectores_boton_iframe = [
            "//a[@data-step='skip' and @aria-label='Close modal']",
            "//a[@data-step='skip']",
            "//a[@aria-label='Close modal']",
            "//div[@class='appcues-skip']//a[@data-step='skip']",
            "//div[@class='appcues-skip']//a[@aria-label='Close modal']",
            "//div[@class='appcues-skip']//a",
            "//a[@role='button' and @aria-label='Close modal']",
        ]
        
        boton_clickeado = False
        for selector_boton in selectores_boton_iframe:
            try:
                LogManager.escribir_log("INFO", f"Buscando botón X con selector: {selector_boton}")
                boton_locator = frame_locator.locator(selector_boton)
                boton_locator.wait_for(state="visible", timeout=5000)
                
                if boton_locator.is_visible(timeout=2000):
                    boton_locator.click(timeout=3000)
                    LogManager.escribir_log("SUCCESS", f"✅ Botón X clickeado exitosamente en iframe inicial")
                    boton_clickeado = True
                    esperarConLoaderSimple(1, "Esperando cierre del iframe inicial")
                    break
            except Exception as e:
                LogManager.escribir_log("DEBUG", f"Selector {selector_boton} no funcionó: {str(e)}")
                continue
        
        if boton_clickeado:
            LogManager.escribir_log("SUCCESS", "✅ Iframe inicial cerrado exitosamente")
        else:
            LogManager.escribir_log("WARNING", "Iframe inicial encontrado pero no se pudo hacer clic en el botón X, continuando...")
        
        return True
        
    except Exception as e:
        LogManager.escribir_log("WARNING", f"Error cerrando iframe inicial: {str(e)}")
        return True  # Continuar de todas formas


def navegar_a_movimientos(page):
    """Navega a la página de movimientos/consulta de cuentas"""
    try:
        LogManager.escribir_log("INFO", "Navegando a página de movimientos...")

        esperarConLoaderSimple(3, "Esperando carga de página principal")

        # PASO 0: Cerrar iframe inicial si aparece (antes de buscar Cuentas)
        cerrar_iframe_inicial(page)
        esperarConLoaderSimple(1, "Esperando después de cerrar iframe inicial")

        # PASO 1: Buscar y hacer clic en el menú "Cuentas" en el PanelMenu
        LogManager.escribir_log("INFO", "Buscando menú 'Cuentas' en el PanelMenu...")
        
        # Múltiples selectores para el menú Cuentas basados en el HTML del PanelMenu
        selectores_cuentas = [
            "//a[contains(@class, 'p-panelmenu-header-link') and .//span[contains(@class, 'p-menuitem-text') and contains(text(), 'Cuentas')]]",
            "//a[contains(@class, 'p-panelmenu-header-link') and contains(., 'Cuentas')]",
            "//div[contains(@class, 'p-panelmenu-header')]//a[.//span[contains(text(), 'Cuentas')]]",
            "//div[contains(@class, 'cb-menu__selected-item')]//a[.//span[contains(text(), 'Cuentas')]]",
            "//a[@href='/BancaEmpresas/content/blank' and .//span[contains(text(), 'Cuentas')]]",
            "//span[contains(@class, 'p-menuitem-text') and contains(text(), 'Cuentas')]//ancestor::a",
            "//a[contains(text(), 'Cuentas')]",
        ]
        
        cuentas_clickeado = False
        for selector_cuentas in selectores_cuentas:
            try:
                LogManager.escribir_log("INFO", f"Buscando menú Cuentas con selector: {selector_cuentas}")
                if ComponenteInteraccion.esperarElemento(page, selector_cuentas, timeout=5000, descripcion="menú cuentas"):
                    if ComponenteInteraccion.clickComponente(page, selector_cuentas, descripcion="menú cuentas", intentos=2, timeout=3000):
                        LogManager.escribir_log("SUCCESS", f"Menú 'Cuentas' clickeado exitosamente")
                        cuentas_clickeado = True
                        break
            except Exception as e:
                LogManager.escribir_log("DEBUG", f"Selector {selector_cuentas} no funcionó: {str(e)}")
                continue
        
        if not cuentas_clickeado:
            raise Exception("No se pudo hacer clic en el menú 'Cuentas'")
        
        esperarConLoaderSimple(3, "Esperando carga de página de Cuentas")
        
        # PASO 2: Buscar y hacer clic en "Consultar movimientos" en la página de Cuentas
        LogManager.escribir_log("INFO", "Buscando 'Consultar movimientos' en la página de Cuentas...")
        
        # Múltiples selectores para "Consultar movimientos" basados en el HTML de cb-menu-table
        selectores_movimientos = [
            "//div[contains(@class, 'cb-menu-table__item')]//img[@alt='menu-corporate.accounts.movementsInquiry.menu']//ancestor::div[contains(@class, 'cb-menu-table__item')]",
            "//div[contains(@class, 'cb-menu-table__item-container')]//div[contains(@class, 'cb-menu-table__title') and contains(text(), 'Consultar movimientos')]",
            "//div[contains(@class, 'cb-menu-table__title') and contains(text(), 'Consultar movimientos')]",
            "//div[contains(@class, 'cb-menu-table__item')]//div[contains(@class, 'cb-menu-table__title') and contains(text(), 'Consultar movimientos')]",
            "//img[@alt='menu-corporate.accounts.movementsInquiry.menu']//ancestor::div[contains(@class, 'cb-menu-table__item')]",
            "//div[contains(text(), 'Consultar movimientos')]",
        ]
        
        movimientos_clickeado = False
        for selector_movimientos in selectores_movimientos:
            try:
                LogManager.escribir_log("INFO", f"Buscando 'Consultar movimientos' con selector: {selector_movimientos}")
                if ComponenteInteraccion.esperarElemento(page, selector_movimientos, timeout=5000, descripcion="Consultar movimientos"):
                    if ComponenteInteraccion.clickComponente(
                        page, selector_movimientos, descripcion="Opción consultar movimientos", intentos=3, timeout=3000):
                        LogManager.escribir_log("SUCCESS", f"'Consultar movimientos' clickeado exitosamente")
                        movimientos_clickeado = True
                        break
            except Exception as e:
                LogManager.escribir_log("DEBUG", f"Selector {selector_movimientos} no funcionó: {str(e)}")
                continue
        
        if not movimientos_clickeado:
            raise Exception("No se pudo hacer clic en 'Consultar movimientos'")
        
        esperarConLoaderSimple(5, "Esperando carga de página de movimientos")

        LogManager.escribir_log("SUCCESS", "Navegación a movimientos exitosa")
        return True

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error navegando a movimientos: {str(e)}")
        return False

# ==================== FUNCIONES DE CONSULTA ====================


@with_timeout_check
def obtener_y_procesar_movimientos(page, id_ejecucion):
    """Obtiene y procesa los movimientos de todas las empresas disponibles"""
    try:
        LogManager.escribir_log(
            "INFO", "Iniciando obtención de movimientos...")

        # Procesar múltiples empresas
        return procesar_todas_las_empresas(page, id_ejecucion)

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error obteniendo movimientos: {str(e)}")
        return False


def cerrar_modal_seguridad(page):
    """Cierra el modal/iframe de seguridad que aparece después de entrar en Consulta de movimientos"""
    try:
        LogManager.escribir_log("INFO", "Buscando modal de seguridad (iframe)...")
        
        # PASO 1: Buscar el iframe con timeout corto primero (3 segundos)
        selectores_iframe = [
            "//appcues-container//iframe",
            "//div[contains(@class, 'appcues')]//iframe",
            "//iframe[contains(@src, 'about:blank')]",
            "iframe",
        ]
        
        iframe_encontrado = None
        frame_locator = None
        
        for selector_iframe in selectores_iframe:
            try:
                LogManager.escribir_log("INFO", f"Buscando iframe con selector: {selector_iframe}")
                if ComponenteInteraccion.esperarElemento(page, selector_iframe, timeout=3000, descripcion="iframe modal"):
                    # Obtener el frame_locator
                    iframe_encontrado = page.locator(selector_iframe).first
                    frame_locator = page.frame_locator(selector_iframe).first
                    LogManager.escribir_log("SUCCESS", f"✅ Iframe encontrado con selector: {selector_iframe}")
                    break
            except Exception as e:
                LogManager.escribir_log("DEBUG", f"Selector iframe {selector_iframe} no funcionó: {str(e)}")
                continue
        
        # Si no se encontró el iframe, continuar directamente sin esperar más
        if not frame_locator:
            LogManager.escribir_log("INFO", "No se encontró iframe del modal de seguridad, continuando con el proceso")
            return True  # Continuar directamente con el dropdown de empresas
        
        # PASO 2: Si encontramos el iframe, esperar un poco más y buscar el botón dentro de él
        LogManager.escribir_log("INFO", "Iframe encontrado, esperando carga completa...")
        esperarConLoaderSimple(2, "Esperando carga completa del iframe")
        
        LogManager.escribir_log("INFO", "Buscando botón X dentro del iframe...")
        
        # Selectores para el botón X dentro del iframe
        selectores_boton_iframe = [
            "//a[@data-step='skip' and @aria-label='Close modal']",
            "//a[@data-step='skip']",
            "//a[@aria-label='Close modal']",
            "//div[@class='appcues-skip']//a[@data-step='skip']",
            "//div[@class='appcues-skip']//a[@aria-label='Close modal']",
            "//div[@class='appcues-skip']//a",
            "//a[@role='button' and @aria-label='Close modal']",
        ]
        
        boton_clickeado = False
        for selector_boton in selectores_boton_iframe:
            try:
                LogManager.escribir_log("INFO", f"Buscando botón X dentro del iframe con selector: {selector_boton}")
                
                # Buscar el elemento dentro del iframe
                boton_locator = frame_locator.locator(selector_boton)
                
                # Esperar que sea visible
                boton_locator.wait_for(state="visible", timeout=5000)
                
                # Verificar que sea visible
                if boton_locator.is_visible(timeout=2000):
                    # Hacer clic
                    boton_locator.click(timeout=3000)
                    LogManager.escribir_log("SUCCESS", f"✅ Botón X clickeado exitosamente dentro del iframe con selector: {selector_boton}")
                    boton_clickeado = True
                    esperarConLoaderSimple(1, "Esperando cierre del modal")
                    break
            except Exception as e:
                LogManager.escribir_log("DEBUG", f"Selector {selector_boton} dentro del iframe no funcionó: {str(e)}")
                continue
        
        if boton_clickeado:
            LogManager.escribir_log("SUCCESS", "✅ Modal de seguridad cerrado exitosamente")
            return True
        else:
            LogManager.escribir_log("WARNING", "Iframe encontrado pero no se pudo hacer clic en el botón X, continuando...")
            return True  # Continuar de todas formas
        
    except Exception as e:
        LogManager.escribir_log("WARNING", f"Error cerrando modal de seguridad: {str(e)}")
        # Continuar de todas formas, puede que el modal no aparezca siempre
        return True


def procesar_todas_las_empresas(page, id_ejecucion):
    """Procesa todas las empresas disponibles en el dropdown"""
    try:
        LogManager.escribir_log(
            "INFO", "Iniciando procesamiento de todas las empresas...")

        empresas_procesadas = []
        nombres_empresas_procesadas = []
        max_intentos_globales = 3
        intentos_globales = 0

        while intentos_globales < max_intentos_globales:
            try:
                LogManager.escribir_log(
                    "INFO", f"Intento {intentos_globales + 1}/{max_intentos_globales} para procesar empresas")
                
                # PASO CRÍTICO: Intentar cerrar el modal/iframe de seguridad (si existe)
                cerrar_modal_seguridad(page)
                
                # Esperar un momento antes de continuar
                esperarConLoaderSimple(1, "Esperando antes de buscar selector de empresa")
                
                # Esperar a que la página cargue completamente
                esperarConLoaderSimple(2, "Esperando carga completa de página de movimientos")
                
                # Múltiples selectores alternativos para el autocomplete de empresa
                selectores_autocomplete = [
                    "//input[contains(@name, 'enterpriseCustomerId')]",
                    "//input[contains(@id, 'enterprise')]",
                    "//input[contains(@placeholder, 'empresa') or contains(@placeholder, 'Empresa')]",
                    "//p-autocomplete//input",
                    "//input[@type='text' and contains(@class, 'p-autocomplete-input')]",
                    "//input[contains(@class, 'p-inputtext')]",
                ]
                
                selector_autocomplete = None
                elemento_encontrado = False
                
                # Intentar encontrar el selector con múltiples alternativas
                for selector in selectores_autocomplete:
                    LogManager.escribir_log("INFO", f"Buscando selector de empresa: {selector}")
                    if ComponenteInteraccion.esperarElemento(page, selector, timeout=5000, descripcion=f"selector empresa ({selector})"):
                        selector_autocomplete = selector
                        elemento_encontrado = True
                        LogManager.escribir_log("SUCCESS", f"Selector encontrado: {selector}")
                        break
                
                if not elemento_encontrado:
                    LogManager.escribir_log(
                        "ERROR", "No se encontró el selector de empresa con ninguno de los selectores probados")
                    # Esperar un poco más y reintentar
                    esperarConLoaderSimple(3, "Esperando antes de reintentar búsqueda de selector")
                    intentos_globales += 1
                    continue

                # Buscar el botón del dropdown de PrimeNG específico para empresas
                # Usar el input como referencia para encontrar el botón correcto
                boton_dropdown_encontrado = False
                
                try:
                    # Método 1: Buscar el botón que está cerca del input de empresa (más específico)
                    # El botón debería estar en el mismo contenedor que el input
                    input_locator = page.locator(selector_autocomplete).first
                    
                    # Buscar el botón dropdown en el mismo contenedor padre
                    boton_dropdown_locator = input_locator.locator("..").locator("//button[contains(@class, 'p-autocomplete-dropdown')]").first
                    
                    if boton_dropdown_locator.is_visible(timeout=2000):
                        boton_dropdown_locator.click(timeout=3000)
                        LogManager.escribir_log("SUCCESS", "Botón dropdown clickeado exitosamente (método contenedor)")
                        boton_dropdown_encontrado = True
                except Exception as e:
                    LogManager.escribir_log("DEBUG", f"Método contenedor no funcionó: {str(e)}")
                
                # Método 2: Buscar usando el contexto del formulario "Tu empresa"
                if not boton_dropdown_encontrado:
                    try:
                        # Buscar el botón dentro del contexto del formulario que contiene "Tu empresa"
                        selector_boton_especifico = "//form[contains(., 'Tu empresa')]//button[contains(@class, 'p-autocomplete-dropdown')] | //form[contains(., 'empresa')]//button[contains(@class, 'p-autocomplete-dropdown')]"
                        boton_especifico = page.locator(selector_boton_especifico).first
                        
                        if boton_especifico.is_visible(timeout=2000) and not boton_especifico.is_disabled(timeout=1000):
                            boton_especifico.click(timeout=3000)
                            LogManager.escribir_log("SUCCESS", "Botón dropdown clickeado exitosamente (método formulario)")
                            boton_dropdown_encontrado = True
                    except Exception as e:
                        LogManager.escribir_log("DEBUG", f"Método formulario no funcionó: {str(e)}")
                
                # Método 3: Usar JavaScript para encontrar el botón correcto
                if not boton_dropdown_encontrado:
                    try:
                        script = """
                        var input = document.querySelector('input[name*="enterpriseCustomerId"]');
                        if (input) {
                            var container = input.closest('p-autocomplete, .p-autocomplete, [class*="autocomplete"]');
                            if (container) {
                                var button = container.querySelector('button.p-autocomplete-dropdown:not([disabled])');
                                if (button) {
                                    button.click();
                                    return true;
                                }
                            }
                        }
                        return false;
                        """
                        resultado = page.evaluate(script)
                        if resultado:
                            LogManager.escribir_log("SUCCESS", "Botón dropdown clickeado exitosamente (método JavaScript)")
                            boton_dropdown_encontrado = True
                    except Exception as e:
                        LogManager.escribir_log("DEBUG", f"Método JavaScript no funcionó: {str(e)}")
                
                # Si no se encontró el botón dropdown, intentar con el input directamente
                if not boton_dropdown_encontrado:
                    LogManager.escribir_log("INFO", "Botón dropdown no encontrado, intentando con input directamente")
                    if not ComponenteInteraccion.clickComponente(
                        page, selector_autocomplete, descripcion="abrir dropdown empresas", intentos=2, timeout=3000):
                        LogManager.escribir_log("WARNING", "No se pudo hacer clic en el selector, intentando escribir...")
                        # Intentar escribir algo para activar el dropdown
                        ComponenteInteraccion.escribirComponente(
                            page, selector_autocomplete, "", descripcion="activar dropdown empresas")
                
                esperarConLoaderSimple(2, "Esperando carga de opciones de empresas")

                # Múltiples selectores alternativos para las opciones del dropdown
                selectores_opciones = [
                    "//ul[contains(@class, 'p-autocomplete-items')]//li[contains(@class, 'p-autocomplete-item')]",
                    "//ul[contains(@class, 'p-autocomplete-panel')]//li",
                    "//div[contains(@class, 'p-autocomplete-panel')]//li",
                    "//ul[@role='listbox']//li[@role='option']",
                    "//li[contains(@class, 'p-autocomplete-item')]",
                ]
                
                opciones = []
                selector_opciones_usado = None
                
                # Intentar obtener opciones con diferentes selectores
                for selector_opciones in selectores_opciones:
                    try:
                        opciones_locator = page.locator(selector_opciones)
                        count = opciones_locator.count()
                        if count > 0:
                            opciones = opciones_locator.all()
                            selector_opciones_usado = selector_opciones
                            LogManager.escribir_log("SUCCESS", f"Opciones encontradas con selector: {selector_opciones} ({count} opciones)")
                            break
                    except Exception as e:
                        LogManager.escribir_log("DEBUG", f"Selector {selector_opciones} no funcionó: {str(e)}")
                        continue

                if not opciones:
                    LogManager.escribir_log(
                        "WARNING", "No se encontraron opciones de empresa con ningún selector")
                    # Intentar hacer clic de nuevo en el selector
                    ComponenteInteraccion.clickComponente(
                        page, selector_autocomplete, descripcion="reabrir dropdown empresas", intentos=1, timeout=2000)
                    esperarConLoaderSimple(2, "Esperando carga de opciones después de reabrir")
                    
                    # Reintentar con el primer selector
                    try:
                        opciones = page.locator(selectores_opciones[0]).all()
                        if opciones:
                            LogManager.escribir_log("SUCCESS", f"Opciones encontradas después de reabrir ({len(opciones)} opciones)")
                    except:
                        pass
                    
                    if not opciones:
                        intentos_globales += 1
                        continue

                # Lista de empresas objetivo en orden de prioridad
                empresas_objetivo = ["MAXXIMUNDO", "AUTOLLANTA"]
                empresas_disponibles = []

                # Crear lista de empresas disponibles con sus elementos
                for opcion in opciones:
                    try:
                        # Intentar obtener el texto de diferentes formas
                        texto = None
                        try:
                            texto = opcion.locator("span").text_content().strip()
                        except:
                            try:
                                texto = opcion.text_content().strip()
                            except:
                                try:
                                    texto = opcion.inner_text().strip()
                                except:
                                    texto = ""
                        
                        if texto:
                            empresas_disponibles.append(
                                {"nombre": texto, "elemento": opcion})
                            LogManager.escribir_log("DEBUG", f"Empresa encontrada: {texto}")
                    except Exception as e:
                        LogManager.escribir_log("WARNING", f"Error extrayendo texto de opción: {str(e)}")
                        continue
                
                total_empresas = len(empresas_disponibles)
                LogManager.escribir_log(
                    "INFO", f"Se encontraron {total_empresas} empresas disponibles para procesar")
                
                if not empresas_disponibles:
                    LogManager.escribir_log(
                        "WARNING", "No se pudieron extraer nombres de empresas de las opciones")
                    intentos_globales += 1
                    continue

                # Procesar empresas por prioridad
                for empresa_objetivo in empresas_objetivo:
                    LogManager.escribir_log(
                        "INFO", f"=== BUSCANDO EMPRESA: {empresa_objetivo} ===")

                    # Si ya fue procesada, saltarla
                    if empresa_objetivo in nombres_empresas_procesadas:
                        LogManager.escribir_log(
                            "INFO", f"Empresa {empresa_objetivo} ya procesada, saltando...")
                        continue

                    empresa_seleccionada = False

                    # Buscar empresa específica
                    for empresa_data in empresas_disponibles:
                        texto = empresa_data["nombre"]
                        elemento = empresa_data["elemento"]

                        if empresa_objetivo.upper() in texto.upper():
                            LogManager.escribir_log(
                                "INFO", f"📍 Encontrada empresa: '{texto}'")
                            
                            # Asegurarse de que el dropdown esté abierto antes de seleccionar
                            dropdown_abierto = False
                            try:
                                # Verificar si el panel del dropdown está visible
                                panel_selector = "//div[contains(@class, 'p-autocomplete-panel')] | //ul[contains(@class, 'p-autocomplete-items')]"
                                panel_locator = page.locator(panel_selector).first
                                
                                if panel_locator.is_visible(timeout=2000):
                                    LogManager.escribir_log("INFO", "Panel dropdown visible")
                                    dropdown_abierto = True
                                else:
                                    LogManager.escribir_log("INFO", "Panel dropdown no visible, abriendo...")
                            except:
                                LogManager.escribir_log("INFO", "No se pudo verificar visibilidad del panel")
                            
                            if not dropdown_abierto:
                                # Intentar abrir el dropdown con el botón específico
                                try:
                                    # Buscar el botón cerca del input
                                    input_locator = page.locator(selector_autocomplete).first
                                    boton_dropdown_locator = input_locator.locator("..").locator("//button[contains(@class, 'p-autocomplete-dropdown')]").first
                                    
                                    if boton_dropdown_locator.is_visible(timeout=2000):
                                        boton_dropdown_locator.click(timeout=3000)
                                        esperarConLoaderSimple(1, "Esperando apertura de dropdown")
                                    else:
                                        # Si no funciona, intentar con el input
                                        ComponenteInteraccion.clickComponente(
                                            page, selector_autocomplete, descripcion="abrir dropdown empresas", intentos=1, timeout=2000)
                                        esperarConLoaderSimple(1, "Esperando apertura de dropdown")
                                except:
                                    # Si falla, intentar con el input directamente
                                    ComponenteInteraccion.clickComponente(
                                        page, selector_autocomplete, descripcion="abrir dropdown empresas", intentos=1, timeout=2000)
                                    esperarConLoaderSimple(1, "Esperando apertura de dropdown")

                            # Seleccionar empresa - Múltiples métodos
                            empresa_seleccionada_exito = False
                            
                            # Método 1: Clic directo en el elemento
                            try:
                                # Esperar a que el elemento sea visible y clickeable
                                elemento.wait_for(state="visible", timeout=3000)
                                if elemento.is_visible(timeout=2000):
                                    elemento.scroll_into_view_if_needed()
                                    elemento.click(timeout=5000)
                                    LogManager.escribir_log("SUCCESS", f"✅ Empresa seleccionada (método directo): '{texto}'")
                                    empresa_seleccionada_exito = True
                            except Exception as e:
                                LogManager.escribir_log("DEBUG", f"Error método directo: {str(e)}")
                            
                            # Método 2: Buscar por texto en el panel
                            if not empresa_seleccionada_exito:
                                try:
                                    # Buscar el elemento por texto dentro del panel
                                    selector_por_texto = f"//div[contains(@class, 'p-autocomplete-panel')]//li[contains(text(), '{texto}')] | //ul[contains(@class, 'p-autocomplete-items')]//li[contains(text(), '{texto}')]"
                                    elemento_por_texto = page.locator(selector_por_texto).first
                                    elemento_por_texto.wait_for(state="visible", timeout=3000)
                                    elemento_por_texto.scroll_into_view_if_needed()
                                    elemento_por_texto.click(timeout=5000)
                                    LogManager.escribir_log("SUCCESS", f"✅ Empresa seleccionada (método por texto): '{texto}'")
                                    empresa_seleccionada_exito = True
                                except Exception as e:
                                    LogManager.escribir_log("DEBUG", f"Error método por texto: {str(e)}")
                            
                            # Método 3: Usar JavaScript para hacer clic
                            if not empresa_seleccionada_exito:
                                try:
                                    # Obtener el elemento usando JavaScript
                                    script = f"""
                                    var items = document.querySelectorAll('li.p-autocomplete-item, li[role="option"]');
                                    for (var i = 0; i < items.length; i++) {{
                                        if (items[i].textContent.trim().includes('{texto}')) {{
                                            items[i].click();
                                            return true;
                                        }}
                                    }}
                                    return false;
                                    """
                                    resultado = page.evaluate(script)
                                    if resultado:
                                        LogManager.escribir_log("SUCCESS", f"✅ Empresa seleccionada (método JavaScript): '{texto}'")
                                        empresa_seleccionada_exito = True
                                except Exception as e:
                                    LogManager.escribir_log("DEBUG", f"Error método JavaScript: {str(e)}")
                            
                            if not empresa_seleccionada_exito:
                                LogManager.escribir_log("ERROR", f"No se pudo seleccionar empresa '{texto}' con ningún método")
                                continue
                            
                            # Esperar a que se procese la selección
                            esperarConLoaderSimple(2, f"Esperando procesamiento de selección de {texto}")
                            
                            # Verificar que la empresa se haya seleccionado correctamente
                            try:
                                # Esperar a que el input muestre el valor seleccionado o que el panel se cierre
                                page.wait_for_timeout(1000)
                                # Verificar si el panel se cerró (indicando que la selección fue exitosa)
                                panel_locator = page.locator("//div[contains(@class, 'p-autocomplete-panel')]").first
                                try:
                                    if not panel_locator.is_visible(timeout=1000):
                                        LogManager.escribir_log("SUCCESS", f"Panel cerrado, empresa '{texto}' seleccionada correctamente")
                                except:
                                    # Si no se puede verificar, asumir que está bien
                                    pass
                            except:
                                pass
                            
                            esperarConLoaderSimple(2, f"Procesando selección de {texto}")

                            # Procesar movimientos para esta empresa
                            if procesar_movimientos_empresa(page, id_ejecucion, texto):
                                nombres_empresas_procesadas.append(
                                    empresa_objetivo)
                                empresas_procesadas.append(
                                    len(empresas_procesadas))
                                LogManager.escribir_log(
                                    "SUCCESS", f"🎉 Empresa {texto} procesada exitosamente")
                            else:
                                LogManager.escribir_log(
                                    "WARNING", f"❌ No se pudieron procesar movimientos para {texto}")

                            empresa_seleccionada = True
                            break

                    if not empresa_seleccionada:
                        LogManager.escribir_log(
                            "WARNING", f"❌ No se encontró la empresa: {empresa_objetivo}")

                # Si procesamos todas las empresas objetivo, salir
                if len(nombres_empresas_procesadas) == len(empresas_objetivo):
                    LogManager.escribir_log(
                        "SUCCESS", f"🎉 Todas las empresas objetivo procesadas: {nombres_empresas_procesadas}")
                    return True

                # Si no procesamos ninguna empresa en este intento, incrementar intentos
                if len(empresas_procesadas) == 0:
                    intentos_globales += 1
                else:
                    # Si procesamos al menos una, considerar éxito
                    LogManager.escribir_log(
                        "SUCCESS", f"✅ Procesamiento parcial completado: {len(nombres_empresas_procesadas)} empresas")
                    return True

            except Exception as e:
                LogManager.escribir_log(
                    "ERROR", f"Error general procesando empresas (intento {intentos_globales+1}): {str(e)}")
                intentos_globales += 1
                esperarConLoaderSimple(5, "Esperando antes de reintentar")

        LogManager.escribir_log(
            "INFO", f"Procesamiento completado: {len(empresas_procesadas)} empresas exitosas")
        return len(empresas_procesadas) > 0

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error en procesar_todas_las_empresas: {str(e)}")
        return False


def procesar_archivo_excel(ruta_archivo, id_ejecucion, empresa):
    """Procesa el archivo Excel descargado usando la estructura del Banco Guayaquil"""
    try:
        LogManager.escribir_log(
            "INFO", f"Procesando archivo Excel: {ruta_archivo}")

        # Leer el archivo Excel usando componentes comunes
        contenido = LectorArchivos.leerExcel(ruta_archivo)
        if contenido is None:
            LogManager.escribir_log(
                "ERROR", f"No se pudo leer el archivo: {ruta_archivo}")
            return False

        # Validar que hay suficientes filas
        if len(contenido) < 15:
            LogManager.escribir_log(
                "WARNING", f"El archivo solo tiene {len(contenido)} filas, se esperaban al menos 15")
            return False

        # Extraer número de cuenta
        cuenta_raw = ""
        if len(contenido) > 6 and len(contenido[6]) > 0:
            cuenta_raw = str(contenido[6][0])
        cuenta = cuenta_raw.split(":")[1].strip(
        ) if ":" in cuenta_raw else cuenta_raw.strip()

        LogManager.escribir_log("INFO", f"Cuenta procesada: '{cuenta}'")

        if not cuenta:
            LogManager.escribir_log(
                "WARNING", "No se pudo extraer número de cuenta")
            cuenta = "SIN_CUENTA"

        # NUEVO: Obtener rango de fechas del archivo para la consulta previa
        LogManager.escribir_log(
            "INFO", "🔍 Analizando rango de fechas en el archivo...")
        fechas_archivo = []

        for i in range(14, len(contenido)):
            fila = contenido[i]
            if fila and len(fila) > 1 and fila[1]:
                fecha_str = str(fila[1])
                if fecha_str not in fechas_archivo:
                    fechas_archivo.append(fecha_str)

        if not fechas_archivo:
            LogManager.escribir_log(
                "WARNING", "No se encontraron fechas válidas en el archivo")
            return False

        # Determinar rango de fechas (del más antiguo al más reciente)
        fecha_min = min(fechas_archivo)
        fecha_max = max(fechas_archivo)
        LogManager.escribir_log(
            "INFO", f"📅 Rango de fechas en archivo: {fecha_min} a {fecha_max}")

        # PASO 1: Consultar registros existentes en la BD para este rango de fechas
        LogManager.escribir_log(
            "INFO", "🔎 Consultando registros existentes en la base de datos...")

        sql_existentes = f"""
            SELECT 
                numDocumento, 
                fechaTransaccion, 
                valor, 
                tipo
            FROM {DATABASE} 
            WHERE numCuenta = '{cuenta}' 
            AND banco = 'Banco Guayaquil' 
            AND empresa = '{empresa}' 
            AND fechaTransaccion BETWEEN '{fecha_min}' AND '{fecha_max}'
        """

        registros_existentes = BaseDatos.consultarBD(sql_existentes)

        # CAMBIO CLAVE: Crear set de combinaciones únicas YA EXISTENTES (sin considerar sufijos)
        combinaciones_existentes = set()
        documentos_existentes_en_bd = set()

        if registros_existentes:
            for registro in registros_existentes:
                doc_completo = registro[0]  # numDocumento (puede tener sufijo)
                fecha = registro[1]
                valor = registro[2]
                tipo = registro[3]

                # Extraer documento original (sin sufijo) usando Python
                if " - " in doc_completo:
                    doc_original = doc_completo.split(" - ")[0]
                else:
                    doc_original = doc_completo

                # Crear clave con documento original
                key_original = f"{doc_original}|{fecha}|{valor}|{tipo}"
                combinaciones_existentes.add(key_original)

                # Mantener documento completo para manejo de sufijos
                documentos_existentes_en_bd.add(doc_completo)

                # DEBUG para los primeros registros
                if len(combinaciones_existentes) <= 5:
                    LogManager.escribir_log(
                        "DEBUG", f"Registro BD: Doc='{doc_completo}' → Original='{doc_original}' → Key='{key_original}'")

        LogManager.escribir_log(
            "INFO", f"📋 Se encontraron {len(combinaciones_existentes)} combinaciones únicas existentes")
        LogManager.escribir_log(
            "INFO", f"📋 Se encontraron {len(documentos_existentes_en_bd)} documentos totales con sufijos")

        # PASO 2: Procesar el contenido del archivo Excel
        movimientos_insertados = 0
        movimientos_omitidos = 0
        filas_procesadas = 0
        # Para evitar duplicados en el mismo archivo
        documentos_procesados_en_memoria = set()
        # NUEVO: Para evitar duplicados en el mismo archivo
        combinaciones_procesadas_memoria = set()

        # La tabla comienza en la fila 15 (índice 14) según la estructura original
        for i in range(14, len(contenido)):
            fila = contenido[i]

            # Validaciones básicas
            if not fila or len(fila) < 2 or not fila[1]:
                continue

            try:
                filas_procesadas += 1

                # Extraer datos de cada columna
                fecha = fila[1] if len(fila) > 1 else ""  # Columna B
                tipo_raw = fila[13] if len(fila) > 0 else ""  # Columna D
                numero_documento_base = str(fila[4]) if len(
                    fila) > 4 else ""  # Columna E
                concepto_transaccion = str(fila[5]) if len(
                    fila) > 5 else ""  # Columna F
                oficina = str(fila[6]) if len(fila) > 6 else ""  # Columna G
                valor_raw = fila[7] if len(fila) > 7 else "0"  # Columna H
                saldo_raw = fila[9] if len(fila) > 9 else "0"  # Columna J
                referencia = str(fila[10]) if len(
                    fila) > 10 else ""  # Columna K

                # Procesar tipo (crédito/débito)
                tipo = "D" if "-" in str(tipo_raw).lower() else "C"

                # Procesar valores monetarios
                valor = str(valor_raw).replace("'", "").replace(
                    "$", "").replace(",", "").strip()
                saldo_contable = str(saldo_raw).replace(
                    "'", "").replace("$", "").replace(",", "").strip()

                # Validar que los valores sean numéricos
                try:
                    valor_float = float(
                        valor) if valor and valor != "" else 0.0
                    saldo_float = float(
                        saldo_contable) if saldo_contable and saldo_contable != "" else 0.0
                except ValueError as ve:
                    LogManager.escribir_log(
                        "WARNING", f"Error convirtiendo valores en fila {i}: valor='{valor}', saldo='{saldo_contable}' - {str(ve)}")
                    valor_float = 0.0
                    saldo_float = 0.0

                # Validar datos mínimos requeridos
                if not fecha or not numero_documento_base:
                    LogManager.escribir_log(
                        "WARNING", f"Fila {i}: Datos insuficientes - fecha: '{fecha}', documento: '{numero_documento_base}'")
                    continue

                # NUEVA VALIDACIÓN CORRECTA: Verificar si la COMBINACIÓN ÚNICA ya existe
                key_combinacion_original = f"{numero_documento_base}|{fecha}|{valor_float}|{tipo}"

                # PRIMERA VERIFICACIÓN: ¿Esta combinación exacta ya existe en BD?
                if key_combinacion_original in combinaciones_existentes:
                    movimientos_omitidos += 1
                    if movimientos_omitidos <= 10:
                        LogManager.escribir_log(
                            "INFO", f"⏭️ Omitiendo registro EXISTENTE: Doc={numero_documento_base}, Fecha={fecha}, Valor=${valor_float}")
                    continue

                # SEGUNDA VERIFICACIÓN: ¿Ya procesé esta combinación en este archivo?
                if key_combinacion_original in combinaciones_procesadas_memoria:
                    movimientos_omitidos += 1
                    if movimientos_omitidos <= 5:
                        LogManager.escribir_log(
                            "INFO", f"⏭️ Omitiendo registro DUPLICADO en archivo: Doc={numero_documento_base}, Fecha={fecha}, Valor=${valor_float}")
                    continue

                # Si llegamos aquí, es un registro NUEVO que debe insertarse

                # LÓGICA DE SUFIJOS: Similar a Banco Pichincha
                def existe_num_documento_bd(doc_numero):
                    """Verifica si un número de documento existe en BD"""
                    return doc_numero in documentos_existentes_en_bd

                def existe_en_memoria(doc_numero):
                    """Verifica si el documento ya está en memoria"""
                    return doc_numero in documentos_procesados_en_memoria

                # Determinar número de documento final con sufijo si es necesario
                sufijo = 0
                numero_documento_final = numero_documento_base

                # SOLO aplicar sufijos si el NÚMERO DE DOCUMENTO (independientemente de fecha/valor) ya existe
                while (existe_num_documento_bd(numero_documento_final) or
                       existe_en_memoria(numero_documento_final)):
                    sufijo += 1
                    numero_documento_final = f"{numero_documento_base} - {sufijo}"

                # Registrar en memoria para evitar duplicados en el mismo archivo
                documentos_procesados_en_memoria.add(numero_documento_final)
                combinaciones_procesadas_memoria.add(key_combinacion_original)

                # Log de sufijo aplicado
                if sufijo > 0:
                    LogManager.escribir_log(
                        "INFO", f"📝 Sufijo aplicado: '{numero_documento_base}' → '{numero_documento_final}' (nuevo registro con documento existente)")

                # Obtener contador de fecha
                sql_contador = f"""
                    SELECT COALESCE(MAX(contFecha), 0) + 1 AS maxCont 
                    FROM {DATABASE} 
                    WHERE numCuenta = '{cuenta}' 
                    AND banco = 'Banco Guayaquil' 
                    AND empresa = '{empresa}' 
                    AND fechaTransaccion = '{fecha}'
                """

                resultado_contador = BaseDatos.consultarBD(sql_contador)
                contFecha = resultado_contador[0][0] if resultado_contador and resultado_contador[0] else 1

                # Limpiar valores para SQL
                concepto_limpio = concepto_transaccion.replace("'", "''")
                referencia_limpia = referencia.replace("'", "''")
                oficina_limpia = oficina.replace("'", "''")
                numero_documento_limpio = numero_documento_final.replace(
                    "'", "''")

                # Preparar SQL de inserción
                sql_insercion = f"""
                    INSERT INTO {DATABASE} (
                        numCuenta, banco, empresa, numDocumento, idEjecucion, 
                        fechaTransaccion, tipo, valor, saldoContable, referencia, 
                        contFecha, conceptoTransaccion, oficina
                    ) VALUES (
                        '{cuenta}', 
                        'Banco Guayaquil', 
                        '{empresa}', 
                        '{numero_documento_limpio}', 
                        {id_ejecucion}, 
                        '{fecha}', 
                        '{tipo}', 
                        {valor_float}, 
                        {saldo_float}, 
                        '{referencia_limpia}', 
                        {contFecha}, 
                        '{concepto_limpio}', 
                        '{oficina_limpia}'
                    )
                """

                # Insertar en BD
                if BaseDatos.ejecutarSQL(sql_insercion):
                    movimientos_insertados += 1

                    # IMPORTANTE: Actualizar estructuras en memoria
                    documentos_existentes_en_bd.add(numero_documento_final)
                    combinaciones_existentes.add(key_combinacion_original)

                else:
                    LogManager.escribir_log(
                        "ERROR", f"❌ Falla insertando fila {i}")

            except Exception as e:
                LogManager.escribir_log(
                    "WARNING", f"Error procesando fila {i}: {str(e)}")
                continue

        # Resumen final detallado
        LogManager.escribir_log("INFO", f"=== RESUMEN PROCESAMIENTO ===")
        LogManager.escribir_log("INFO", f"🏢 Empresa: {empresa}")
        LogManager.escribir_log("INFO", f"💳 Cuenta: {cuenta}")
        LogManager.escribir_log(
            "INFO", f"📊 Total filas procesadas: {filas_procesadas}")
        LogManager.escribir_log(
            "INFO", f"✅ Registros nuevos insertados: {movimientos_insertados}")
        LogManager.escribir_log(
            "INFO", f"⏭️ Registros omitidos (existentes/duplicados): {movimientos_omitidos}")
        LogManager.escribir_log(
            "INFO", f"📅 Rango de fechas: {fecha_min} a {fecha_max}")
        LogManager.escribir_log(
            "INFO", f"📝 Documentos únicos procesados: {len(documentos_procesados_en_memoria)}")
        LogManager.escribir_log(
            "INFO", f"🔑 Combinaciones únicas procesadas: {len(combinaciones_procesadas_memoria)}")

        # CAMBIO PRINCIPAL: Considerar éxito tanto si hay nuevos como si no hay
        if movimientos_insertados > 0:
            LogManager.escribir_log(
                "SUCCESS", f"✅ Procesamiento exitoso: {movimientos_insertados} nuevos movimientos para {empresa}")
        else:
            LogManager.escribir_log(
                "SUCCESS", f"✅ Procesamiento exitoso: No se encontraron registros nuevos para {empresa} (todos ya existen)")

        # Eliminar archivo después de procesarlo
        try:
            os.remove(ruta_archivo)
            LogManager.escribir_log(
                "INFO", f"Archivo eliminado: {ruta_archivo}")
        except Exception as e:
            LogManager.escribir_log(
                "WARNING", f"No se pudo eliminar archivo: {str(e)}")

        return True

    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error procesando Excel: {str(e)}")
        return False


def obtener_contador_fecha(cuenta, empresa, fecha):
    """Obtiene el siguiente contador de fecha para evitar duplicados"""
    try:
        sql = f"""
            SELECT COALESCE(MAX(contFecha), 0) + 1 AS maxCont 
            FROM {DATABASE} 
            WHERE numCuenta = '{cuenta}' 
            AND banco = 'Banco Guayaquil' 
            AND empresa = '{empresa}' 
            AND fechaTransaccion = '{fecha}'
        """
        resultado = BaseDatos.consultarBD(sql)
        return resultado[0][0] if resultado and resultado[0] else 1
    except Exception as e:
        LogManager.escribir_log(
            "WARNING", f"Error obteniendo contador fecha: {str(e)}")
        return 1


def procesar_movimientos_empresa(page, id_ejecucion, nombre_empresa):
    """Procesa los movimientos de una empresa específica"""
    try:
        LogManager.escribir_log(
            "INFO", f"Procesando movimientos para empresa: {nombre_empresa}")

        # Las fechas ya vienen por defecto seleccionadas (últimos 7 días)
        # Solo necesitamos exportar los datos
        LogManager.escribir_log("INFO", "Las fechas ya están seleccionadas por defecto, iniciando exportación...")
        
        esperarConLoaderSimple(2, "Esperando carga de página de movimientos")

        # Exportar datos
        LogManager.escribir_log("INFO", "Iniciando exportación...")

        # Múltiples selectores para el botón Exportar
        selectores_boton_exportar = [
            "//button[.//span[contains(text(), 'Exportar')]]",
            "//button[.//span[@class='p-button-label' and contains(text(), 'Exportar')]]",
            "//app-cbanco-button//button[.//span[contains(text(), 'Exportar')]]",
            "//button[contains(@class, 'p-button') and .//span[contains(text(), 'Exportar')]]",
            "//button[contains(@class, 'cb-button') and .//span[contains(text(), 'Exportar')]]",
        ]
        
        boton_exportar_clickeado = False
        for selector_exportar in selectores_boton_exportar:
            try:
                LogManager.escribir_log("INFO", f"Buscando botón 'Exportar' con selector: {selector_exportar}")
                if ComponenteInteraccion.esperarElemento(page, selector_exportar, timeout=5000, descripcion="botón exportar"):
                    if ComponenteInteraccion.clickComponente(
                        page, selector_exportar, descripcion="botón exportar", intentos=2, timeout=5000):
                        LogManager.escribir_log("SUCCESS", f"Botón 'Exportar' clickeado exitosamente")
                        boton_exportar_clickeado = True
                        break
            except Exception as e:
                LogManager.escribir_log("DEBUG", f"Selector {selector_exportar} no funcionó: {str(e)}")
                continue
        
        if not boton_exportar_clickeado:
            LogManager.escribir_log("ERROR", "No se pudo hacer clic en el botón 'Exportar'")
            return False

        esperarConLoaderSimple(1, "Esperando modal de descarga")

        # Paso 3: Descargar archivo
        LogManager.escribir_log("INFO", "Descargando archivo...")

        ruta_archivo = ComponenteInteraccion.esperarDescarga(
            page,
            "//button[.//span[contains(text(), 'Descargar')]]",
            timeout=30000,
            descripcion="botón descargar movimientos"
        )

        if not ruta_archivo:
            LogManager.escribir_log(
                "ERROR", f"No se pudo descargar archivo para {nombre_empresa}")
            return False

        # Paso 4: Procesar archivo descargado
        if procesar_archivo_excel(ruta_archivo, id_ejecucion, nombre_empresa):
            LogManager.escribir_log(
                "SUCCESS", f"Movimientos de {nombre_empresa} procesados exitosamente")
            return True
        else:
            LogManager.escribir_log(
                "ERROR", f"Error procesando archivo de {nombre_empresa}")
            return False

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error procesando movimientos de {nombre_empresa}: {str(e)}")
        return False

# ==================== FUNCIONES AUXILIARES ====================


def convertir_fecha_sql(fecha_str):
    """Convierte string de fecha a formato SQL Server"""
    try:
        if not fecha_str:
            return None

        # Intentar diferentes formatos de fecha
        formatos = ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y']

        for formato in formatos:
            try:
                fecha_obj = datetime.strptime(fecha_str, formato)
                return fecha_obj.strftime('%Y-%m-%d')
            except ValueError:
                continue

        LogManager.escribir_log(
            "WARNING", f"No se pudo convertir fecha: {fecha_str}")
        return None

    except Exception as e:
        LogManager.escribir_log(
            "WARNING", f"Error convirtiendo fecha {fecha_str}: {str(e)}")
        return None


def limpiar_valor_monetario(valor_str):
    """Limpia y convierte valores monetarios a float"""
    try:
        if not valor_str:
            return 0.0

        # Limpiar caracteres no numéricos excepto punto y coma
        valor_limpio = str(valor_str).replace(
            '$', '').replace(',', '').replace(' ', '').strip()

        # Manejar valores negativos entre paréntesis
        if valor_limpio.startswith('(') and valor_limpio.endswith(')'):
            valor_limpio = '-' + valor_limpio[1:-1]

        return float(valor_limpio) if valor_limpio and valor_limpio != '-' else 0.0

    except (ValueError, TypeError):
        return 0.0


def esperar_carga_completa_pagina(page):
    """Espera que la página cargue completamente"""
    try:
        EsperasInteligentes.esperar_carga_pagina(page)
        esperarConLoaderSimple(2, "Esperando carga completa")
        return True
    except Exception as e:
        LogManager.escribir_log(
            "WARNING", f"Timeout esperando carga: {str(e)}")
        return False

# ==================== FUNCIÓN PRINCIPAL ====================


@with_timeout_check
def main():
    """Función principal de automatización Banco Guayaquil"""
    playwright = None
    browser = None
    context = None
    page = None
    id_ejecucion = None

    try:
        # Obtener ID de ejecución
        id_ejecucion = obtenerIDEjecucion()
        
        # Guardar timestamp de inicio del programa (para buscar correos desde este momento)
        timestamp_inicio_programa = datetime.now(timezone.utc)
        LogManager.escribir_log("INFO", f"Timestamp de inicio del programa: {timestamp_inicio_programa.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        
        LogManager.iniciar_proceso(NOMBRE_BANCO, id_ejecucion, f"Automatización Banco Guayaquil - ID: {id_ejecucion}")
        # Iniciar timeout manager
        timeout_manager.start()

        # Registrar inicio de ejecución
        sql_inicio = f"""
            INSERT INTO {DATABASE_RUNS} (idAutomationRun, processName, startDate, finalizationStatus) VALUES ({id_ejecucion}, 'Descarga comprobantes-Banco Guayaquil', SYSDATETIME(), 'Running')
        """
        datosEjecucion(sql_inicio)
        escribirLog("Proceso iniciado", id_ejecucion, "Information", "Inicio")

        # Inicializar Playwright
        LogManager.escribir_log("INFO", "Inicializando navegador...")
        manager = PlaywrightManager(
            headless=False, download_path=RUTAS_CONFIG['descargas'])
        playwright, browser, context, page = manager.iniciar_navegador()

        # Realizar login (pasar timestamp de inicio del programa)
        if not realizar_login_completo(page, timestamp_inicio=timestamp_inicio_programa):
            raise Exception("Login falló")
        escribirLog("Login exitoso", id_ejecucion, "Success", "Login")

        # Navegar a movimientos
        if not navegar_a_movimientos(page):
            raise Exception("Navegación a movimientos falló")
        escribirLog("Navegación exitosa", id_ejecucion,
                    "Success", "Navegación")

        # Obtener y procesar movimientos
        if not obtener_y_procesar_movimientos(page, id_ejecucion):
            raise Exception("Procesamiento de movimientos falló")
        escribirLog("Movimientos procesados exitosamente",
                    id_ejecucion, "Success", "Procesamiento")

        # Registrar éxito
        sql_fin = f"""
            UPDATE {DATABASE_RUNS} 
            SET endDate = GETDATE(), finalizationStatus = 'Completado'
            WHERE idAutomationRun = {id_ejecucion}
        """
        datosEjecucion(sql_fin)
        escribirLog("Proceso completado exitosamente",
                    id_ejecucion, "Success", "Fin")

        # Ejecutar BAT para subir moviemientos al portal
        LogManager.escribir_log("INFO", "🔧 Ejecutando proceso final...")
        SubprocesoManager.ejecutar_bat_final()

        LogManager.finalizar_proceso(
            NOMBRE_BANCO, True, "Automatización completada exitosamente")
        return True

    except Exception as e:
        error_msg = f"Error en proceso principal: {str(e)}"
        LogManager.escribir_log("ERROR", error_msg)

        if id_ejecucion:
            sql_error = f"""
                UPDATE {DATABASE_RUNS} 
                SET endDate = GETDATE(), finalizationStatus = 'Error'
                WHERE idAutomationRun = {id_ejecucion}
            """
            datosEjecucion(sql_error)
            escribirLog(error_msg, id_ejecucion, "Error", "Error General")

            # Ejecutar BAT para subir moviemientos al portal
            LogManager.escribir_log("INFO", "🔧 Ejecutando proceso final...")
            SubprocesoManager.ejecutar_bat_final()

        LogManager.finalizar_proceso(NOMBRE_BANCO, False, error_msg)
        return False

    finally:
        # Limpiar recursos de forma segura
        try:
            timeout_manager.stop()
        except Exception as e:
            LogManager.escribir_log(
                "WARNING", f"Error deteniendo timeout manager: {str(e)}")
        
        # Cerrar context de forma segura (antes del browser)
        try:
            if context:
                try:
                    if hasattr(context, 'close'):
                        context.close()
                        LogManager.escribir_log("INFO", "Context cerrado exitosamente")
                except Exception as e:
                    LogManager.escribir_log(
                        "WARNING", f"Context ya estaba cerrado: {str(e)}")
        except Exception as e:
            LogManager.escribir_log(
                "WARNING", f"Error cerrando context: {str(e)}")
        
        # Cerrar browser de forma segura
        try:
            if browser:
                # Verificar si el browser aún está conectado antes de cerrar
                try:
                    if hasattr(browser, 'is_connected') and browser.is_connected():
                        browser.close()
                        LogManager.escribir_log("INFO", "Browser cerrado exitosamente")
                except Exception as e:
                    LogManager.escribir_log(
                        "WARNING", f"Browser ya estaba cerrado o desconectado: {str(e)}")
        except Exception as e:
            LogManager.escribir_log(
                "WARNING", f"Error cerrando browser: {str(e)}")
        
        # Cerrar playwright de forma segura
        try:
            if playwright:
                playwright.stop()
                LogManager.escribir_log("INFO", "Playwright detenido exitosamente")
        except Exception as e:
            LogManager.escribir_log(
                "WARNING", f"Error deteniendo playwright: {str(e)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        LogManager.escribir_log("WARNING", "Proceso interrumpido por usuario")
    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error no controlado: {str(e)}")
    finally:
        LogManager.escribir_log("INFO", "Finalizando aplicación")
