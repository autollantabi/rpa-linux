
# -*- coding: utf-8 -*-
"""
BANCO PICHINCHA - AUTOMATIZACIÓN COMPLETA OPTIMIZADA
Incluye medidas anti-detección de bots y descarga de CSVs
"""
from datetime import datetime, date, timedelta
import json
import re
import time
import threading
import signal
from functools import wraps
import sys
import os
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
    RUTAS_CONFIG
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
        os._exit(1)  # Salida forzada sin cleanup

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
# 12 minutos 30 seg (12.5 * 60 = 750 segundos)
timeout_manager = TimeoutManager(750)


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
NOMBRE_BANCO = "Banco Pichincha"

URLS = {
    'login': "https://bancaempresas.pichincha.com/",
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


def tomar_screenshot(page, nombre):
    """Toma un screenshot y lo guarda"""
    try:
        ruta_screenshots = os.path.join(RUTAS_CONFIG['logs'], "screenshots")
        os.makedirs(ruta_screenshots, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ruta_archivo = os.path.join(ruta_screenshots, f"{nombre}_{timestamp}.png")
        page.screenshot(path=ruta_archivo)
        LogManager.escribir_log("SUCCESS", f"Screenshot guardado: {ruta_archivo}")
        return ruta_archivo
    except Exception as e:
        LogManager.escribir_log("WARNING", f"Error tomando screenshot: {str(e)}")
        return None


def realizar_login_completo(page):
    """Realiza el login completo en Banco Pichincha"""
    try:
        LogManager.escribir_log("INFO", "Iniciando proceso de login")

        # Leer credenciales
        credenciales = LectorArchivos.leerCSV(
            RUTAS_CONFIG['credenciales_banco'],
            filtro_columna=0,
            valor_filtro="Banco Pichincha"
        )
        
        if not credenciales or len(credenciales) == 0:
            raise Exception("No se pudieron leer las credenciales de Banco Pichincha")
        
        credenciales = credenciales[0]
        usuario = credenciales[1]
        password = credenciales[2]

        # Navegar a la página
        LogManager.escribir_log("INFO", f"Navegando a: {URLS['login']}")
        page.goto(URLS['login'])
        EsperasInteligentes.esperar_carga_pagina(page)
        tomar_screenshot(page, "pagina_login_cargada")

        # Escribir credenciales usando selectores que proporcionaste
        LogManager.escribir_log("INFO", "Escribiendo credenciales")
        ComponenteInteraccion.escribirComponente(
            page,
            "//input[@id='signInName']",
            usuario,
            descripcion="usuario"
        )
        ComponenteInteraccion.escribirComponente(
            page,
            "//input[@id='password']",
            password,
            descripcion="password"
        )
        tomar_screenshot(page, "credenciales_ingresadas")
        
        LogManager.escribir_log("INFO", "Haciendo clic en botón login")
        ComponenteInteraccion.clickComponente(
            page,
            "//button[@id='continue']",
            descripcion="botón login"
        )
        tomar_screenshot(page, "despues_clic_login_0s")
        EsperasInteligentes.esperar_con_loader_simple(2, "Esperando después del login")
        tomar_screenshot(page, "despues_clic_login_2s")

        # Manejar código de seguridad
        LogManager.escribir_log("INFO", "Esperando código de seguridad...")

        # Obtener código del correo usando la función simplificada
        codigo = CorreoManager.obtener_codigo_correo(
            asunto="Codigo de Seguridad",  # Asunto específico de Pichincha
        )

        if not codigo:
            raise Exception("No se pudo obtener el código de seguridad del correo")

        if codigo and re.fullmatch(r"^\d{6}$", codigo):
            LogManager.escribir_log("SUCCESS", f"Código válido recibido: {codigo}")

            ComponenteInteraccion.escribirComponente(
                page,
                "input[formcontrolname='userCode']",
                codigo,
                descripcion="código seguridad"
            )
            tomar_screenshot(page, "codigo_seguridad_ingresado")
            
            ComponenteInteraccion.clickComponente(
                page,
                "#kt_login_signin_submit1",
                descripcion="validar código"
            )
            tomar_screenshot(page, "despues_clic_validar_codigo")

            # Manejar diálogos posteriores
            EsperasInteligentes.esperar_con_loader_simple(2, "Procesando código de seguridad")

            # Manejo de diálogos opcionales con selectores robustos
            ComponenteInteraccion.clickComponenteOpcional(
                page,
                "//button[contains(text(), 'OK')] | //button[.//span[contains(text(), 'OK')]] | //button[@mat-dialog-close and contains(., 'OK')]",
                descripcion="botón OK",
                intentos=1,
                timeout=2000
            )

            EsperasInteligentes.esperar_con_loader_simple(1, "Esperando diálogos")

            ComponenteInteraccion.clickComponente(
                page,
                "//button[.//span[contains(text(), 'No')]]",
                descripcion="botón No guardar sesión",
            )

            LogManager.escribir_log("SUCCESS", "Login completado exitosamente")
            tomar_screenshot(page, "login_completado")
            return True

        raise Exception("No se pudo completar el proceso de login")

    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error en login: {str(e)}")
        tomar_screenshot(page, "error_login")
        return False

# ==================== FUNCIONES DE NAVEGACIÓN ====================


def navegar_a_movimientos(page):
    """Navega a la página de movimientos/consulta de cuentas a través del menú"""
    try:
        LogManager.escribir_log("INFO", "Navegando a página de movimientos a través del menú...")

        EsperasInteligentes.esperar_carga_pagina(page)
        EsperasInteligentes.esperar_con_loader_simple(5, "Esperando carga de página principal")
        tomar_screenshot(page, "pagina_principal_cargada")

        ComponenteInteraccion.clickComponenteOpcional(
            page,
            "//a[contains(text(), 'Aceptar')]",
            descripcion="botón Aceptar mensaje",
            intentos=2,
            timeout=2000
        )

        # PASO 1: Hacer clic en "Banca Empresas"
        LogManager.escribir_log("INFO", "Paso 1: Haciendo clic en 'Banca Empresas'")

        selector_banca_empresas = "//span[contains(text(), 'Banca Empresas')]"
        banca_empresas_encontrado = False

        if ComponenteInteraccion.esperarElemento(page, selector_banca_empresas, timeout=5000, descripcion=f"Botón Banca Empresas)"):
            if ComponenteInteraccion.clickComponente(page, selector_banca_empresas, descripcion="Banca Empresas"):
                banca_empresas_encontrado = True

        if not banca_empresas_encontrado:
            raise Exception("No se encontró el menú 'Banca Empresas'")
        
        tomar_screenshot(page, "despues_clic_banca_empresas")

        # Esperar que se expanda el menú de Banca Empresas
        EsperasInteligentes.esperar_con_loader_simple(1, "Esperando expansión de menú Banca Empresas")

        # PASO 2: Hacer clic en "Cuentas"
        LogManager.escribir_log("INFO", "Paso 2: Haciendo clic en 'Cuentas'")

        selector_cuentas = "//a[contains(@ng-click, 'AbrirModuloClick')][contains(., 'Cuentas')]"

        cuentas_encontrado = False

        if ComponenteInteraccion.esperarElemento(page, selector_cuentas, timeout=5000, descripcion=f"Botón Cuentas"):
            if ComponenteInteraccion.clickComponente(page, selector_cuentas, descripcion="módulo Cuentas"):
                cuentas_encontrado = True

        if not cuentas_encontrado:
            raise Exception("No se encontró el módulo 'Cuentas'")
        
        tomar_screenshot(page, "despues_clic_cuentas")

        # Esperar que se expanda el submenú de Cuentas
        EsperasInteligentes.esperar_con_loader_simple(1, "Esperando expansión de submenú Cuentas")

        # PASO 3: Hacer clic en "Movimientos"
        LogManager.escribir_log("INFO", "Paso 3: Haciendo clic en 'Movimientos'")

        selector_movimientos = "//a[@href='#/trans/BVE/Cuentas/ESTADOCUENTA']"

        movimientos_encontrado = False

        if ComponenteInteraccion.esperarElemento(page, selector_movimientos, timeout=5000, descripcion=f"Botón Movimientos"):
            if ComponenteInteraccion.clickComponente(page, selector_movimientos, descripcion="Movimientos"):
                movimientos_encontrado = True

        if not movimientos_encontrado:
            raise Exception("No se encontró la opción 'Movimientos'")
        
        tomar_screenshot(page, "pagina_movimientos_cargada")
        return True

    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error navegando a movimientos: {str(e)}")
        tomar_screenshot(page, "error_navegacion_movimientos")
        return False

# ==================== FUNCIONES DE DESCARGA ====================


@with_timeout_check
def obtener_y_descargar_csvs(page, id_ejecucion):
    """
    Obtiene las empresas disponibles y descarga los CSVs para cada una
    """
    try:
        LogManager.escribir_log("INFO", "Obteniendo y procesando empresas...")

        # Esperar carga de página
        EsperasInteligentes.esperar_carga_pagina(page)

        # Selector específico del select de empresas
        selector_empresas = "//div[@data-ng-show='!easyfiltros.busquedaEmpresaHabilitada']//select[@id='seleccionEmpresaCombo']"

        # Usar la función genérica para obtener opciones
        opciones_data = ComponenteInteraccion.obtener_opciones_select(
            page, selector_empresas, "select empresas")

        if not opciones_data:
            LogManager.escribir_log("ERROR", "No se pudieron obtener las opciones de empresas")
            return False

        empresas_procesadas = 0

        # Procesar cada empresa
        for i, opcion_data in enumerate(opciones_data):
            texto_empresa = opcion_data['text']
            valor_empresa = opcion_data['value']

            # Filtrar opciones vacías o de placeholder
            if not texto_empresa or texto_empresa in ["Seleccione", "-- Seleccione --", ""]:
                LogManager.escribir_log("DEBUG", f"Saltando opción vacía: '{texto_empresa}'")
                continue

            tiempo_transcurrido = formatear_tiempo_ejecucion(timeout_manager.get_elapsed_time())
            print("=" * 125)
            LogManager.escribir_log("INFO", f"======= Empresa {i+1}/{len(opciones_data)} - Tiempo: {tiempo_transcurrido} =======")
            escribirLog(f"Iniciando consulta para empresa: {texto_empresa}", id_ejecucion, "Information", "Consulta Empresa")

            try:
                # Seleccionar empresa usando la función común
                if ComponenteInteraccion.seleccionar_opcion_select(page, selector_empresas, texto_empresa, "selector empresas"):
                    tomar_screenshot(page, f"empresa_{texto_empresa.replace(' ', '_')}_seleccionada")
                    # Procesar la empresa seleccionada
                    if descargar_csv_empresa(page, texto_empresa, id_ejecucion):
                        empresas_procesadas += 1
                        LogManager.escribir_log("SUCCESS", f"{texto_empresa} procesada exitosamente")
                        escribirLog(f"Empresa {texto_empresa} completada", id_ejecucion, "Information", "Empresa Completada")
                    else:
                        LogManager.escribir_log("ERROR", f"Error procesando empresa: {texto_empresa}")
                        escribirLog(f"Error procesando empresa: {texto_empresa}", id_ejecucion, "Error", "Error Empresa")
                else:
                    LogManager.escribir_log("ERROR", f"No se pudo seleccionar empresa: {texto_empresa}")
                    escribirLog(f"Error seleccionando empresa: {texto_empresa}", id_ejecucion, "Error", "Error Selección")

            except Exception as e:
                error_msg = f"Error procesando empresa {texto_empresa}: {str(e)}"
                LogManager.escribir_log("ERROR", error_msg)
                escribirLog(error_msg, id_ejecucion, "Error", "Error Empresa")
                continue

        LogManager.escribir_log("SUCCESS", f"Procesadas {empresas_procesadas} empresas exitosamente")
        return empresas_procesadas > 0

    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error en obtener y seleccionar empresas: {str(e)}")
        return False


@with_timeout_check
def descargar_csv_empresa(page, nombre_empresa, id_ejecucion):
    """Descarga el CSV para una empresa individual"""
    try:
        LogManager.escribir_log("INFO", f"Descargando CSV para empresa: {nombre_empresa}")

        # Hacer clic en botón procesar cambio empresa
        ComponenteInteraccion.clickComponente(
            page,
            "//button[.//span[contains(text(),' Consultar ')]]",
            descripcion="botón procesar cambio empresa",
            intentos=1,
            timeout=5000
        )
        esperarConLoaderSimple(1, f"Esperando formulario de empresa: {nombre_empresa}")

        # Configurar fechas de consulta
        fecha_desde_config = ConfiguracionManager.leer_configuracion(
            RUTAS_CONFIG['configuraciones'], "Fecha desde"
        )
        fecha_hasta_config = ConfiguracionManager.leer_configuracion(
            RUTAS_CONFIG['configuraciones'], "Fecha hasta"
        )

        if not fecha_desde_config or not fecha_hasta_config:
            hoy = date.today()
            ayer = hoy - timedelta(days=1)
            fecha_desde = ayer.strftime("%d/%m/%Y")
            fecha_hasta = hoy.strftime("%d/%m/%Y")
        else:
            fecha_desde = fecha_desde_config[1]
            fecha_hasta = fecha_hasta_config[1]

        # Configurar tipo de consulta
        selector_tipo_consulta = "//select[@data-ng-model='frmItem.tipoConsulta']"
        if not ComponenteInteraccion.seleccionar_opcion_select(
            page, selector_tipo_consulta, "Movimientos por rango de fecha", "tipo de consulta"
        ):
            LogManager.escribir_log("ERROR", "No se pudo configurar el tipo de consulta")
            return False

        LogManager.escribir_log("INFO", f"Configurando fechas: {fecha_desde} - {fecha_hasta}")

        # Escribir fecha desde
        ComponenteInteraccion.escribirComponente(
            page, "//input[@name='desde']", fecha_desde, descripcion="fecha desde"
        )
        # Escribir fecha hasta
        ComponenteInteraccion.escribirComponente(
            page, "//input[@name='hasta']", fecha_hasta, descripcion="fecha hasta"
        )
        # Escribir paginado
        ComponenteInteraccion.escribirComponente(
            page, "//input[@name='paginado']", "100", descripcion="paginado hasta"
        )

        tomar_screenshot(page, f"empresa_{nombre_empresa.replace(' ', '_')}_fechas_configuradas")

        # Hacer clic en botón consultar movimientos
        ComponenteInteraccion.clickComponente(
            page,
            "//button[@data-ng-click='inicializarValoresBusquedaMasDatos(); ejecutarClick()']",
            descripcion="botón procesar consulta movimientos empresa",
            intentos=2,
            timeout=3000
        )

        # Descargar el CSV
        selector_excel = "//a[@data-ng-click=\"exportar('excel')\"]"
        EsperasInteligentes.esperar_con_loader_simple(10, f"Esperando datos para {nombre_empresa}")
        
        # Descargar el CSV
        ruta_archivo = ComponenteInteraccion.esperarDescarga(
            page, selector_excel, timeout=20000, descripcion="descarga de movimientos",
            adicional=nombre_empresa.replace(' ', '_'))

        if ruta_archivo:
            LogManager.escribir_log("SUCCESS", f"CSV descargado para {nombre_empresa}: {ruta_archivo}")
            
            # Mover el archivo a la carpeta de Pichincha
            ruta_pichincha = RUTAS_CONFIG['pichincha']
            os.makedirs(ruta_pichincha, exist_ok=True)
            nombre_archivo = os.path.basename(ruta_archivo)
            ruta_final = os.path.join(ruta_pichincha, nombre_archivo)
            import shutil
            shutil.move(ruta_archivo, ruta_final)  # Use shutil.move for cross-device compatibility
            LogManager.escribir_log("INFO", f"CSV movido a: {ruta_final}")
            
            return True
        else:
            LogManager.escribir_log("ERROR", "No se pudo descargar el CSV")
            return False

    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error descargando CSV para {nombre_empresa}: {str(e)}")
        return False

# ==================== FUNCIÓN PRINCIPAL ====================


def main():
    """Función principal"""
    id_ejecucion = None
    playwright_manager = None

    try:
        # Obtener ID de ejecución
        id_ejecucion = obtenerIDEjecucion()

        LogManager.iniciar_proceso(
            NOMBRE_BANCO, id_ejecucion, f"Automatización Pichincha - ID: {id_ejecucion}")

        # Registrar inicio en BD
        sql_inicio = f"""
            INSERT INTO {DATABASE_RUNS} (idAutomationRun, processName, startDate, finalizationStatus)
            VALUES ({id_ejecucion}, 'Automatización-{NOMBRE_BANCO}', SYSDATETIME(), 'Running')
        """
        datosEjecucion(sql_inicio)
        escribirLog("Inicio automatización", id_ejecucion, "Information", "Inicio")

        # Inicializar Playwright
        LogManager.escribir_log("INFO", "Iniciando Playwright...")
        playwright_manager = PlaywrightManager(
            headless=True,  # Modo headless para servidor
            download_path=RUTAS_CONFIG['descargas'],
            timeout=60000
        )
        playwright, browser, context, page = playwright_manager.iniciar_navegador()
        
        # Add anti-detection scripts
        LogManager.escribir_log("INFO", "Aplicando medidas anti-detección...")
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            delete navigator.__proto__.webdriver;
            
            window.chrome = {
                runtime: {},
                loadTimes: () => {},
                csi: () => {}
            };
            
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            Object.defineProperty(navigator, 'plugins', {
                get: () => ({
                    0: { type: 'application/pdf' },
                    length: 1
                }),
            });
            
            Object.defineProperty(navigator, 'mimeTypes', {
                get: () => ({
                    0: { type: 'application/pdf' },
                    length: 1
                }),
            });
            
            Object.defineProperty(navigator, 'languages', {
                get: () => ['es-ES', 'es', 'en-US', 'en'],
            });
            
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) return 'Google Inc.';
                if (parameter === 37446) return 'ANGLE (NVIDIA GeForce GTX 1080 Ti Direct3D11 vs_5_0 ps_5_0)';
                return getParameter(parameter);
            };
            
            Object.defineProperty(screen, 'availWidth', { get: () => 1920 });
            Object.defineProperty(screen, 'availHeight', { get: () => 1040 });
            Object.defineProperty(screen, 'width', { get: () => 1920 });
            Object.defineProperty(screen, 'height', { get: () => 1080 });
            Object.defineProperty(screen, 'colorDepth', { get: () => 24 });
            Object.defineProperty(screen, 'pixelDepth', { get: () => 24 });
            
            Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
            Object.defineProperty(navigator, 'productSub', { get: () => '20030107' });
            Object.defineProperty(navigator, 'vendor', { get: () => 'Google Inc.' });
            Object.defineProperty(navigator, 'vendorSub', { get: () => '' });
        """)

        # Realizar login completo
        if not realizar_login_completo(page):
            raise Exception("No se pudo completar el login")

        # Navegar a movimientos
        if not navegar_a_movimientos(page):
            raise Exception("No se pudo navegar a la página de movimientos")

        # Obtener y descargar CSVs
        exitoso = obtener_y_descargar_csvs(page, id_ejecucion)

        # Actualizar estado en BD
        estado_final = "Completed" if exitoso else "Failed"
        sql_fin = f"""
            UPDATE {DATABASE_RUNS}
            SET endDate = SYSDATETIME(), finalizationStatus = '{estado_final}'
            WHERE idAutomationRun = {id_ejecucion}
        """
        datosEjecucion(sql_fin)

        mensaje_final = "Automatización completada exitosamente" if exitoso else "Automatización falló"
        LogManager.escribir_log("SUCCESS" if exitoso else "ERROR", mensaje_final)

        LogManager.finalizar_proceso(NOMBRE_BANCO, exito=exitoso, descripcion=mensaje_final)
        return exitoso

    except Exception as e:
        error_msg = f"Error en proceso principal: {str(e)}"
        LogManager.escribir_log("ERROR", error_msg)

        if id_ejecucion:
            sql_error = f"""
                UPDATE {DATABASE_RUNS}
                SET endDate = SYSDATETIME(), finalizationStatus = 'Failed'
                WHERE idAutomationRun = {id_ejecucion}
            """
            datosEjecucion(sql_error)
            escribirLog(error_msg, id_ejecucion, "Error", "Error Fatal")

        LogManager.finalizar_proceso(NOMBRE_BANCO, exito=False, descripcion=error_msg)
        return False

    finally:
        if playwright_manager:
            try:
                playwright_manager.cerrar_navegador()
            except:
                pass


if __name__ == "__main__":
    try:
        resultado = main()
        if resultado:
            LogManager.escribir_log("SUCCESS", "=== AUTOMATIZACIÓN COMPLETADA EXITOSAMENTE ===")
        else:
            LogManager.escribir_log("ERROR", "=== AUTOMATIZACIÓN FALLO ===")
    except Exception as e:
        LogManager.escribir_log("ERROR", f"Error crítico en ejecución: {str(e)}")
    finally:
        LogManager.escribir_log("INFO", "=== FIN DE EJECUCIÓN ===")
