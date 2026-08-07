# -*- coding: utf-8 -*-
"""
COOPERATIVA JEP - AUTOMATIZACIÓN COMPLETA OPTIMIZADA
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
    RUTAS_CONFIG,
    CorreoManager,
    ConfiguracionManager,
    SubprocesoManager,
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
# source /home/administrador/Escritorio/venv/bin/activate
# ejecucion manual python CooperativaJEP_Final.py --manual

# DATABASE = "RegistrosBancosPRUEBA"
# DATABASE_LOGS = "AutomationLogPRUEBA"
# DATABASE_RUNS = "AutomationRunPRUEBA"
DATABASE = "RegistrosBancos"
DATABASE_LOGS = "AutomationLog"
DATABASE_RUNS = "AutomationRun"
NOMBRE_BANCO = "Cooperativa JEP"

NUM_CUENTA_TECNICENTRO = "406102270900"

URLS = {
    'login': "https://jepvirtual.jep.coop/empresas/signinEmpresas.jsf",
}

# Configuración específica de JEP
CONFIG_JEP = {
    'celda_inicio_datos': "A8",
    'celda_final_datos': "G",
    'celda_empresa': "A5",
    'celda_cuenta': "A4",
    'banco_codigo': "JEP",
    'prefijo_tecnicentro': "TECNICENTRO // ",
    'tiempo_espera_descarga': 15
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

# ==================== FUNCIONES DE OTP PARA JEP ====================

def ingresar_codigo_teclado_virtual(page, codigo):
    """Ingresa el código usando el teclado virtual de JEP"""
    try:
        LogManager.escribir_log(
            "INFO", f"Ingresando código en teclado virtual: {codigo}")

        # Esperar a que aparezca el teclado virtual
        ComponenteInteraccion.esperarElemento(
            page,
            "//div[@id='idTecladoPrincipal']",
            timeout=10000,
            descripcion="teclado virtual"
        )

        # Limpiar cualquier entrada previa
        ComponenteInteraccion.clickComponenteOpcional(
            page,
            "//button[contains(text(), 'LIMPIAR')]",
            descripcion="botón limpiar",
            intentos=1,
            timeout=2000
        )

        esperarConLoaderSimple(1, "Esperando después de limpiar")

        # Hacer clic en cada dígito del código
        for i, digito in enumerate(codigo):

            # Buscar el botón que contiene este dígito
            selector_boton = f"//div[@id='idTecladoPrincipal']//button[contains(@class, 'JPEVirtual-loginotp-teclado-tecla') and text()='{digito}']"

            if not click_con_habilitacion(page, selector_boton, f"dígito {digito}"):
                LogManager.escribir_log(
                    "ERROR", f"No se pudo hacer clic en el dígito {digito}")
                return False

        LogManager.escribir_log(
            "SUCCESS", "Código ingresado completamente en teclado virtual")

        ComponenteInteraccion.clickComponente(
            page,
            "//button[.//span[contains(text(), 'ACCEDER')]]",
            descripcion="botón acceder",
            intentos=3,
            timeout=2000
        )

        # Esperar a que se procese el código
        esperarConLoaderSimple(2, "Esperando procesamiento del código")

        return True

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error ingresando código en teclado virtual: {str(e)}")
        return False


def manejar_codigo_seguridad_jep(page, timestamp_inicio_login):
    """Maneja todo el proceso de obtención e ingreso del código de seguridad para JEP"""
    try:
        LogManager.escribir_log(
            "INFO", "Iniciando proceso de código de seguridad JEP")

        # Verificar si aparece el teclado virtual (indicativo de que se requiere código)
        if not ComponenteInteraccion.esperarElemento(
            page,
            "//div[@id='idTecladoPrincipal']",
            timeout=5000,
            descripcion="teclado virtual"
        ):
            LogManager.escribir_log(
                "INFO", "No se requiere código de seguridad")
            return True
        
        # Usar el timestamp de inicio de login (pasado como parámetro)
        LogManager.escribir_log(
            "INFO", f"Usando timestamp de inicio de login: {timestamp_inicio_login.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        
        # Obtener código del correo usando asunto sin caracteres especiales para evitar problemas de encoding
        # Intentar primero con asunto sin acentos, luego con el original
        codigo = None
        asuntos_intento = [
            "Código de Seguridad",  # Con acento (original)
            "Codigo de Seguridad",  # Sin acento para evitar problemas de encoding
        ]
        
        for asunto_intento in asuntos_intento:
            try:
                LogManager.escribir_log(
                    "INFO", f"Buscando código con asunto: '{asunto_intento}'")
                codigo = CorreoManager.obtener_codigo_correo(
                    asunto=asunto_intento,
                    intentos=30,  # Reducir a 30 segundos en lugar de 60
                    espera=1,
                    timestamp_inicio=timestamp_inicio_login  # Pasar el timestamp de inicio de login para todas las búsquedas
                )
                if codigo:
                    break
            except Exception as e:
                LogManager.escribir_log(
                    "DEBUG", f"Error con asunto '{asunto_intento}': {str(e)}")
                continue

        if not codigo:
            LogManager.escribir_log(
                "ERROR", "No se pudo obtener el código de seguridad del correo")
            return False

        if not re.fullmatch(r"^\d{6}$", codigo):
            LogManager.escribir_log(
                "ERROR", f"Código recibido no es válido (debe ser 6 dígitos): {codigo}")
            return False

        LogManager.escribir_log(
            "SUCCESS", f"Código JEP válido recibido: {codigo}")

        # Ingresar código en teclado virtual
        if not ingresar_codigo_teclado_virtual(page, codigo):
            LogManager.escribir_log(
                "ERROR", "Error al ingresar el código JEP en el teclado virtual")
            return False

        LogManager.escribir_log(
            "SUCCESS", "Código JEP aceptado correctamente")

        # Esperar a que se complete la autenticación
        esperarConLoaderSimple(3, "Esperando autenticación completa")

        return True

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error en manejo de código de seguridad JEP: {str(e)}")
        return False

# ==================== FUNCIONES DE NAVEGACIÓN ====================

def cerrar_modal_cookies(page):
    """Cierra el modal de cookies que aparece al cargar la página"""
    try:
        LogManager.escribir_log("INFO", "Buscando modal de cookies...")
        
        # Esperar un momento para que aparezca el modal
        esperarConLoaderSimple(2, "Esperando aparición del modal de cookies")
        
        # Múltiples selectores para el botón "Aceptar" del modal de cookies
        selectores_boton_aceptar = [
            "//div[@id='cookieDialog']//button[contains(@class, 'btn-cancel') and contains(text(), 'Aceptar')]",
            "//div[@class='jep-politica-privacidad']//button[contains(@class, 'btn-cancel')]",
            "//div[@id='cookieDialog']//button[contains(@onclick, 'acceptCookies')]",
            "//div[@class='modal modalCookies']//button[contains(text(), 'Aceptar')]",
            "//button[@onclick='acceptCookies()']",
            "//div[@class='botonescookies']//button[contains(text(), 'Aceptar')]",
        ]
        
        boton_clickeado = False
        for selector_boton in selectores_boton_aceptar:
            try:
                LogManager.escribir_log("INFO", f"Buscando botón 'Aceptar' cookies con selector: {selector_boton}")
                if ComponenteInteraccion.esperarElemento(page, selector_boton, timeout=5000, descripcion="botón Aceptar cookies"):
                    if ComponenteInteraccion.clickComponente(
                        page, selector_boton, descripcion="botón Aceptar cookies", intentos=2, timeout=3000):
                        LogManager.escribir_log("SUCCESS", f"✅ Botón 'Aceptar' cookies clickeado exitosamente")
                        boton_clickeado = True
                        esperarConLoaderSimple(1, "Esperando cierre del modal de cookies")
                        break
            except Exception as e:
                LogManager.escribir_log("DEBUG", f"Selector {selector_boton} no funcionó: {str(e)}")
                continue
        
        if not boton_clickeado:
            LogManager.escribir_log("INFO", "No se encontró el modal de cookies, puede que ya esté cerrado o no apareció")
        
        return True
        
    except Exception as e:
        LogManager.escribir_log("WARNING", f"Error cerrando modal de cookies: {str(e)}")
        # Continuar de todas formas
        return True


@with_timeout_check
def navegar_a_login(page):
    """Navega a la página de login de JEP"""
    try:
        LogManager.escribir_log("INFO", f"Navegando a: {URLS['login']}")
        LogManager.escribir_log("INFO", "La página puede tardar hasta 85 segundos en cargar, esperando...")
        
        # Aumentar timeout para navegación (100 segundos para dar margen)
        page.goto(URLS['login'], timeout=200000, wait_until="domcontentloaded")
        LogManager.escribir_log("INFO", "Navegación inicial completada, esperando carga completa...")
        
        # Esperar a que la página cargue completamente (la página tarda ~85 segundos)
        try:
            # Esperar domcontentloaded con timeout largo
            page.wait_for_load_state("domcontentloaded", timeout=150000)
            LogManager.escribir_log("SUCCESS", "Página cargada (domcontentloaded)")
        except Exception as e:
            LogManager.escribir_log("WARNING", f"Timeout esperando domcontentloaded, continuando: {str(e)}")
        
        # Esperar networkidle con timeout suficiente (puede tardar más después de domcontentloaded)
        try:
            page.wait_for_load_state("networkidle", timeout=60000)
            LogManager.escribir_log("SUCCESS", "Página cargada completamente (networkidle)")
        except Exception as e:
            LogManager.escribir_log("WARNING", f"Timeout esperando networkidle, continuando: {str(e)}")
        
        esperarConLoaderSimple(3, "Esperando carga completa de la página")

        # PASO 1: Cerrar el modal de cookies si aparece
        cerrar_modal_cookies(page)
        
        esperarConLoaderSimple(1, "Esperando después de cerrar modal de cookies")

        return True

    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error navegando a login: {str(e)}")
        return False


@with_timeout_check
def iniciar_sesion(page, usuario, password):
    """Inicia sesión en la plataforma de JEP"""
    try:
        # Guardar timestamp de inicio del proceso de login (antes de cualquier operación)
        from datetime import datetime, timezone
        timestamp_inicio_login = datetime.now(timezone.utc)
        LogManager.escribir_log(
            "INFO", f"Iniciando sesión para usuario: {usuario}")
        LogManager.escribir_log(
            "INFO", f"Timestamp de inicio de login: {timestamp_inicio_login.strftime('%Y-%m-%d %H:%M:%S')} UTC")

        login_button = "//button[.//span[contains(text(),'ACCEDER')]]"
        ComponenteInteraccion.esperarElemento(
            page, login_button, timeout=10000, descripcion="botón de login")

        # Función auxiliar para realizar el login
        def realizar_login():
            escribir_con_habilitacion(
                page, "//input[@id='username1']", usuario, "campo usuario")
            escribir_con_habilitacion(
                page, "//input[@id='password1']", password, "campo password")
            esperarConLoaderSimple(1, "Esperando escritura de credenciales")

            login_button = "//button[.//span[contains(text(),'ACCEDER')]]"
            click_con_habilitacion(page, login_button, "botón login")
            esperarConLoaderSimple(2, "Esperando respuesta del login")

        # Realizar el primer intento de login
        realizar_login()

        # while para manejar sesión activa previa
        while True:
            # Verificar si hay sesión activa previa
            if manejar_sesion_activa(page, login_button):
                LogManager.escribir_log(
                    "INFO", "Sesión activa previa detectada, reingresando credenciales")

                # Reingresar credenciales
                realizar_login()
            else:
                break

        # Código de seguridad
        if not manejar_codigo_seguridad_jep(page, timestamp_inicio_login):
            LogManager.escribir_log(
                "ERROR", "Falló la validación del código de seguridad")
            return False

        # Esperar a que cargue la tabla de cuentas (en lugar de ui-datatable genérico)
        ComponenteInteraccion.esperarElemento(
            page, "//tbody[contains(@id, 'tablaDatosConsolAhorros_data')]", timeout=30000, descripcion="tabla de cuentas JEP")
        LogManager.escribir_log(
            "SUCCESS", f"Sesión iniciada correctamente para: {usuario}")
        return True

    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error al iniciar sesión: {str(e)}")
        return False


def manejar_sesion_activa(page, boton_espera):
    """Maneja el caso de sesión activa previa"""
    try:
        # Buscar botón de cerrar sesión activa
        cerrar_sesion_xpath = "//form/div[2]/a"
        if ComponenteInteraccion.clickComponenteOpcional(
            page,
            cerrar_sesion_xpath,
            "cerrar sesión activa",
            intentos=2,
            timeout=2000
        ):
            esperarConLoaderSimple(12, "Esperando cierre de sesión activa")

            # Esperar a que aparezca nuevamente el formulario de login
            if ComponenteInteraccion.esperarElemento(page, boton_espera, timeout=15000, descripcion="campo usuario después de cerrar sesión"):
                LogManager.escribir_log(
                    "INFO", "Sesión anterior cerrada, formulario de login disponible")
                esperarConLoaderSimple(2, "Esperando estabilización de página")
                return True
            else:
                LogManager.escribir_log(
                    "WARNING", "No apareció el formulario de login después de cerrar sesión")
                return False
        else:
            LogManager.escribir_log(
                "DEBUG", "No se detectó sesión activa previa")
            return False

    except Exception as e:
        LogManager.escribir_log(
            "DEBUG", f"No se detectó sesión activa previa: {str(e)}")

    return False

# ==================== FUNCIONES DE CONSULTA ====================


@with_timeout_check
def obtener_y_procesar_movimientos(page, id_ejecucion):
    """Obtiene y procesa los movimientos de todas las empresas disponibles"""
    try:
        LogManager.escribir_log(
            "INFO", "Iniciando obtención de movimientos...")

        # Procesar empresas
        return procesar_todas_las_empresas(page, id_ejecucion)

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error obteniendo movimientos: {str(e)}")
        return False


def procesar_todas_las_empresas(page, id_ejecucion):
    """Procesa todas las empresas disponibles"""
    try:
        LogManager.escribir_log(
            "INFO", "Iniciando procesamiento de empresas...")

        # Obtener cantidad de empresas disponibles
        cantidad_empresas = obtener_cantidad_empresas(page)
        if cantidad_empresas == 0:
            LogManager.escribir_log(
                "ERROR", "No se encontraron empresas disponibles")
            return False

        # Procesar cada empresa (primero la última, luego la primera)
        cuentas_exitosas = 0

        # Procesar última empresa
        if procesar_empresa_por_posicion(page, id_ejecucion, "ultima"):
            cuentas_exitosas += 1

        # Si hay más de una empresa, procesar la primera
        if cantidad_empresas > 1:
            if procesar_empresa_por_posicion(page, id_ejecucion, "primera"):
                cuentas_exitosas += 1

        LogManager.escribir_log(
            "SUCCESS", f"Procesamiento completado. {cuentas_exitosas} empresas exitosas de {min(cantidad_empresas, 2)} procesadas")
        return cuentas_exitosas > 0

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error procesando empresas: {str(e)}")
        return False


def obtener_cantidad_empresas(page):
    """Obtiene la cantidad de empresas disponibles"""
    try:
        # Usar el selector correcto para la tabla de cuentas
        filas = page.locator(
            "//tbody[contains(@id, 'tablaDatosConsolAhorros_data')]/tr").all()
        cantidad = len(filas)
        LogManager.escribir_log(
            "DEBUG", f"Cantidad de filas encontradas: {cantidad}")

        esperarConLoaderSimple(1, "Esperando estabilización de tabla")
        LogManager.escribir_log(
            "INFO", f"Se encontraron {cantidad} empresas disponibles")
        return cantidad
    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error al obtener cantidad de empresas: {str(e)}")
        return 0


def regresar_a_dashboard(page):
    """Regresa al dashboard principal donde están listadas las cuentas"""
    try:
        # Intentar diferentes selectores para regresar al dashboard
        selectores_regresar = [
            "//div/form/div[3]/div/div/button",  # Selector original
            "//button[contains(text(), 'Regresar')]",
            "//button[contains(text(), 'Volver')]",
            "//a[contains(text(), 'Dashboard')]",
            "//a[contains(text(), 'Inicio')]"
        ]

        for selector in selectores_regresar:
            if ComponenteInteraccion.clickComponenteOpcional(page, selector, f"botón regresar ({selector})", intentos=1, timeout=3000):
                LogManager.escribir_log("INFO", "Regreso al dashboard exitoso")
                esperarConLoaderSimple(3, "Esperando carga del dashboard")

                # Verificar que la tabla de cuentas esté visible
                if ComponenteInteraccion.esperarElemento(page, "//tbody[contains(@id, 'tablaDatosConsolAhorros_data')]", timeout=10000, descripcion="tabla de cuentas"):
                    return True
                break

        LogManager.escribir_log(
            "WARNING", "No se pudo encontrar botón para regresar al dashboard")
        return False

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error al regresar al dashboard: {str(e)}")
        return False


def procesar_empresa_por_posicion(page, id_ejecucion, posicion):
    """Procesa una empresa específica por posición (primera/ultima)"""
    try:
       # Seleccionar empresa
        if not seleccionar_empresa(page, posicion):
            return False

        # Esperar a que aparezcan los elementos de la página de movimientos
        if not ComponenteInteraccion.esperarElemento(page, "//form/div[6]/span/button", timeout=15000, descripcion="botón consultar movimientos"):
            LogManager.escribir_log(
                "ERROR", "No se encontró el botón de consultar movimientos")
            return False

        # Consultar movimientos
        if not consultar_movimientos(page):
            return False

        # Descargar y procesar archivo
        resultado = descargar_y_procesar_archivo(page, id_ejecucion, posicion)

        return resultado

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error procesando empresa {posicion}: {str(e)}")
        return False


def seleccionar_empresa(page, posicion):
    """Selecciona una empresa específica (primera/ultima)"""
    try:
        if posicion == "ultima":
            # Última fila - hacer click en el enlace de la cuenta
            enlace_xpath = "//tbody[contains(@id, 'tablaDatosConsolAhorros_data')]/tr[last()]//a[contains(@id, ':tablaDatosConsolAhorros:')]"
        else:  # primera
            # Primera fila - hacer click en el enlace de la cuenta
            enlace_xpath = "//tbody[contains(@id, 'tablaDatosConsolAhorros_data')]/tr[1]//a[contains(@id, ':tablaDatosConsolAhorros:')]"

        click_con_habilitacion(page, enlace_xpath, f"enlace cuenta {posicion}")
        LogManager.escribir_log("INFO", f"Cuenta seleccionada: {posicion}")

        # Esperar a que aparezca la página de movimientos
        esperarConLoaderSimple(3, "Esperando carga de página de movimientos")
        return True

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error al seleccionar empresa {posicion}: {str(e)}")
        return False


def consultar_movimientos(page):
    """Hace click en el botón consultar"""
    try:
        consultar_xpath = "//form/div[6]/span/button"
        click_con_habilitacion(page, consultar_xpath, "botón consultar")
        LogManager.escribir_log("INFO", "Consulta de movimientos iniciada")
        esperarConLoaderSimple(2, "Esperando procesamiento de consulta")
        return True

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error al consultar movimientos: {str(e)}")
        return False


def descargar_y_procesar_archivo(page, id_ejecucion, posicion):
    """Descarga el archivo de movimientos y lo procesa"""
    try:
        LogManager.escribir_log("INFO", "Descargando archivo...")

        # Habilitar botón de descarga antes de usar esperarDescarga
        descargar_xpath = "//div/form/div[1]/div/div[3]/div[1]/button"
        habilitar_campo_si_es_necesario(page, descargar_xpath)

        # Usar esperarDescarga para obtener la ruta del archivo descargado
        ruta_archivo = ComponenteInteraccion.esperarDescarga(
            page,
            descargar_xpath,
            timeout=30000,
            descripcion="botón descargar movimientos JEP"
        )

        if not ruta_archivo:
            LogManager.escribir_log(
                "ERROR", f"No se pudo descargar archivo para empresa {posicion}")
            return False

        # Procesar archivo descargado
        if procesar_archivo_excel(ruta_archivo, id_ejecucion, posicion):
            LogManager.escribir_log(
                "SUCCESS", f"Movimientos de empresa {posicion} procesados exitosamente")

            # Regresar a selección de empresas para siguiente iteración
            regresar_seleccion(page)
            return True
        else:
            LogManager.escribir_log(
                "ERROR", f"Error procesando archivo de empresa {posicion}")
            return False

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error descargando archivo para empresa {posicion}: {str(e)}")
        return False


def regresar_seleccion(page):
    """Regresa a la selección de empresas"""
    try:
        regresar_xpath = "//div/form/div[3]/div/div/button"
        click_con_habilitacion(page, regresar_xpath, "botón regresar")

        LogManager.escribir_log("INFO", "Regreso a selección de empresas")
        esperarConLoaderSimple(1, "Esperando regreso a selección")
        return True

    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error al regresar: {str(e)}")
        return False

# ==================== FUNCIONES DE PROCESAMIENTO DE ARCHIVOS ====================


def procesar_archivo_excel(ruta_archivo, id_ejecucion, empresa_posicion):
    """Procesa el archivo Excel descargado de JEP"""
    try:
        LogManager.escribir_log(
            "INFO", f"Procesando movimeintos ...")

        # Leer el archivo Excel usando componentes comunes
        contenido = LectorArchivos.leerExcel(ruta_archivo)
        if contenido is None:
            LogManager.escribir_log(
                "ERROR", f"No se pudo leer el archivo: {ruta_archivo}")
            return False

        # Validar que hay suficientes filas
        if len(contenido) < 8:
            LogManager.escribir_log(
                "WARNING", f"El archivo solo tiene {len(contenido)} filas, se esperaban al menos 8")
            return False

        # Extraer información del archivo según configuración JEP
        empresa = ""
        cuenta = ""

        # Extraer empresa (celda A5)
        if len(contenido) > 4 and len(contenido[4]) > 0:
            empresa = str(contenido[4][0]) if contenido[4][0] else ""

        # Extraer cuenta (celda A4)
        if len(contenido) > 3 and len(contenido[3]) > 0:
            cuenta_raw = str(contenido[3][0]) if contenido[3][0] else ""
            cuenta = cuenta_raw.split(":")[1].strip(
            ) if ":" in cuenta_raw else cuenta_raw.strip()

        LogManager.escribir_log(
            "INFO", f"Empresa: '{empresa}', Cuenta: '{cuenta}'")

        if not cuenta:
            LogManager.escribir_log(
                "WARNING", "No se pudo extraer número de cuenta")
            cuenta = "SIN_CUENTA"

        # Obtener rango de fechas del archivo para la consulta previa
        LogManager.escribir_log(
            "INFO", "🔍 Analizando rango de fechas en el archivo...")
        fechas_archivo = []

        # Los datos empiezan en la fila 8 (índice 7)
        for i in range(7, len(contenido)):
            fila = contenido[i]
            if fila and len(fila) > 1 and fila[1]:
                fecha_str = str(fila[0])
                if fecha_str not in fechas_archivo:
                    fechas_archivo.append(fecha_str)

        if not fechas_archivo:
            LogManager.escribir_log(
                "WARNING", "No se encontraron fechas válidas en el archivo")
            return False

        fechas_convertidas = []
        for fecha_str in fechas_archivo:
            fecha_sql = convertir_fecha_sql(fecha_str)
            if fecha_sql:
                fechas_convertidas.append(fecha_sql)
        if not fechas_convertidas:
            LogManager.escribir_log(
                "WARNING", "No se pudieron convertir las fechas")
            return False

        # Determinar rango de fechas
        fecha_min = min(fechas_convertidas)
        fecha_max = max(fechas_convertidas)
        LogManager.escribir_log(
            "INFO", f"📅 Rango de fechas en archivo: {fecha_min} a {fecha_max}")

        # Consultar registros existentes en la BD
        LogManager.escribir_log(
            "INFO", "🔎 Consultando registros existentes en la base de datos...")

        # CONSULTA 1: Obtener TODOS los documentos para esta cuenta y banco (para verificar PRIMARY KEY)
        # La PRIMARY KEY es (numCuenta, banco, numDocumento), así que necesitamos todos los documentos
        sql_documentos = f"""
            SELECT DISTINCT numDocumento
            FROM {DATABASE}
            WHERE numCuenta = '{cuenta}' 
            AND banco = '{CONFIG_JEP['banco_codigo']}'
        """
        documentos_bd_todos = BaseDatos.consultarBD(sql_documentos)
        documentos_existentes_en_bd = set()
        if documentos_bd_todos:
            for doc in documentos_bd_todos:
                documentos_existentes_en_bd.add(str(doc[0]))
        
        LogManager.escribir_log(
            "INFO", f"📋 Documentos existentes encontrados: {len(documentos_existentes_en_bd)}")

        # CONSULTA 2: Obtener registros en el rango de fechas para verificar combinaciones
        sql_consulta = f"""
            SELECT numDocumento, fechaTransaccion, valor, tipo, conceptoTransaccion
            FROM {DATABASE}
            WHERE numCuenta = '{cuenta}' 
            AND banco = '{CONFIG_JEP['banco_codigo']}' 
            AND empresa = '{empresa}' 
            AND fechaTransaccion BETWEEN '{fecha_min}' AND '{fecha_max}'
        """

        registros_existentes = BaseDatos.consultarBD(sql_consulta)
        combinaciones_existentes = set()

        if registros_existentes:
            for registro in registros_existentes:
                num_documento_bd_completo = str(registro[0])
                fecha_bd = str(registro[1])
                valor_bd = float(registro[2])
                tipo_bd = str(registro[3])
                concepto_bd = str(registro[4]) if registro[4] else ""

                # Extraer número base (sin sufijo) para la combinación
                # Esto permite que coincidan registros con mismo base pero diferentes sufijos
                num_documento_bd_base = extraer_numero_documento_base(num_documento_bd_completo)

                # Crear combinación única usando el número BASE: numDocumentoBase + fecha + valor + tipo + concepto
                # Usar el número base permite detectar duplicados incluso si tienen sufijos diferentes (_1, _2, etc.)
                clave_combinacion = f"{num_documento_bd_base}|{fecha_bd}|{valor_bd}|{tipo_bd}|{concepto_bd[:50]}"
                combinaciones_existentes.add(clave_combinacion)
        else:
            LogManager.escribir_log(
                "INFO", "📋 No se encontraron registros existentes en el rango de fechas")

        # Procesar movimientos del archivo
        movimientos_insertados = 0
        movimientos_omitidos = 0
        filas_procesadas = 0
        documentos_procesados_en_memoria = set()
        combinaciones_procesadas_memoria = set()

        for i in range(7, len(contenido)):  # Empezar desde fila 8 (índice 7)
            fila = contenido[i]

            if not fila or len(fila) < 7:
                continue

            # Extraer datos básicos
            fecha_str = str(fila[0]) if fila[0] else ""
            tipo_trx_raw = str(fila[1]) if fila[1] else ""
            num_documento_raw = str(fila[2]) if fila[2] else ""
            descripcion = str(fila[3]) if fila[3] else ""
            oficina = str(fila[4]) if fila[4] else ""
            valor_str = str(fila[5]) if fila[5] else ""
            saldo_str = str(fila[6]) if fila[6] else ""

            if not fecha_str or not valor_str:
                continue

            filas_procesadas += 1

            try:
                # Convertir fecha
                fecha_convertida = convertir_fecha_sql(fecha_str)
                if not fecha_convertida:
                    LogManager.escribir_log(
                        "WARNING", f"Fecha inválida en fila {i+1}: {fecha_str}")
                    continue

                # Determinar tipo
                tipo_trx = "C" if tipo_trx_raw.upper() == "CREDITO" else "D"

                # Limpiar valores monetarios
                valor = limpiar_valor_monetario(valor_str)
                saldo = limpiar_valor_monetario(saldo_str)

                # Aplicar prefijo si es TECNICENTRO
                prefijo = CONFIG_JEP['prefijo_tecnicentro'] if cuenta == NUM_CUENTA_TECNICENTRO else ""
                descripcion_final = f"{prefijo}{descripcion}".strip()

                # PASO 1: Procesar número de documento BASE primero (necesario para la combinación)
                if num_documento_raw and num_documento_raw.strip():
                    num_documento_base = num_documento_raw.strip()
                else:
                    # Generar número de documento si no existe
                    fecha_codigo = fecha_str.replace("/", "")
                    tipo_codigo = str(len(tipo_trx_raw))
                    concepto_codigo = str(len(descripcion))
                    agencia_codigo = str(len(oficina))
                    monto_codigo = str(valor).replace('.', '').replace(',', '')
                    saldo_codigo = str(saldo).replace('.', '').replace(',', '')
                    num_documento_base = f"{fecha_codigo}{tipo_codigo}{concepto_codigo}{agencia_codigo}{monto_codigo}{saldo_codigo}G"

                # Crear combinación única usando el número BASE (sin sufijo): numDocumentoBase + fecha + valor + tipo + concepto
                # Usar el número base permite detectar duplicados incluso si en BD tienen sufijos (_1, _2, etc.)
                # El numDocumento es crítico para diferenciar registros con mismos datos pero diferentes documentos
                clave_combinacion_archivo = f"{num_documento_base}|{fecha_convertida}|{valor}|{tipo_trx}|{descripcion_final[:50]}"

                # PASO 2: Verificar si ya existe por combinación completa (usando número base)
                # Si la combinación existe, es el mismo registro, omitir (incluso si en BD tiene sufijo _1, _2, etc.)
                if clave_combinacion_archivo in combinaciones_existentes:
                    movimientos_omitidos += 1
                    LogManager.escribir_log(
                        "DEBUG", f"📋 Movimiento omitido (combinación duplicada en BD): {num_documento_base} - {fecha_convertida} - ${valor} - {tipo_trx}")
                    continue

                # Verificar si ya se procesó en memoria (mismo archivo)
                if clave_combinacion_archivo in combinaciones_procesadas_memoria:
                    movimientos_omitidos += 1
                    LogManager.escribir_log(
                        "DEBUG", f"📋 Movimiento omitido (duplicado en archivo): {num_documento_base} - {fecha_convertida} - ${valor} - {tipo_trx}")
                    continue

                # PASO 3: Obtener contador de fecha
                cont_fecha = obtener_contador_fecha(
                    cuenta, empresa, fecha_convertida)

                # PASO 4: Asegurar número de documento único (para PRIMARY KEY)
                # Si el número de documento ya existe pero la combinación es diferente,
                # agregar sufijo para diferenciarlo
                num_documento_final = asegurar_numero_unico(
                    num_documento_base, documentos_existentes_en_bd, documentos_procesados_en_memoria)
                
                # Si se agregó un sufijo, loguear la razón
                if num_documento_final != num_documento_base:
                    LogManager.escribir_log(
                        "DEBUG", f"📝 Número de documento con sufijo: {num_documento_base} -> {num_documento_final} (número base duplicado, agregando sufijo para PRIMARY KEY)")

                # VERIFICACIÓN FINAL: Asegurar que el documento final no existe antes de insertar
                # Esto previene errores de PRIMARY KEY (numCuenta, banco, numDocumento)
                intentos_verificacion = 0
                while (num_documento_final in documentos_existentes_en_bd or 
                       num_documento_final in documentos_procesados_en_memoria) and intentos_verificacion < 10:
                    intentos_verificacion += 1
                    LogManager.escribir_log(
                        "WARNING", f"⚠️ Documento {num_documento_final} aún existe (intento {intentos_verificacion}), buscando siguiente sufijo...")
                    
                    # Extraer el sufijo actual si existe
                    if "_" in num_documento_final:
                        partes = num_documento_final.rsplit("_", 1)
                        try:
                            sufijo_actual = int(partes[1])
                            num_documento_final = f"{num_documento_base}_{sufijo_actual + 1}"
                        except:
                            num_documento_final = f"{num_documento_base}_1"
                    else:
                        num_documento_final = f"{num_documento_base}_1"
                
                if intentos_verificacion >= 10:
                    # Si después de 10 intentos aún hay conflicto, usar timestamp
                    num_documento_final = f"{num_documento_base}_{int(time.time())}"
                    LogManager.escribir_log(
                        "WARNING", f"⚠️ Usando timestamp para número de documento único: {num_documento_final}")

                # Insertar en base de datos con reintentos en caso de PRIMARY KEY duplicada
                intentos_insert = 0
                insertado = False
                
                while not insertado and intentos_insert < 5:
                    sql_insert = f"""
                        INSERT INTO {DATABASE} 
                        (numCuenta, banco, empresa, numDocumento, idEjecucion, fechaTransaccion, 
                         tipo, valor, saldoContable, oficina, conceptoTransaccion, contFecha)
                        VALUES ('{cuenta}', '{CONFIG_JEP['banco_codigo']}', '{empresa.replace("'", "''")}', 
                                '{num_documento_final}', {id_ejecucion}, '{fecha_convertida}', 
                                '{tipo_trx}', {valor}, {saldo}, '{oficina.replace("'", "''")}', 
                                '{descripcion_final.replace("'", "''")}', {cont_fecha})
                    """

                    if datosEjecucion(sql_insert):
                        movimientos_insertados += 1
                        # Agregar a los sets de memoria para evitar duplicados en el mismo procesamiento
                        documentos_procesados_en_memoria.add(num_documento_final)
                        documentos_existentes_en_bd.add(num_documento_final)  # Actualizar también el set de BD
                        # Usar la combinación con numDocumento base para verificación de duplicados
                        combinaciones_procesadas_memoria.add(clave_combinacion_archivo)

                        LogManager.escribir_log(
                            "DEBUG", f"✅ Movimiento insertado: {num_documento_final} - {fecha_convertida} - ${valor} - {tipo_trx}")
                        insertado = True
                    else:
                        # Si falla por PRIMARY KEY, intentar con siguiente sufijo
                        intentos_insert += 1
                        if intentos_insert < 5:
                            LogManager.escribir_log(
                                "WARNING", f"⚠️ Error insertando {num_documento_final} (intento {intentos_insert}), intentando con siguiente sufijo...")
                            
                            # Buscar siguiente sufijo
                            if "_" in num_documento_final:
                                partes = num_documento_final.rsplit("_", 1)
                                try:
                                    sufijo_actual = int(partes[1])
                                    num_documento_final = f"{num_documento_base}_{sufijo_actual + 1}"
                                except:
                                    num_documento_final = f"{num_documento_base}_{intentos_insert + 1}"
                            else:
                                num_documento_final = f"{num_documento_base}_{intentos_insert + 1}"
                        else:
                            LogManager.escribir_log(
                                "ERROR", f"❌ Error insertando movimiento después de {intentos_insert} intentos: {num_documento_final}")

            except Exception as e:
                LogManager.escribir_log(
                    "ERROR", f"Error procesando fila {i+1}: {str(e)}")
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
        LogManager.escribir_log(
            "INFO", f"📋 Combinaciones existentes en BD: {len(combinaciones_existentes)}")

        # Considerar éxito tanto si hay nuevos como si no hay
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
        LogManager.escribir_log(
            "ERROR", f"Error procesando archivo Excel: {str(e)}")
        return False


def obtener_contador_fecha(cuenta, empresa, fecha):
    """Obtiene el siguiente contador de fecha para evitar duplicados"""
    try:
        sql = f"""
            SELECT COALESCE(MAX(contFecha), 0) + 1 AS maxCont 
            FROM {DATABASE} 
            WHERE numCuenta = '{cuenta}' 
            AND banco = '{CONFIG_JEP['banco_codigo']}' 
            AND empresa = '{empresa}' 
            AND fechaTransaccion = '{fecha}'
        """
        resultado = BaseDatos.consultarBD(sql)
        return resultado[0][0] if resultado and resultado[0] else 1
    except Exception as e:
        LogManager.escribir_log(
            "WARNING", f"Error obteniendo contador fecha: {str(e)}")
        return 1


def asegurar_numero_unico(num_documento_base, documentos_bd, documentos_memoria):
    """
    Asegura que el número de documento sea único.
    Si el número base ya existe, busca el siguiente sufijo disponible.
    """
    try:
        # Verificar si el número base ya existe (con o sin sufijo)
        existe_base = num_documento_base in documentos_bd or num_documento_base in documentos_memoria
        
        # Si no existe el número base, retornarlo directamente
        if not existe_base:
            return num_documento_base

        # Si existe el número base, buscar el siguiente sufijo disponible
        # Buscar todos los sufijos existentes para este número base
        sufijos_existentes = set()
        
        # Buscar en documentos de BD
        for doc in documentos_bd:
            if doc == num_documento_base:
                sufijos_existentes.add(0)  # El base existe
            elif doc.startswith(num_documento_base + "_"):
                try:
                    sufijo_str = doc[len(num_documento_base) + 1:]  # Obtener parte después de "_"
                    # Verificar si es un número
                    if sufijo_str.isdigit():
                        sufijos_existentes.add(int(sufijo_str))
                except:
                    pass
        
        # Buscar en documentos en memoria
        for doc in documentos_memoria:
            if doc == num_documento_base:
                sufijos_existentes.add(0)  # El base existe
            elif doc.startswith(num_documento_base + "_"):
                try:
                    sufijo_str = doc[len(num_documento_base) + 1:]  # Obtener parte después de "_"
                    # Verificar si es un número
                    if sufijo_str.isdigit():
                        sufijos_existentes.add(int(sufijo_str))
                except:
                    pass

        # Encontrar el siguiente sufijo disponible
        sufijo = 1
        while sufijo in sufijos_existentes:
            sufijo += 1
            if sufijo > 1000:  # Evitar bucle infinito
                return f"{num_documento_base}_{int(time.time())}"

        num_documento_con_sufijo = f"{num_documento_base}_{sufijo}"
        LogManager.escribir_log(
            "DEBUG", f"📝 Número con sufijo generado: {num_documento_base} -> {num_documento_con_sufijo} (sufijos existentes: {sorted(sufijos_existentes)})")
        return num_documento_con_sufijo

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error asegurando número único: {str(e)}")
        return f"{num_documento_base}_{int(time.time())}"

# ==================== FUNCIONES AUXILIARES ====================


def extraer_numero_documento_base(num_documento):
    """
    Extrae el número de documento base (sin sufijo) de un numDocumento.
    Ejemplos:
    - '9550' -> '9550'
    - '9550_1' -> '9550'
    - '9550_2' -> '9550'
    """
    try:
        if not num_documento:
            return ""
        
        num_doc_str = str(num_documento).strip()
        
        # Si tiene sufijo (formato: base_sufijo), extraer solo la base
        if "_" in num_doc_str:
            # Dividir por el último "_" para obtener la base
            partes = num_doc_str.rsplit("_", 1)
            # Verificar que la segunda parte sea numérica (sufijo)
            if len(partes) == 2 and partes[1].isdigit():
                return partes[0]
        
        # Si no tiene sufijo, retornar tal cual
        return num_doc_str
    except Exception as e:
        LogManager.escribir_log(
            "WARNING", f"Error extrayendo número base de '{num_documento}': {str(e)}")
        return str(num_documento) if num_documento else ""


def habilitar_campo_si_es_necesario(page, selector):
    """Habilita un campo si está deshabilitado"""
    try:
        element = page.locator(selector).first
        element.evaluate("""
            element => {
                element.removeAttribute('aria-disabled');
                element.removeAttribute('disabled');
                element.removeAttribute('readonly');
                element.setAttribute('aria-disabled', 'false');
                element.disabled = false;
                element.readOnly = false;
                
                // Para inputs específicos
                if (element.tagName === 'INPUT') {
                    element.style.backgroundColor = '';
                    element.style.color = '';
                    element.removeAttribute('aria-readonly');
                }
                
                // Para botones
                if (element.tagName === 'BUTTON') {
                    element.style.pointerEvents = 'auto';
                    element.style.opacity = '1';
                }
                
                element.focus();
            }
        """)
        return True
    except Exception as e:
        LogManager.escribir_log(
            "DEBUG", f"No se pudo habilitar el campo {selector}: {str(e)}")
        return False


def escribir_con_habilitacion(page, selector, texto, descripcion="campo"):
    """Escribe en un campo después de habilitarlo"""
    try:
        # Habilitar campo primero
        habilitar_campo_si_es_necesario(page, selector)

        # esperarConLoaderSimple(1, f"Esperando después de habilitar {descripcion}")

        # Escribir texto
        ComponenteInteraccion.escribirComponente(
            page, selector, texto, descripcion=descripcion)

        return True
    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error escribiendo en {descripcion}: {str(e)}")
        return False


def click_con_habilitacion(page, selector, descripcion="elemento"):
    """Hace click en un elemento después de habilitarlo"""
    try:
        # Habilitar elemento primero
        habilitar_campo_si_es_necesario(page, selector)
        # esperarConLoaderSimple(1, f"Esperando después de habilitar {descripcion}")

        # Hacer click
        ComponenteInteraccion.clickComponente(
            page, selector, descripcion=descripcion)

        return True
    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error haciendo click en {descripcion}: {str(e)}")
        return False


def limpiar_con_habilitacion(page, selector, descripcion="campo"):
    """Limpia un campo después de habilitarlo"""
    try:
        # Habilitar campo primero
        habilitar_campo_si_es_necesario(page, selector)
        # esperarConLoaderSimple(1, f"Esperando después de habilitar {descripcion}")

        # Limpiar campo
        element = page.locator(selector).first
        element.clear()

        return True
    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error limpiando {descripcion}: {str(e)}")
        return False


def click_opcional_con_habilitacion(page, selector, descripcion="elemento", intentos=2, timeout=5000):
    """Hace click opcional en un elemento después de habilitarlo"""
    try:
        # Habilitar elemento primero
        habilitar_campo_si_es_necesario(page, selector)
        # esperarConLoaderSimple(1, f"Esperando después de habilitar {descripcion}")

        # Hacer click opcional
        resultado = ComponenteInteraccion.clickComponenteOpcional(
            page, selector, descripcion, intentos=intentos, timeout=timeout
        )

        return resultado
    except Exception as e:
        LogManager.escribir_log(
            "DEBUG", f"Click opcional falló en {descripcion}: {str(e)}")
        return False


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

# ==================== FUNCIONES DE PROCESAMIENTO MANUAL ====================


def identificar_empresa_desde_archivo(ruta_archivo):
    """Identifica la empresa desde un archivo Excel de JEP"""
    try:
        contenido = LectorArchivos.leerExcel(ruta_archivo)
        if contenido is None or len(contenido) < 5:
            return None, None
        
        # Extraer empresa (celda A5, índice 4)
        empresa = ""
        if len(contenido) > 4 and len(contenido[4]) > 0:
            empresa = str(contenido[4][0]) if contenido[4][0] else ""
        
        # Extraer cuenta (celda A4, índice 3)
        cuenta = ""
        if len(contenido) > 3 and len(contenido[3]) > 0:
            cuenta_raw = str(contenido[3][0]) if contenido[3][0] else ""
            cuenta = cuenta_raw.split(":")[1].strip() if ":" in cuenta_raw else cuenta_raw.strip()
        
        # Identificar tipo de empresa
        empresa_normalizada = empresa.upper().strip() if empresa else ""
        cuenta_normalizada = cuenta.strip() if cuenta else ""
        
        # Verificar si es Tecnicentro por cuenta
        if cuenta_normalizada == NUM_CUENTA_TECNICENTRO:
            return "AUTOLLANTA TECNICENTRO", cuenta_normalizada
        
        # Verificar por nombre de empresa
        if "AUTOLLANTA" in empresa_normalizada and "TECNICENTRO" in empresa_normalizada:
            return "AUTOLLANTA TECNICENTRO", cuenta_normalizada
        elif "AUTOLLANTA" in empresa_normalizada:
            return "AUTOLLANTA", cuenta_normalizada
        elif "MAXXIMUNDO" in empresa_normalizada:
            return "MAXXIMUNDO", cuenta_normalizada
        
        # Si no se identifica, retornar el nombre original
        return empresa, cuenta_normalizada
        
    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error identificando empresa desde archivo {ruta_archivo}: {str(e)}")
        return None, None


def buscar_archivos_jep_en_descargas():
    """Busca archivos Excel de JEP en la carpeta de descargas por nombres específicos"""
    try:
        carpeta_descargas = RUTAS_CONFIG['descargas']
        if not os.path.exists(carpeta_descargas):
            LogManager.escribir_log(
                "ERROR", f"La carpeta de descargas no existe: {carpeta_descargas}")
            return []
        
        # Mapeo de nombres de archivo a empresas (ordenados de más específico a menos específico)
        nombres_archivos = [
            ('jepAutollantaT', 'AUTOLLANTA TECNICENTRO'),  # Más específico primero
            ('jepAutollanta', 'AUTOLLANTA'),
            ('jepMaxximundo', 'MAXXIMUNDO')
        ]
        
        archivos_encontrados = []
        archivos_procesados = set()  # Para evitar procesar el mismo archivo dos veces
        
        # Buscar archivos por nombre específico (ordenados de más específico a menos)
        for nombre_base, empresa_nombre in nombres_archivos:
            # Buscar archivos que empiecen con el nombre base (puede tener extensión .xlsx o .xls)
            for archivo in os.listdir(carpeta_descargas):
                # Evitar procesar archivos ya asignados
                if archivo in archivos_procesados:
                    continue
                    
                archivo_lower = archivo.lower()
                nombre_base_lower = nombre_base.lower()
                
                # Verificar coincidencia exacta del nombre base (sin extensión)
                nombre_sin_ext = os.path.splitext(archivo_lower)[0]
                
                # Verificar si el nombre del archivo (sin extensión) coincide exactamente con el nombre base
                if nombre_sin_ext == nombre_base_lower and archivo_lower.endswith(('.xlsx', '.xls')):
                    ruta_completa = os.path.join(carpeta_descargas, archivo)
                    
                    # Verificar que el archivo existe y es válido
                    if os.path.isfile(ruta_completa):
                        # Obtener cuenta desde el archivo para validación
                        _, cuenta = identificar_empresa_desde_archivo(ruta_completa)
                        
                        archivos_encontrados.append({
                            'ruta': ruta_completa,
                            'nombre': archivo,
                            'empresa': empresa_nombre,
                            'cuenta': cuenta
                        })
                        archivos_procesados.add(archivo)  # Marcar como procesado
                        LogManager.escribir_log(
                            "SUCCESS", f"✅ Archivo encontrado: {archivo} -> Empresa: {empresa_nombre}, Cuenta: {cuenta}")
                        break  # Solo tomar el primer archivo que coincida con el nombre
        
        return archivos_encontrados
        
    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error buscando archivos JEP: {str(e)}")
        return []


def procesar_archivos_manuales():
    """Procesa archivos de JEP manualmente desde la carpeta de descargas"""
    try:
        LogManager.escribir_log("INFO", "=" * 60)
        LogManager.escribir_log("INFO", "📁 MODO MANUAL: Procesamiento de archivos JEP")
        LogManager.escribir_log("INFO", "=" * 60)
        
        # Obtener ID de ejecución
        id_ejecucion = obtenerIDEjecucion()
        LogManager.iniciar_proceso(NOMBRE_BANCO, id_ejecucion, f"Procesamiento Manual JEP - ID: {id_ejecucion}")
        
        # Registrar inicio de ejecución
        sql_inicio = f"""
            INSERT INTO {DATABASE_RUNS} (idAutomationRun, processName, startDate, finalizationStatus) 
            VALUES ({id_ejecucion}, 'Procesamiento Manual JEP', SYSDATETIME(), 'Running')
        """
        datosEjecucion(sql_inicio)
        escribirLog(
            f"Iniciando procesamiento manual {NOMBRE_BANCO}", id_ejecucion, "INFO", "INICIO")
        
        # Buscar archivos en la carpeta de descargas
        LogManager.escribir_log(
            "INFO", "🔍 Buscando archivos con nombres específicos:")
        LogManager.escribir_log(
            "INFO", "   - jepAutollanta.xlsx (o .xls) -> Autollanta")
        LogManager.escribir_log(
            "INFO", "   - jepAutollantaT.xlsx (o .xls) -> Autollanta Tecnicentro")
        LogManager.escribir_log(
            "INFO", "   - jepMaxximundo.xlsx (o .xls) -> Maxximundo")
        
        archivos = buscar_archivos_jep_en_descargas()
        
        if not archivos:
            LogManager.escribir_log(
                "ERROR", "No se encontraron archivos Excel de JEP en la carpeta de descargas")
            LogManager.escribir_log(
                "ERROR", "Asegúrate de que los archivos tengan los nombres: jepAutollanta, jepAutollantaT, jepMaxximundo")
            return False
        
        # Empresas objetivo
        empresas_objetivo = {
            "AUTOLLANTA": None,
            "AUTOLLANTA TECNICENTRO": None,
            "MAXXIMUNDO": None
        }
        
        # Identificar archivos por empresa
        for archivo_info in archivos:
            empresa = archivo_info['empresa']
            if empresa in empresas_objetivo:
                if empresas_objetivo[empresa] is None:
                    empresas_objetivo[empresa] = archivo_info
                    LogManager.escribir_log(
                        "SUCCESS", f"✅ Archivo identificado para {empresa}: {archivo_info['nombre']}")
                else:
                    LogManager.escribir_log(
                        "WARNING", f"⚠️ Múltiples archivos encontrados para {empresa}, usando el primero")
        
        # Procesar cada empresa
        empresas_procesadas = 0
        empresas_exitosas = 0
        
        # Mapeo de empresas a nombres de archivo esperados
        nombres_esperados = {
            "AUTOLLANTA": "jepAutollanta",
            "AUTOLLANTA TECNICENTRO": "jepAutollantaT",
            "MAXXIMUNDO": "jepMaxximundo"
        }
        
        for empresa_nombre, archivo_info in empresas_objetivo.items():
            if archivo_info is None:
                nombre_esperado = nombres_esperados.get(empresa_nombre, "desconocido")
                LogManager.escribir_log(
                    "WARNING", f"⚠️ No se encontró archivo para {empresa_nombre} (buscar: {nombre_esperado}.xlsx o .xls)")
                continue
            
            empresas_procesadas += 1
            LogManager.escribir_log("INFO", "=" * 60)
            LogManager.escribir_log(
                "INFO", f"🔄 Procesando {empresa_nombre} desde archivo: {archivo_info['nombre']}")
            LogManager.escribir_log("INFO", "=" * 60)
            
            # Determinar posición para el procesamiento (solo para compatibilidad con la función existente)
            posicion = "manual"
            
            # Procesar archivo
            if procesar_archivo_excel(archivo_info['ruta'], id_ejecucion, posicion):
                empresas_exitosas += 1
                LogManager.escribir_log(
                    "SUCCESS", f"✅ {empresa_nombre} procesada exitosamente")
            else:
                LogManager.escribir_log(
                    "ERROR", f"❌ Error procesando {empresa_nombre}")
        
        # Resumen final
        LogManager.escribir_log("INFO", "=" * 60)
        LogManager.escribir_log("INFO", "📊 RESUMEN PROCESAMIENTO MANUAL")
        LogManager.escribir_log("INFO", "=" * 60)
        LogManager.escribir_log(
            "INFO", f"📁 Archivos encontrados: {len(archivos)}")
        LogManager.escribir_log(
            "INFO", f"🔄 Empresas procesadas: {empresas_procesadas}")
        LogManager.escribir_log(
            "INFO", f"✅ Empresas exitosas: {empresas_exitosas}")
        LogManager.escribir_log("INFO", "=" * 60)
        
        # Actualizar estado en BD
        if empresas_exitosas > 0:
            estado_final = "Exitoso" if empresas_exitosas == empresas_procesadas else "Parcial"
            sql_exito = f"""
                UPDATE {DATABASE_RUNS} 
                SET endDate = SYSDATETIME(), finalizationStatus = '{estado_final}'
                WHERE idAutomationRun = {id_ejecucion}
            """
            datosEjecucion(sql_exito)
            escribirLog(
                f"Procesamiento manual {NOMBRE_BANCO} completado: {empresas_exitosas}/{empresas_procesadas} empresas exitosas",
                id_ejecucion, "SUCCESS", "FIN")
            
            # Ejecutar BAT para subir movimientos al portal
            LogManager.escribir_log("INFO", "🔧 Ejecutando proceso final...")
            SubprocesoManager.ejecutar_bat_final()
            
            return True
        else:
            sql_error = f"""
                UPDATE {DATABASE_RUNS} 
                SET endDate = SYSDATETIME(), finalizationStatus = 'Error'
                WHERE idAutomationRun = {id_ejecucion}
            """
            datosEjecucion(sql_error)
            escribirLog(
                f"Error: Procesamiento manual {NOMBRE_BANCO} falló",
                id_ejecucion, "ERROR", "FIN")
            return False
            
    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"❌ Error en procesamiento manual: {str(e)}")
        return False


# ==================== FUNCIÓN PRINCIPAL ====================


def procesar_cuenta_individual(page, usuario, password, id_ejecucion, numero_cuenta):
    """Procesa una cuenta individual de JEP"""
    try:
        LogManager.escribir_log(
            "INFO", f"🔑 Iniciando sesión para cuenta {numero_cuenta}: {usuario}")

        # Navegar a login
        if not navegar_a_login(page):
            LogManager.escribir_log(
                "ERROR", f"Error navegando a login para {usuario}")
            return False

        # Iniciar sesión
        if not iniciar_sesion(page, usuario, password):
            LogManager.escribir_log("ERROR", f"Error en login para {usuario}")
            return False

        # Obtener y procesar movimientos
        if not obtener_y_procesar_movimientos(page, id_ejecucion):
            LogManager.escribir_log(
                "ERROR", f"Error procesando movimientos para {usuario}")
            return False

        return True

    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error procesando cuenta {usuario}: {str(e)}")
        return False


def cerrar_sesion(page):
    """Cierra la sesión actual en JEP"""
    try:
        # Intentar cerrar sesión usando el botón de cerrar sesión
        boton_cerrar_sesion = "//a[contains(@class, 'ui-commandlink') and .//i[contains(@class, 'fa-power-off')]]"
        if ComponenteInteraccion.clickComponenteOpcional(page, boton_cerrar_sesion, "botón cerrar sesión", intentos=2, timeout=5000):
            LogManager.escribir_log("INFO", "Sesión cerrada exitosamente")
            esperarConLoaderSimple(3, "Esperando cierre de sesión")
            return True
    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error cerrando sesión: {str(e)}")

    return False


@with_timeout_check
def main():
    """Función principal del robot JEP"""

    id_ejecucion = None
    inicio_ejecucion = datetime.now()

    try:
        # Obtener ID de ejecución
        id_ejecucion = obtenerIDEjecucion()
        
        LogManager.iniciar_proceso(NOMBRE_BANCO, id_ejecucion, f"Automatización Cooperativa JEP - ID: {id_ejecucion}")
        # Iniciar timeout manager
        timeout_manager.start()

        # Registrar inicio de ejecución
        sql_inicio = f"""
            INSERT INTO {DATABASE_RUNS} (idAutomationRun, processName, startDate, finalizationStatus) 
            VALUES ({id_ejecucion}, 'Descarga comprobantes-Cooperativa JEP', SYSDATETIME(), 'Running')
        """
        datosEjecucion(sql_inicio)
        escribirLog(
            f"Iniciando automatización {NOMBRE_BANCO}", id_ejecucion, "INFO", "INICIO")

        # Leer credenciales del banco
        credenciales_banco = LectorArchivos.leerCSV(
            RUTAS_CONFIG['credenciales_banco'],
            filtro_columna=0,
            valor_filtro=CONFIG_JEP['banco_codigo']
        )

        if not credenciales_banco:
            LogManager.escribir_log(
                "ERROR", f"No se encontraron credenciales para {CONFIG_JEP['banco_codigo']}")
            return False

        LogManager.escribir_log(
            "INFO", f"Se encontraron {len(credenciales_banco)} cuentas para procesar")

        # Procesar cada cuenta
        cuentas_exitosas = 0
        cuentas_fallidas = 0

        for i, credencial in enumerate(credenciales_banco):

            usuario = credencial[1]
            password = credencial[2]
            LogManager.escribir_log(
                "INFO", f"🔄 Procesando cuenta {i+1}/{len(credenciales_banco)}: {usuario}")
            LogManager.escribir_log("INFO", "=" * 40)

            # Inicializar Playwright con timeout aumentado (la página tarda ~85 segundos)
            manager = PlaywrightManager(
                headless=True, download_path=RUTAS_CONFIG['descargas'], timeout=100000)
            playwright, browser, context, page = manager.iniciar_navegador()

            try:
                # Procesar cuenta actual
                if procesar_cuenta_individual(page, usuario, password, id_ejecucion, i+1):
                    cuentas_exitosas += 1
                    LogManager.escribir_log(
                        "SUCCESS", f"✅ Cuenta {usuario} procesada exitosamente")
                else:
                    cuentas_fallidas += 1
                    LogManager.escribir_log(
                        "ERROR", f"❌ Error procesando cuenta {usuario}")

            except Exception as e:
                cuentas_fallidas += 1
                LogManager.escribir_log(
                    "ERROR", f"❌ Error en cuenta {usuario}: {str(e)}")

            finally:
                # Cerrar navegador después de cada cuenta
                try:
                    cerrar_sesion(page)

                    if 'context' in locals():
                        context.close()
                    if 'browser' in locals():
                        browser.close()
                    if 'playwright' in locals():
                        playwright.stop()
                except Exception as e:
                    LogManager.escribir_log(
                        "WARNING", f"Error cerrando navegador: {str(e)}")

            # Esperar entre cuentas para evitar sobrecargar el servidor
            if i < len(credenciales_banco) - 1:  # No esperar después de la última cuenta
                LogManager.escribir_log(
                    "INFO", "⏳ Esperando 2 segundos antes de la siguiente cuenta...")
                esperarConLoaderSimple(2, f"Preparando cuenta {i+2}")

        # Resumen final
        tiempo_total = formatear_tiempo_ejecucion(
            datetime.now() - inicio_ejecucion)
        LogManager.escribir_log("INFO", "=" * 60)
        LogManager.escribir_log("INFO", "📊 RESUMEN FINAL DE PROCESAMIENTO")
        LogManager.escribir_log("INFO", "=" * 60)
        LogManager.escribir_log("INFO", f"🏦 Banco: {NOMBRE_BANCO}")
        LogManager.escribir_log(
            "INFO", f"👥 Total cuentas procesadas: {len(credenciales_banco)}")
        LogManager.escribir_log(
            "INFO", f"✅ Cuentas exitosas: {cuentas_exitosas}")
        LogManager.escribir_log(
            "INFO", f"❌ Cuentas fallidas: {cuentas_fallidas}")
        LogManager.escribir_log("INFO", f"⏱️ Tiempo total: {tiempo_total}")
        LogManager.escribir_log("INFO", "=" * 60)

        # Determinar resultado final
        if cuentas_exitosas > 0:
            estado_final = "Exitoso" if cuentas_fallidas == 0 else "Parcial"
            LogManager.escribir_log(
                "SUCCESS", f"✅ {NOMBRE_BANCO} completado: {estado_final}")

            sql_exito = f"""
                UPDATE {DATABASE_RUNS} 
                SET endDate = SYSDATETIME(), finalizationStatus = '{estado_final}'
                WHERE idAutomationRun = {id_ejecucion}
            """
            datosEjecucion(sql_exito)
            escribirLog(
                f"Automatización {NOMBRE_BANCO} completada: {cuentas_exitosas}/{len(credenciales_banco)} cuentas exitosas",
                id_ejecucion, "SUCCESS", "FIN")

            # Ejecutar BAT para subir moviemientos al portal
            LogManager.escribir_log("INFO", "🔧 Ejecutando proceso final...")
            SubprocesoManager.ejecutar_bat_final()

            return True
        else:
            LogManager.escribir_log(
                "ERROR", f"❌ Todas las cuentas de {NOMBRE_BANCO} fallaron")

            sql_error = f"""
                UPDATE {DATABASE_RUNS} 
                SET endDate = SYSDATETIME(), finalizationStatus = 'Error'
                WHERE idAutomationRun = {id_ejecucion}
            """
            datosEjecucion(sql_error)
            escribirLog(
                f"Error: Todas las cuentas de {NOMBRE_BANCO} fallaron",
                id_ejecucion, "ERROR", "FIN")

            # Ejecutar BAT para subir moviemientos al portal (aunque no haya éxito)'
            LogManager.escribir_log("INFO", "🔧 Ejecutando proceso final...")
            SubprocesoManager.ejecutar_bat_final()

            return False

    except Exception as e:
        tiempo_total = formatear_tiempo_ejecucion(
            datetime.now() - inicio_ejecucion)
        LogManager.escribir_log(
            "ERROR", f"❌ Error en {NOMBRE_BANCO}: {str(e)} (Tiempo: {tiempo_total})")

        if id_ejecucion:
            sql_error = f"""
                UPDATE {DATABASE_RUNS} 
                SET endDate = SYSDATETIME(), finalizationStatus = 'Error'
                WHERE idAutomationRun = {id_ejecucion}
            """
            datosEjecucion(sql_error)
            escribirLog(
                f"Error en automatización {NOMBRE_BANCO}: {str(e)}", id_ejecucion, "ERROR", "FIN")
            
            # Ejecutar BAT final en caso de error
            LogManager.escribir_log("INFO", "🔧 Ejecutando proceso final de emergencia...")
            SubprocesoManager.ejecutar_bat_final()

        return False

    finally:
        # Detener timeout manager
        timeout_manager.stop()

        tiempo_total = formatear_tiempo_ejecucion(
            datetime.now() - inicio_ejecucion)
        LogManager.escribir_log(
            "INFO", f"Tiempo total de ejecución: {tiempo_total}")
        LogManager.escribir_log("INFO", "=" * 60)


if __name__ == "__main__":
    try:
        # Verificar si se solicita modo manual
        modo_manual = False
        if len(sys.argv) > 1:
            if sys.argv[1] in ['--manual', '-m', 'manual']:
                modo_manual = True
                LogManager.escribir_log(
                    "INFO", "🔧 Modo manual activado: Procesando archivos desde carpeta de descargas")
        
        if modo_manual:
            # Procesar archivos manualmente
            exito = procesar_archivos_manuales()
            if exito:
                LogManager.escribir_log(
                    "SUCCESS", f"Procesamiento manual {NOMBRE_BANCO} finalizado exitosamente")
                sys.exit(0)
            else:
                LogManager.escribir_log(
                    "ERROR", f"Procesamiento manual {NOMBRE_BANCO} finalizado con errores")
                sys.exit(1)
        else:
            # Ejecutar proceso normal
            exito = main()
            if exito:
                LogManager.escribir_log(
                    "SUCCESS", f"Robot {NOMBRE_BANCO} finalizado exitosamente")
                sys.exit(0)
            else:
                LogManager.escribir_log(
                    "ERROR", f"Robot {NOMBRE_BANCO} finalizado con errores")
                sys.exit(1)
    except KeyboardInterrupt:
        LogManager.escribir_log(
            "WARNING", f"Robot {NOMBRE_BANCO} interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        LogManager.escribir_log(
            "ERROR", f"Error fatal en robot {NOMBRE_BANCO}: {str(e)}")
        sys.exit(1)
