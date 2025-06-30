# -*- coding: utf-8 -*-
"""
Módulo de componentes comunes para automatización bancaria con Playwright
Centraliza todas las funciones de interacción, lectura de archivos y logs
"""

import os
import csv
import time
import subprocess
import json
import sys
import re
import imaplib
import email
import pyodbc
import openpyxl
import pandas as pd
from datetime import datetime, date, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ==================== ARCHIVOS ====================================


RUTAS_CONFIG = {
    'credenciales_banco': "/home/administrador/configBancos/config/credencialesBanco.csv",
    'credenciales_correo': "/home/administrador/configBancos/config/credencialesCorreo.csv",
    'credenciales_bd': "/home/administrador/configBancos/config/credencialesDB.csv",
    'configuraciones': "/home/administrador/configBancos/config/configuraciones.csv",
    'rutas': "/home/administrador/configBancos/config/rutas.csv",
    'descargas': "/home/administrador/configBancos/descargas",
    'logs': "/home/administrador/configBancos/logs",
    'bolivariano': "/home/administrador/configBancos/Bolivariano",
    'bat_final': "/home/administrador/Escritorio/UNION_BANCOS_0.1/UNION_BANCOS/UNION_BANCOS_run.sh"
}

# ==================== COMPONENTES DE NAVEGADOR ====================


class PlaywrightManager:
    """Administrador central de Playwright"""

    def __init__(self, headless=True, download_path=None, timeout=30000):
        self.headless = headless
        self.download_path = download_path
        self.timeout = timeout
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def iniciar_navegador(self):
        """Inicia un navegador con Playwright"""
        self.playwright = sync_playwright().start()

        # Configuraciones específicas para Linux
        browser_args = [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--disable-web-security',
            '--disable-features=VizDisplayCompositor',
            '--window-size=1920,1080',
            '--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]

        if self.headless:
            browser_args.extend([
                '--disable-extensions',
                '--disable-plugins',
                '--disable-images',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding'
            ])

        # Configurar opciones del navegador
        browser_options = {
            'headless': self.headless,
            'args': browser_args,
        }

        self.browser = self.playwright.chromium.launch(**browser_options)

        # Crear contexto con configuraciones específicas
        context_options = {
            'viewport': {'width': 1920, 'height': 1080},
            'user_agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'java_script_enabled': True,
            'accept_downloads': True
        }

        # Configurar descargas si se especifica
        if self.download_path:
            context_options['accept_downloads'] = True

        self.context = self.browser.new_context(**context_options)
        self.page = self.context.new_page()

        # Configurar timeout más alto para headless
        timeout = self.timeout * 2 if self.headless else self.timeout
        self.page.set_default_timeout(timeout)
        self.page.set_default_navigation_timeout(timeout)

        return self.playwright, self.browser, self.context, self.page

    def cerrar_navegador(self):
        """Cierra el navegador y Playwright"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

# ==================== COMPONENTES DE INTERACCIÓN ====================


class ComponenteInteraccion:
    """Clase para manejar interacciones con elementos web"""

    @staticmethod
    def clickComponente(page, selector, intentos=5, timeout=30000, descripcion="elemento"):
        """
        Hace clic en un elemento usando Playwright

        Args:
            page: Página de Playwright
            selector: Selector CSS o XPath
            intentos: Número de intentos
            timeout: Timeout en milisegundos
            descripcion: Descripción del elemento para logs

        Returns:
            bool: True si el clic fue exitoso
        """
        for intento in range(intentos):
            try:
                # Esperar que el elemento sea visible y clickeable
                page.wait_for_selector(
                    selector, timeout=timeout, state='visible')

                # Verificar si está deshabilitado
                if page.is_disabled(selector):
                    LogManager.escribir_log(
                        "INFO", f"{descripcion} está deshabilitado. Intento {intento + 1}/{intentos}")
                    time.sleep(2)
                    continue

                # Scroll al elemento si es necesario
                page.locator(selector).scroll_into_view_if_needed()

                # Hacer clic
                page.click(selector)
                LogManager.escribir_log(
                    "SUCCESS", f"Clic exitoso en {descripcion} (intento {intento + 1})")
                return True

            except PlaywrightTimeoutError:
                LogManager.escribir_log(
                    "WARNING", f"Timeout esperando {descripcion}. Intento {intento + 1}/{intentos}")
            except Exception as e:
                LogManager.escribir_log(
                    "ERROR", f"Error al hacer clic en {descripcion}: {str(e)}")

            if intento < intentos - 1:
                time.sleep(1)  # Espera entre intentos

        LogManager.escribir_log(
            "ERROR", f"No se pudo hacer clic en {descripcion} después de {intentos} intentos")
        return False

    @staticmethod
    def escribirComponente(page, selector, valor, intentos=5, timeout=15000, descripcion="campo"):
        """
        Escribe en un campo de texto usando Playwright

        Args:
            page: Página de Playwright
            selector: Selector CSS o XPath
            valor: Valor a escribir
            intentos: Número de intentos
            timeout: Timeout en milisegundos
            descripcion: Descripción del campo para logs

        Returns:
            bool: True si la escritura fue exitosa
        """
        for intento in range(intentos):
            try:
                page.wait_for_selector(
                    selector, timeout=timeout, state='visible')
                page.fill(selector, "")  # Limpiar campo
                page.fill(selector, valor)  # Escribir valor

                LogManager.escribir_log(
                    "SUCCESS", f"Escritura exitosa en {descripcion}: '{valor}' (intento {intento + 1})")
                return True

            except PlaywrightTimeoutError:
                LogManager.escribir_log(
                    "WARNING", f"Timeout esperando {descripcion}. Intento {intento + 1}/{intentos}")
            except Exception as e:
                LogManager.escribir_log(
                    "ERROR", f"Error al escribir en {descripcion}: {str(e)}")

            if intento < intentos - 1:
                time.sleep(1)

        LogManager.escribir_log(
            "ERROR", f"No se pudo escribir en {descripcion} después de {intentos} intentos")
        return False

    @staticmethod
    def leerComponente(page, selector, intentos=5, timeout=15000, descripcion="elemento"):
        """
        Lee el texto de un elemento usando Playwright

        Args:
            page: Página de Playwright
            selector: Selector CSS o XPath
            intentos: Número de intentos
            timeout: Timeout en milisegundos
            descripcion: Descripción del elemento para logs

        Returns:
            str: Texto del elemento o cadena vacía si falla
        """
        for intento in range(intentos):
            try:
                page.wait_for_selector(
                    selector, timeout=timeout, state='visible')
                texto = page.text_content(selector)

                LogManager.escribir_log(
                    "SUCCESS", f"Lectura exitosa de {descripcion}: '{texto}' (intento {intento + 1})")
                return texto.strip() if texto else ""

            except PlaywrightTimeoutError:
                LogManager.escribir_log(
                    "WARNING", f"Timeout esperando {descripcion}. Intento {intento + 1}/{intentos}")
            except Exception as e:
                LogManager.escribir_log(
                    "ERROR", f"Error al leer {descripcion}: {str(e)}")

            if intento < intentos - 1:
                time.sleep(1)

        LogManager.escribir_log(
            "ERROR", f"No se pudo leer {descripcion} después de {intentos} intentos")
        return ""

    @staticmethod
    def leerValorInput(page, selector, intentos=5, timeout=15000, descripcion="input"):
        """
        Lee el valor de un campo input usando Playwright

        Args:
            page: Página de Playwright
            selector: Selector CSS o XPath
            intentos: Número de intentos
            timeout: Timeout en milisegundos
            descripcion: Descripción del input para logs

        Returns:
            str: Valor del input o cadena vacía si falla
        """
        for intento in range(intentos):
            try:
                page.wait_for_selector(
                    selector, timeout=timeout, state='visible')
                valor = page.input_value(selector)

                LogManager.escribir_log(
                    "SUCCESS", f"Lectura de valor exitosa de {descripcion}: '{valor}' (intento {intento + 1})")
                return valor

            except PlaywrightTimeoutError:
                LogManager.escribir_log(
                    "WARNING", f"Timeout esperando {descripcion}. Intento {intento + 1}/{intentos}")
            except Exception as e:
                LogManager.escribir_log(
                    "ERROR", f"Error al leer valor de {descripcion}: {str(e)}")

            if intento < intentos - 1:
                time.sleep(1)

        LogManager.escribir_log(
            "ERROR", f"No se pudo leer valor de {descripcion} después de {intentos} intentos")
        return ""

    @staticmethod
    def esperarElemento(page, selector, timeout=30000, estado='visible', descripcion="elemento"):
        """
        Espera a que aparezca un elemento

        Args:
            page: Página de Playwright
            selector: Selector CSS o XPath
            timeout: Timeout en milisegundos
            estado: Estado a esperar ('visible', 'attached', 'hidden')
            descripcion: Descripción del elemento para logs

        Returns:
            bool: True si el elemento apareció
        """
        try:
            page.wait_for_selector(selector, timeout=timeout, state=estado)
            # LogManager.escribir_log(
            #     "SUCCESS", f"{descripcion} apareció correctamente")
            return True
        except PlaywrightTimeoutError:
            LogManager.escribir_log(
                "ERROR", f"Timeout esperando {descripcion}")
            return False
        except Exception as e:
            LogManager.escribir_log(
                "ERROR", f"Error esperando {descripcion}: {str(e)}")
            return False

    @staticmethod
    def esperarDescarga(page, selector_boton, timeout=60000, descripcion="descarga", adicional=""):
        """
        Espera y maneja una descarga

        Args:
            page: Página de Playwright
            selector_boton: Selector del botón de descarga
            timeout: Timeout en milisegundos
            descripcion: Descripción de la descarga para logs

        Returns:
            str: Ruta del archivo descargado o None si falla
        """
        try:
             # PASO 1: Verificar que el elemento existe y es visible
            if not ComponenteInteraccion.esperarElemento(page, selector_boton, timeout=timeout//3, descripcion=f"botón {descripcion}"):
                LogManager.escribir_log(
                    "ERROR", f"Elemento {descripcion} no encontrado")
                return None

            # PASO 2: Scroll al elemento
            try:
                elemento_locator = page.locator(selector_boton).first
                elemento_locator.scroll_into_view_if_needed()
                page.wait_for_timeout(1000)
            except Exception as e:
                LogManager.escribir_log(
                    "WARNING", f"Error posicionando elemento: {str(e)}")

            # PASO 3: Esperar que sea clickeable
            try:
                # XPath
                page.wait_for_function(f"""
                    () => {{
                        const xpath = "{selector_boton.replace('"', '\\"')}";
                        const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                        const elemento = result.singleNodeValue;

                        if (!elemento) return false;

                        const rect = elemento.getBoundingClientRect();
                        const visible = rect.width > 0 && rect.height > 0;
                        const enabled = !elemento.disabled && !elemento.hasAttribute('disabled') && !elemento.classList.contains('disabled');

                        return visible && enabled;
                    }}
                """, timeout=15000)


                LogManager.escribir_log("SUCCESS", f"Elemento {descripcion} confirmado como clickeable")
            except Exception as e:
                LogManager.escribir_log("WARNING", f"No se pudo verificar clickeabilidad: {str(e)}")
                EsperasInteligentes.esperar_con_loader_simple(2, "Esperando estabilización del elemento")
            

            with page.expect_download(timeout=timeout) as download_info:
                page.click(selector_boton)

            download = download_info.value

            # Obtener la ruta temporal original
            ruta_temporal = download.path()

            # Usar el nombre sugerido tal como viene
            nombre_archivo = download.suggested_filename
            nombre = nombre_archivo.split('.')[0]  # Nombre sin extensión
            extension = nombre_archivo.split('.')[-1]  # Extensión del archivo

            if adicional:
                # Si hay un adicional, agregarlo al nombre del archivo
                nombre_archivo = f"{nombre}_{adicional}.{extension}"

            ruta_descarga = os.path.join(
                RUTAS_CONFIG['descargas'], nombre_archivo)

            # Guardar archivo con el nombre original
            download.save_as(ruta_descarga)

            # ELIMINAR EL ARCHIVO TEMPORAL
            try:
                if os.path.exists(ruta_temporal):
                    os.remove(ruta_temporal)
            except Exception as e:
                LogManager.escribir_log(
                    "WARNING", f"No se pudo eliminar archivo temporal: {str(e)}")

            LogManager.escribir_log(
                "SUCCESS", f"{descripcion} completada: {ruta_descarga}")
            return ruta_descarga

        except PlaywrightTimeoutError:
            LogManager.escribir_log("ERROR", f"Timeout en {descripcion}")
            return None
        except Exception as e:
            LogManager.escribir_log(
                "ERROR", f"Error en {descripcion}: {str(e)}")
            return None

    @staticmethod
    def clickComponenteOpcional(page, selector, descripcion="elemento opcional", intentos=3, timeout=2000):
        """
        Hace clic en un elemento opcional (que puede o no aparecer)
        Los logs son menos alarmantes ya que es normal que no aparezca

        Args:
            page: Página de Playwright
            selector: Selector CSS o XPath
            descripcion: Descripción del elemento para logs
            intentos: Número de intentos (por defecto 3 para elementos opcionales)
            timeout: Timeout en milisegundos (por defecto 2000 para elementos opcionales)

        Returns:
            bool: True si el clic fue exitoso, False si el elemento no está presente
        """
        for intento in range(intentos):
            try:
                # Esperar que el elemento sea visible y clickeable
                page.wait_for_selector(
                    selector, timeout=timeout, state='visible')

                # Verificar si está deshabilitado
                if page.is_disabled(selector):
                    LogManager.escribir_log(
                        "INFO", f"{descripcion} está deshabilitado. Intento {intento + 1}/{intentos}")
                    time.sleep(1)
                    continue

                # Scroll al elemento si es necesario
                page.locator(selector).scroll_into_view_if_needed()

                # Hacer clic
                page.click(selector)
                LogManager.escribir_log(
                    "SUCCESS", f"Clic exitoso en {descripcion} (elemento opcional encontrado)")
                return True

            except PlaywrightTimeoutError:
                # Para elementos opcionales, el timeout no es un error grave
                LogManager.escribir_log(
                    "INFO", f"{descripcion} no encontrado. Intento {intento + 1}/{intentos}")
            except Exception as e:
                LogManager.escribir_log(
                    "WARNING", f"Error al hacer clic en {descripcion}: {str(e)}")

            if intento < intentos - 1:
                time.sleep(0.5)  # Espera más corta para elementos opcionales

        # Para elementos opcionales, no encontrarlos no es un error
        LogManager.escribir_log(
            "INFO", f"{descripcion} no apareció (esto es normal para elementos opcionales)")
        return False

    @staticmethod
    def obtener_opciones_select(page, selector, descripcion="select"):
        """
        Función genérica para obtener todas las opciones de cualquier select - SOLO XPATH
        """
        try:

            # Verificar que es XPath
            if not (selector.startswith("//") or selector.startswith("/")):
                LogManager.escribir_log("ERROR", f"Selector debe ser XPath: {selector}")
                return []

            # Esperar que el select esté disponible
            if not ComponenteInteraccion.esperarElemento(page, selector, timeout=15000, descripcion=descripcion):
                LogManager.escribir_log("ERROR", f"No se encontró el {descripcion}")
                return []

            # Scroll al elemento por si está fuera de vista
            page.locator(selector).scroll_into_view_if_needed()
            page.wait_for_timeout(1000)

            # Esperar que tenga opciones cargadas - SOLO XPATH
            try:
                xpath_escaped = selector.replace("'", "\\'").replace('"', '\\"')
                page.wait_for_function(f"""
                    () => {{
                        const xpath = '{xpath_escaped}';
                        const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                        const select = result.singleNodeValue;
                        return select && select.options && select.options.length > 0;
                    }}
                """, timeout=10000)
            except Exception as e:
                LogManager.escribir_log("WARNING", f"Error esperando opciones en {descripcion}: {str(e)}")

            # Obtener todas las opciones usando JavaScript con XPath
            script_opciones = f"""
            () => {{
                const xpath = "{selector.replace('"', '\\"')}";
                const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                const select = result.singleNodeValue;
                
                if (!select) return [];
                
                return Array.from(select.options).map((option, index) => ({{
                    index: index,
                    value: option.value,
                    text: option.textContent.trim(),
                    selected: option.selected
                }}));
            }}
            """

            opciones_data = page.evaluate(script_opciones)

            if not opciones_data:
                LogManager.escribir_log("WARNING", f"No se encontraron opciones en {descripcion}")
                return []


            return opciones_data

        except Exception as e:
            LogManager.escribir_log("ERROR", f"Error obteniendo opciones de {descripcion}: {str(e)}")
            return []

    @staticmethod
    def seleccionar_opcion_select(page, selector, valor_objetivo, descripcion="select"):
        """
        Función genérica para seleccionar una opción en cualquier select

        Args:
            page: Página de Playwright
            selector: Selector CSS/XPath del select
            valor_objetivo: Valor o texto de la opción a seleccionar
            descripcion: Descripción para logs

        Returns:
            bool: True si la selección fue exitosa, False en caso contrario
        """
        try:
            # LogManager.escribir_log("INFO", f"Seleccionando opción en {descripcion}: {valor_objetivo}")

            # Verificar que es XPath
            if not (selector.startswith("//") or selector.startswith("/")):
                LogManager.escribir_log("ERROR", f"Selector debe ser XPath: {selector}")
                return False
                 # Usar la función genérica para obtener opciones
            opciones_data = ComponenteInteraccion.obtener_opciones_select(page, selector, descripcion)
            
            for opcion in opciones_data:
                estado = " (SELECCIONADA)" if opcion.get('selected', False) else ""

            if not opciones_data:
                LogManager.escribir_log("ERROR", f"No se pudieron obtener opciones del {descripcion}")
                return False

            # Buscar la opción objetivo por texto exacto
            valor_a_seleccionar = None
            opcion_encontrada = None   

            for opcion in opciones_data:
                if opcion['text'] == valor_objetivo:
                    valor_a_seleccionar = opcion['value']
                    opcion_encontrada = opcion
                    break

            if valor_a_seleccionar is None:
                LogManager.escribir_log("ERROR", f"No se encontró la opción '{valor_objetivo}' en {descripcion}")
                # Log de opciones disponibles para debug
                opciones_disponibles = [f"'{opt['text']}'" for opt in opciones_data]
                LogManager.escribir_log("DEBUG", f"Opciones disponibles: {', '.join(opciones_disponibles)}")
                return False

            # Obtener el locator del select
            select_locator = page.locator(selector).first

            # MÉTODO 1: Seleccionar por valor usando Playwright
            try:
                select_locator.select_option(value=valor_a_seleccionar)
                page.wait_for_timeout(2000)
                return True
            except Exception as e:
                LogManager.escribir_log("WARNING", f"Método Playwright falló: {str(e)}")

            # MÉTODO 2: JavaScript como fallback - SOLO XPATH
            try:
                script_seleccion = f"""
                () => {{
                    const xpath = "{selector.replace('"', '\\"')}";
                    const valor = "{valor_a_seleccionar}";
                    const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                    const select = result.singleNodeValue;
                    
                    if (select) {{
                        select.value = valor;
                        select.dispatchEvent(new Event('focus'));
                        select.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        select.dispatchEvent(new Event('blur'));
                        return select.value === valor;
                    }}
                    return false;
                }}
                """

                resultado = page.evaluate(script_seleccion)
                
                if resultado:
                    page.wait_for_timeout(2000)
                    return True
                else:
                    LogManager.escribir_log("ERROR", f"Falló selección por JavaScript")
                    return False
                    
            except Exception as e:
                LogManager.escribir_log("ERROR", f"Error en JavaScript: {str(e)}")
                return False
        except Exception as e:
            LogManager.escribir_log(
                "ERROR", f"Error seleccionando opción en {descripcion}: {str(e)}")
            return False

    @staticmethod
    def buscar_opcion_por_texto(opciones_data, texto_busqueda, busqueda_parcial=False):
        """
        Busca una opción específica en una lista de opciones
        """
        try:
            opciones_encontradas = []
            
            for opcion in opciones_data:
                if busqueda_parcial:
                    if texto_busqueda.lower() in opcion['text'].lower():
                        opciones_encontradas.append(opcion)
                else:
                    if opcion['text'] == texto_busqueda:
                        opciones_encontradas.append(opcion)
            
            return opciones_encontradas
            
        except Exception as e:
            LogManager.escribir_log("ERROR", f"Error buscando opción por texto: {str(e)}")
            return []

    @staticmethod
    def obtener_opcion_seleccionada(page, selector, descripcion="select"):
        """
        Obtiene la opción actualmente seleccionada de un select - SOLO XPATH
        """
        try:
            # Verificar que es XPath
            if not (selector.startswith("//") or selector.startswith("/")):
                LogManager.escribir_log("ERROR", f"Selector debe ser XPath: {selector}")
                return None

            opciones_data = ComponenteInteraccion.obtener_opciones_select(page, selector, descripcion)
            
            for opcion in opciones_data:
                if opcion.get('selected', False):
                    LogManager.escribir_log("INFO", f"Opción seleccionada en {descripcion}: '{opcion['text']}'")
                    return opcion
            
            LogManager.escribir_log("WARNING", f"No se encontró opción seleccionada en {descripcion}")
            return None
            
        except Exception as e:
            LogManager.escribir_log("ERROR", f"Error obteniendo opción seleccionada: {str(e)}")
            return None

    @staticmethod
    def seleccionar_opcion_por_indice(page, selector, indice, descripcion="select"):
        """
        Selecciona una opción por su índice - SOLO XPATH
        """
        try:
            LogManager.escribir_log("INFO", f"Seleccionando opción por índice {indice} en {descripcion}")

            # Verificar que es XPath
            if not (selector.startswith("//") or selector.startswith("/")):
                LogManager.escribir_log("ERROR", f"Selector debe ser XPath: {selector}")
                return False

            # Obtener opciones primero
            opciones_data = ComponenteInteraccion.obtener_opciones_select(page, selector, descripcion)
            
            if not opciones_data or indice >= len(opciones_data):
                LogManager.escribir_log("ERROR", f"Índice {indice} fuera de rango en {descripcion}")
                return False

            opcion_objetivo = opciones_data[indice]
            valor_a_seleccionar = opcion_objetivo['value']

            # Usar JavaScript para seleccionar por índice
            script_seleccion = f"""
            () => {{
                const xpath = "{selector.replace('"', '\\"')}";
                const indice = {indice};
                const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                const select = result.singleNodeValue;
                
                if (select && select.options && select.options[indice]) {{
                    select.selectedIndex = indice;
                    select.dispatchEvent(new Event('focus'));
                    select.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    select.dispatchEvent(new Event('blur'));
                    return true;
                }}
                return false;
            }}
            """
            
            resultado = page.evaluate(script_seleccion)
            
            if resultado:
                LogManager.escribir_log("SUCCESS", f"Selección exitosa por índice {indice}: '{opcion_objetivo['text']}'")
                page.wait_for_timeout(2000)
                return True
            else:
                LogManager.escribir_log("ERROR", f"Falló selección por índice {indice}")
                return False
                
        except Exception as e:
            LogManager.escribir_log("ERROR", f"Error seleccionando por índice en {descripcion}: {str(e)}")
            return False

    @staticmethod
    def seleccionar_opcion_iframe(iframe, selector, index=None, value=None, text=None, descripcion="elemento"):
        """Selecciona una opción en un select dentro de iframe"""
        try:
            locator = iframe.locator(selector)

            if index is not None:
                locator.select_option(index=index)
            elif value is not None:
                locator.select_option(value=value)
            elif text is not None:
                locator.select_option(label=text)
            else:
                raise Exception("Debe especificar index, value o text")

            LogManager.escribir_log(
                "SUCCESS", f"✅ Opción seleccionada en {descripcion}")
            return True

        except Exception as e:
            LogManager.escribir_log(
                "ERROR", f"❌ Error seleccionando opción en {descripcion}: {str(e)}")
            return False

    @staticmethod
    def hacer_clic_iframe_con_validacion(iframe, selector, descripcion="elemento", timeout=10000):
        """Hace clic en un elemento dentro de iframe con validación"""
        try:
            locator = iframe.locator(selector)
            locator.wait_for(timeout=timeout)
            locator.click()

            LogManager.escribir_log(
                "SUCCESS", f"✅ Clic exitoso en {descripcion}")
            return True

        except Exception as e:
            LogManager.escribir_log(
                "ERROR", f"❌ Error haciendo clic en {descripcion}: {str(e)}")
            return False


# ==================== ESPERAS INTELIGENTES ====================


class EsperasInteligentes:
    """Clase para manejar esperas específicas sin time.sleep"""

    @staticmethod
    def esperar_carga_pagina(page, timeout=30000):
        """Espera a que la página termine de cargar completamente"""
        try:
            page.wait_for_load_state("networkidle", timeout=timeout)
            LogManager.escribir_log("SUCCESS", "Página cargada completamente")
            return True
        except PlaywrightTimeoutError:
            LogManager.escribir_log(
                "WARNING", "Timeout esperando carga completa de página")
            return False

    @staticmethod
    def esperar_condicion_javascript(page, condicion, timeout=30000, descripcion="condición"):
        """
        Espera a que se cumpla una condición JavaScript

        Args:
            page: Página de Playwright
            condicion: Código JavaScript que debe retornar True
            timeout: Timeout en milisegundos
            descripcion: Descripción de la condición para logs

        Returns:
            bool: True si la condición se cumple
        """
        try:
            page.wait_for_function(condicion, timeout=timeout)
            LogManager.escribir_log(
                "SUCCESS", f"Condición cumplida: {descripcion}")
            return True
        except PlaywrightTimeoutError:
            LogManager.escribir_log(
                "ERROR", f"Timeout esperando condición: {descripcion}")
            return False

    @staticmethod
    def esperar_elemento_desaparecer(page, selector, timeout=30000, descripcion="elemento"):
        """Espera a que un elemento desaparezca"""
        try:
            page.wait_for_selector(selector, timeout=timeout, state='hidden')
            # LogManager.escribir_log(
            #     "SUCCESS", f"{descripcion} desapareció correctamente")
            return True
        except PlaywrightTimeoutError:
            LogManager.escribir_log(
                "WARNING", f"Timeout esperando que desaparezca {descripcion}")
            return False

    @staticmethod
    def esperar_con_loader(segundos, descripcion="Esperando", mostrar_progreso=True):
        """
        Espera el tiempo especificado mostrando un contador visual en consola

        Args:
            segundos: Número de segundos a esperar
            descripcion: Descripción de lo que se está esperando
            mostrar_progreso: Si mostrar el progreso visual (True por defecto)
        """
        import sys

        if not mostrar_progreso:
            # Si no se quiere mostrar progreso, usar time.sleep normal
            time.sleep(segundos)
            return

        try:
            for i in range(segundos):
                tiempo_restante = segundos - i

                # Crear barra de progreso visual
                progreso = int((i / segundos) * 20)  # Barra de 20 caracteres
                barra = "█" * progreso + "░" * (20 - progreso)
                porcentaje = int((i / segundos) * 100)

                # Crear timestamp actual para cada actualización
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Crear mensaje completo con formato de LogManager
                mensaje_completo = f"[{LogManager._banco_actual}] [{timestamp}] [LOADING] {descripcion}: [{barra}] {porcentaje}% - {tiempo_restante}s restantes"

                # Mostrar en consola con \r para sobrescribir la línea
                print(f"\r{mensaje_completo}", end="", flush=True)

                time.sleep(1)

            # Completar al 100% con timestamp final
            timestamp_final = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            barra_completa = "█" * 20
            mensaje_final = f"[{LogManager._banco_actual}] [{timestamp_final}] [LOADING] {descripcion}: [{barra_completa}] 100% - Completado"
            
            print(f"\r{mensaje_final}", flush=True)


        except KeyboardInterrupt:
            print(f"\n⚠️ Espera interrumpida por el usuario")
            LogManager.escribir_log("WARNING", f"{descripcion} interrumpido por el usuario")
            raise
        except Exception as e:
            print(f"\n❌ Error durante la espera: {str(e)}")
            LogManager.escribir_log("ERROR", f"Error en espera: {str(e)}")
            # Continuar con time.sleep normal como fallback
            time.sleep(max(0, segundos - i))

    @staticmethod
    def esperar_con_loader_simple(segundos, descripcion="Esperando"):
        """
        Versión simple que solo muestra contador numérico

        Args:
            segundos: Número de segundos a esperar
            descripcion: Descripción de lo que se está esperando
        """
        import sys

        try:
            for i in range(segundos, 0, -1):
                # Crear timestamp actual para cada actualización
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Crear mensaje con formato completo incluyendo banco y timestamp
                mensaje_completo = f"[{LogManager._banco_actual}] [{timestamp}] [LOADING] {descripcion}: {i} segundos restantes..."
                
                # Mostrar con \r para reemplazar la línea
                print(f"\r{mensaje_completo}", end="", flush=True)
                time.sleep(1)

            # Mensaje final con timestamp actualizado
            timestamp_final = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            mensaje_final = f"[{LogManager._banco_actual}] [{timestamp_final}] [LOADING] {descripcion}: Completado"
            
            # Limpiar línea y mostrar mensaje final
            print(f"\r{mensaje_final}", flush=True)

        except KeyboardInterrupt:
            print(f"\n⚠️ Espera interrumpida por el usuario")
            LogManager.escribir_log(
                "WARNING", f"{descripcion} interrumpido por el usuario")
            raise

    @staticmethod
    def esperar_elemento_iframe_con_retry(iframe, selector, descripcion="elemento", timeout=30000, reintentos=3):
        """Espera un elemento en iframe con reintentos"""
        for intento in range(reintentos):
            try:
                LogManager.escribir_log(
                    "DEBUG", f"🔍 Esperando {descripcion} (intento {intento + 1}/{reintentos})")

                locator = iframe.locator(selector)
                locator.wait_for(timeout=timeout // reintentos)

                LogManager.escribir_log(
                    "SUCCESS", f"✅ {descripcion} encontrado")
                return True

            except Exception as e:
                if intento < reintentos - 1:
                    LogManager.escribir_log(
                        "WARNING", f"⚠️ Intento {intento + 1} fallido para {descripcion}, reintentando...")
                    time.sleep(1)
                else:
                    LogManager.escribir_log(
                        "ERROR", f"❌ No se encontró {descripcion} después de {reintentos} intentos: {str(e)}")

        return False

# ==================== GESTIÓN DE ARCHIVOS ====================


class LectorArchivos:
    """Clase para leer diferentes tipos de archivos"""

    @staticmethod
    def leerCSV(ruta_archivo, filtro_columna=None, valor_filtro=None):
        """
        Lee un archivo CSV con filtro opcional

        Args:
            ruta_archivo: Ruta al archivo CSV
            filtro_columna: Índice de columna para filtrar (opcional)
            valor_filtro: Valor a buscar en la columna de filtro

        Returns:
            list: Lista de filas del CSV
        """
        try:
            data = []
            with open(ruta_archivo, 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                for row in reader:
                    if filtro_columna is not None and valor_filtro is not None:
                        if len(row) > filtro_columna and row[filtro_columna] == valor_filtro:
                            data.append(row)
                    else:
                        data.append(row)

            # LogManager.escribir_log(
            #     "SUCCESS", f"CSV leído correctamente: {ruta_archivo} ({len(data)} filas)")
            return data

        except Exception as e:
            LogManager.escribir_log(
                "ERROR", f"Error leyendo CSV {ruta_archivo}: {str(e)}")
            return []

    @staticmethod
    def leerExcel(ruta_archivo, hoja=0, data_only=True):
        """
        Lee un archivo Excel

        Args:
            ruta_archivo: Ruta al archivo Excel
            hoja: Índice o nombre de la hoja (por defecto 0)
            data_only: Solo datos, sin fórmulas

        Returns:
            openpyxl.Worksheet: Hoja de Excel cargada
        """
        try:
            wb = openpyxl.load_workbook(ruta_archivo, data_only=data_only)

            if isinstance(hoja, int):
                ws = wb.worksheets[hoja]
            else:
                ws = wb[hoja]

            contenido = []
            for fila in ws.iter_rows(values_only=True):
                # Convertir a lista y manejar valores None
                fila_lista = []
                for celda in fila:
                    fila_lista.append(celda if celda is not None else "")
                contenido.append(fila_lista)

            # Cerrar el workbook para liberar memoria
            wb.close()

            LogManager.escribir_log(
                "SUCCESS", f"Excel leído correctamente: {ruta_archivo}")
            return contenido

        except Exception as e:
            LogManager.escribir_log(
                "ERROR", f"Error leyendo Excel {ruta_archivo}: {str(e)}")
            return None

    @staticmethod
    def leerTxt(ruta_archivo, encoding='utf-8'):
        """
        Lee un archivo de texto

        Args:
            ruta_archivo: Ruta al archivo de texto
            encoding: Codificación del archivo

        Returns:
            str: Contenido del archivo
        """
        try:
            with open(ruta_archivo, 'r', encoding=encoding) as file:
                contenido = file.read()

            LogManager.escribir_log(
                "SUCCESS", f"Archivo de texto leído correctamente: {ruta_archivo}")
            return contenido

        except Exception as e:
            LogManager.escribir_log(
                "ERROR", f"Error leyendo archivo de texto {ruta_archivo}: {str(e)}")
            return ""

    @staticmethod
    def obtener_ultimo_archivo_descargado(carpeta, extension=None):
        """
        Obtiene el último archivo descargado de una carpeta

        Args:
            carpeta: Ruta de la carpeta
            extension: Extensión de archivo a buscar (opcional)

        Returns:
            str: Ruta del último archivo descargado
        """
        try:
            archivos = []
            for archivo in os.listdir(carpeta):
                if extension is None or archivo.endswith(extension):
                    ruta_completa = os.path.join(carpeta, archivo)
                    archivos.append(
                        (ruta_completa, os.path.getmtime(ruta_completa)))

            if not archivos:
                LogManager.escribir_log(
                    "WARNING", f"No se encontraron archivos en {carpeta}")
                return None

            # Ordenar por fecha de modificación (más reciente primero)
            archivos.sort(key=lambda x: x[1], reverse=True)
            ultimo_archivo = archivos[0][0]

            LogManager.escribir_log(
                "SUCCESS", f"Último archivo encontrado: {ultimo_archivo}")
            return ultimo_archivo

        except Exception as e:
            LogManager.escribir_log(
                "ERROR", f"Error buscando último archivo en {carpeta}: {str(e)}")
            return None

# ==================== GESTIÓN DE LOGS ====================


class LogManager:
    """Administrador de logs por banco"""

    _instance = None
    _banco_actual = "GENERAL"
    _ruta_logs = RUTAS_CONFIG['logs']
    _id_ejecucion = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LogManager, cls).__new__(cls)
            cls._instance._inicializar()
        return cls._instance

    def _inicializar(self):
        """Inicializa el sistema de logs"""
        # Crear carpeta de logs si no existe
        if not os.path.exists(self._ruta_logs):
            os.makedirs(self._ruta_logs)

    @classmethod
    def configurar_banco(cls, nombre_banco):
        """Configura el banco actual para los logs"""
        cls._banco_actual = nombre_banco.upper()

    @classmethod
    def configurar_id_ejecucion(cls, id_ejecucion):
        """Configura el id de ejecución para los logs"""
        cls._id_ejecucion = str(id_ejecucion)

    @classmethod
    def escribir_log(cls, nivel, mensaje, incluir_timestamp=True):
        """
        Escribe un log

        Args:
            nivel: Nivel del log (SUCCESS, INFO, WARNING, ERROR)
            mensaje: Mensaje del log
            incluir_timestamp: Si incluir timestamp en el mensaje
        """
        # Asegurar que la instancia existe
        if cls._instance is None:
            cls()

        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S") if incluir_timestamp else ""
        fecha_archivo = datetime.now().strftime("%Y-%m-%d")

        # Crear nombre del archivo de log
        if cls._id_ejecucion:
            nombre_archivo = f"{cls._id_ejecucion}_{cls._banco_actual}_{fecha_archivo}.log"
        else:
            nombre_archivo = f"{cls._banco_actual}_{fecha_archivo}.log"
            
        ruta_archivo = os.path.join(cls._ruta_logs, nombre_archivo)

        # Formatear mensaje
        if incluir_timestamp:
            linea_log = f"[{timestamp}] [{nivel}] {mensaje}\n"
        else:
            linea_log = f"[{nivel}] {mensaje}\n"

        try:
            # Escribir al archivo
            with open(ruta_archivo, 'a', encoding='utf-8') as archivo_log:
                archivo_log.write(linea_log)

            # También imprimir en consola
            print(f"[{cls._banco_actual}] {linea_log.strip()}")

        except Exception as e:
            print(f"Error escribiendo log: {e}")

    @classmethod
    def iniciar_proceso(cls, banco, idEjecucion, descripcion="Proceso iniciado"):
        """Inicia un nuevo proceso de banco"""
        cls.configurar_banco(banco)
        cls.configurar_id_ejecucion(idEjecucion)
        cls.escribir_log("INFO", "=" * 80)
        cls.escribir_log("INFO", f"INICIANDO PROCESO: {banco}")
        cls.escribir_log("INFO", descripcion)
        cls.escribir_log("INFO", "=" * 80)

    @classmethod
    def finalizar_proceso(cls, banco, exito=True, descripcion=""):
        """Finaliza un proceso de banco"""
        cls.configurar_banco(banco)

        if exito:
            cls.escribir_log(
                "SUCCESS", f"PROCESO COMPLETADO EXITOSAMENTE: {banco}")
        else:
            cls.escribir_log("ERROR", f"PROCESO FALLÓ: {banco}")

        if descripcion:
            cls.escribir_log("INFO", descripcion)

        cls.escribir_log("INFO", "=" * 60)

    @classmethod
    def obtener_ruta_log_actual(cls):
        """Obtiene la ruta del archivo de log actual"""
        fecha_archivo = datetime.now().strftime("%Y-%m-%d")
        nombre_archivo = f"{cls._banco_actual}_{fecha_archivo}.log"
        return os.path.join(cls._ruta_logs, nombre_archivo)

# ==================== GESTIÓN DE BASE DE DATOS ====================


class BaseDatos:
    """Clase para manejar operaciones con base de datos SQL Server"""

    @staticmethod
    def conexionBD(servidor, database, usuario, password):
        """
        Establece conexión con base de datos SQL Server

        Args:
            servidor: Servidor SQL Server
            database: Nombre de la base de datos
            usuario: Usuario de la base de datos
            password: Contraseña de la base de datos

        Returns:
            tuple: (conexion, cursor) o (None, None) si falla
        """
        try:
            import pyodbc

            connection_string = f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={servidor};DATABASE={database};UID={usuario};PWD={password};TrustServerCertificate=yes"
            conn = pyodbc.connect(connection_string)
            cursor = conn.cursor()

            # LogManager.escribir_log(
            #     "SUCCESS", f"Conexión exitosa a BD: {database} en {servidor}")
            return conn, cursor

        except Exception as e:
            LogManager.escribir_log(
                "ERROR", f"Error conectando a BD {database}: {str(e)}")
            return None, None

    @staticmethod
    def normalizar_fecha(fecha):
        """
        Convierte automáticamente cualquier tipo de fecha a string YYYY-MM-DD
        
        Args:
            fecha: Fecha en cualquier formato (datetime.date, datetime.datetime, str)
            
        Returns:
            str: Fecha en formato YYYY-MM-DD
        """
        try:
            if isinstance(fecha, date):
                # Convertir datetime.date o datetime.datetime a string YYYY-MM-DD
                return fecha.strftime("%Y-%m-%d")
            elif isinstance(fecha, str):
                # Si ya es string, verificar si necesita conversión
                if '/' in fecha:
                    # Convertir DD/MM/YYYY a YYYY-MM-DD
                    try:
                        fecha_obj = datetime.strptime(fecha, "%d/%m/%Y")
                        return fecha_obj.strftime("%Y-%m-%d")
                    except ValueError:
                        # Si no es DD/MM/YYYY, intentar otros formatos
                        try:
                            fecha_obj = datetime.strptime(fecha, "%Y-%m-%d")
                            return fecha_obj.strftime("%Y-%m-%d")
                        except ValueError:
                            return str(fecha)  # Devolver como string si no se puede convertir
                elif '-' in fecha and len(fecha) == 10:
                    # Ya está en formato YYYY-MM-DD
                    return fecha
                else:
                    return str(fecha)
            else:
                # Para cualquier otro tipo, convertir a string
                return str(fecha)
        except Exception as e:
            LogManager.escribir_log("WARNING", f"Error normalizando fecha {fecha}: {str(e)}")
            return str(fecha)

    @staticmethod
    def procesar_resultados_consulta(resultados):
        """
        Procesa automáticamente los resultados de una consulta, normalizando fechas
        
        Args:
            resultados: Lista de tuplas de resultados de la consulta
            
        Returns:
            list: Lista de tuplas con fechas normalizadas
        """
        try:
            resultados_procesados = []
            
            for fila in resultados:
                fila_procesada = []
                for columna in fila:
                    # Si es una fecha, normalizarla automáticamente
                    if isinstance(columna, date):
                        fila_procesada.append(BaseDatos.normalizar_fecha(columna))
                    else:
                        fila_procesada.append(columna)
                resultados_procesados.append(tuple(fila_procesada))
            
            return resultados_procesados
            
        except Exception as e:
            LogManager.escribir_log("WARNING", f"Error procesando resultados: {str(e)}")
            return resultados

    @staticmethod
    def consultarBD(query):
        """
        Ejecuta una consulta SELECT en la base de datos

        Args:
            query: Consulta SQL a ejecutar

        Returns:
            list: Resultados de la consulta o lista vacía si falla
        """
        conn = None
        cursor = None

        try:
            # Leer credenciales desde el archivo CSV
            credenciales = LectorArchivos.leerCSV(
                RUTAS_CONFIG["credenciales_bd"])
            credenciales = credenciales[0] if credenciales else []

            if len(credenciales) < 4:
                raise Exception("Credenciales incompletas para base de datos")

            conn, cursor = BaseDatos.conexionBD(
                credenciales[0],  # servidor
                credenciales[1],  # database
                credenciales[2],  # usuario
                credenciales[3]   # password
            )

            if not conn or not cursor:
                raise Exception(
                    "No se pudo establecer conexión a la base de datos")

            cursor.execute(query)
            resultados = cursor.fetchall()

            # PROCESAR AUTOMÁTICAMENTE LAS FECHAS
            resultados_normalizados = BaseDatos.procesar_resultados_consulta(resultados)

            return resultados_normalizados

        except Exception as e:
            LogManager.escribir_log("ERROR", f"Error en consulta BD: {str(e)}")
            return []

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def ejecutarSQL(query):
        """
        Ejecuta una consulta INSERT, UPDATE o DELETE en la base de datos

        Args:
            credenciales: Lista con [servidor, database, usuario, password]
            query: Consulta SQL a ejecutar

        Returns:
            bool: True si la ejecución fue exitosa
        """
        conn = None
        cursor = None

        try:
            # Leer credenciales desde el archivo CSV
            credenciales = LectorArchivos.leerCSV(
                RUTAS_CONFIG["credenciales_bd"])
            credenciales = credenciales[0] if credenciales else []

            if len(credenciales) < 4:
                raise Exception("Credenciales incompletas para base de datos")

            conn, cursor = BaseDatos.conexionBD(
                credenciales[0],  # servidor
                credenciales[1],  # database
                credenciales[2],  # usuario
                credenciales[3]   # password
            )

            if not conn or not cursor:
                raise Exception(
                    "No se pudo establecer conexión a la base de datos")

            cursor.execute(query)
            conn.commit()

            # LogManager.escribir_log("SUCCESS", f"Query ejecutado exitosamente")
            return True

        except Exception as e:
            LogManager.escribir_log("ERROR", f"Error ejecutando SQL: {str(e)}")
            if conn:
                conn.rollback()
            return False

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def insertarBD(query):
        """
        Inserta datos en la base de datos

        Args:
            credenciales: Lista con [servidor, database, usuario, password]
            query: Query INSERT a ejecutar

        Returns:
            bool: True si la inserción fue exitosa
        """

        return BaseDatos.ejecutarSQL(query)

    @staticmethod
    def verificarConexion(credenciales):
        """
        Verifica si se puede conectar a la base de datos

        Args:
            credenciales: Lista con [servidor, database, usuario, password]

        Returns:
            bool: True si la conexión es exitosa
        """
        conn = None
        cursor = None

        try:
            # Leer credenciales desde el archivo CSV
            credenciales = LectorArchivos.leerCSV(
                RUTAS_CONFIG["credenciales_bd"])
            credenciales = credenciales[0] if credenciales else []

            conn, cursor = BaseDatos.conexionBD(
                credenciales[0],  # servidor
                credenciales[1],  # database
                credenciales[2],  # usuario
                credenciales[3]   # password
            )

            if conn and cursor:
                # Ejecutar una consulta simple para verificar
                cursor.execute("SELECT 1")
                cursor.fetchone()
                return True

            return False

        except Exception as e:
            LogManager.escribir_log(
                "ERROR", f"Error verificando conexión BD: {str(e)}")
            return False

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

# ==================== GESTIÓN DE CORREO ====================


class CorreoManager:
    """Clase para manejar operaciones de correo IMAP"""

    @staticmethod
    def conectar_imap(carpeta="inbox", key='mail.maxximundo.com'):
        """
        Conecta a un servidor IMAP usando credenciales del archivo de configuración

        Args:
            carpeta: Carpeta a seleccionar (por defecto inbox)

        Returns:
            imaplib.IMAP4_SSL: Conexión IMAP o None si falla
        """
        try:
            import imaplib

            # Leer credenciales de correo desde el archivo de configuración
            credenciales_correo = LectorArchivos.leerCSV(
                RUTAS_CONFIG['credenciales_correo'],
                filtro_columna=0,  # Por servidor
                valor_filtro=key
            )

            if not credenciales_correo:
                raise Exception(
                    "No se encontraron credenciales de correo en el archivo de configuración")

            fila_correo = credenciales_correo[0]

            servidor = fila_correo[0]
            usuario = fila_correo[1]
            password = fila_correo[2]

            conexion = imaplib.IMAP4_SSL(servidor)
            conexion.login(usuario, password)
            conexion.select(carpeta)

            LogManager.escribir_log(
                "SUCCESS", f"Conexión IMAP exitosa a {servidor}")
            return conexion

        except Exception as e:
            LogManager.escribir_log(
                "ERROR", f"Error conectando IMAP: {str(e)}")
            return None

    @staticmethod
    def obtener_ultimo_correo(carpeta="inbox", key='mail.maxximundo.com'):
        """
        Obtiene el último correo de una cuenta usando credenciales del archivo de configuración

        Args:
            carpeta: Carpeta de correo

        Returns:
            email.message.Message: Mensaje de correo o None si falla
        """
        try:
            import imaplib
            import email

            conexion = CorreoManager.conectar_imap(carpeta, key)
            if not conexion:
                return None

            # Buscar todos los correos
            _, correo_ids = conexion.search(None, 'ALL')

            if not correo_ids[0]:
                LogManager.escribir_log("WARNING", "No se encontraron correos")
                conexion.logout()
                return None

            # Obtener el ID del último correo
            ultimo_correo_id = correo_ids[0].split()[-1]

            # Obtener el correo completo
            _, correo_data = conexion.fetch(ultimo_correo_id, '(RFC822)')

            # Parsear el correo
            mensaje = email.message_from_bytes(correo_data[0][1])

            conexion.logout()
            LogManager.escribir_log(
                "SUCCESS", "Último correo obtenido exitosamente")

            return mensaje

        except Exception as e:
            LogManager.escribir_log(
                "ERROR", f"Error obteniendo último correo: {str(e)}")
            return None

    @staticmethod
    def decodificar_contenido_correo(correo):
        """
        Decodifica el contenido de un correo electrónico

        Args:
            correo: Objeto email.message.Message

        Returns:
            str: Contenido decodificado del correo
        """
        try:
            contenido = ""

            if correo.is_multipart():
                for parte in correo.walk():
                    if parte.get_content_type() == "text/html":
                        payload = parte.get_payload(decode=True)
                        if payload:
                            contenido += payload.decode('utf-8',
                                                        errors='ignore')
            else:
                payload = correo.get_payload(decode=True)
                if payload:
                    contenido = payload.decode('utf-8', errors='ignore')

            LogManager.escribir_log(
                "SUCCESS", "Contenido de correo decodificado exitosamente")
            return contenido

        except Exception as e:
            LogManager.escribir_log(
                "ERROR", f"Error decodificando correo: {str(e)}")
            return ""

    @staticmethod
    def obtener_codigo_correo(asunto="Nuevo token", intentos=60, espera=1, key='mail.maxximundo.com'):
        """
        Obtiene un código de 6 dígitos de un correo electrónico específico
        usando credenciales del archivo de configuración

        Args:
            asunto: Asunto del correo a buscar
            intentos: Número de intentos
            espera: Segundos entre intentos
            key: Servidor de correo a buscar

        Returns:
            str: Código de 6 dígitos o None si no se encuentra
        """
        mail = None
        try:
            import imaplib
            import email
            import time
            import re

            LogManager.escribir_log(
                "INFO", f"Conectando al servidor de correo para obtener token con asunto: '{asunto}'...")

            # Leer credenciales de correo desde el archivo de configuración
            credenciales_correo = LectorArchivos.leerCSV(
                RUTAS_CONFIG['credenciales_correo'],
                filtro_columna=0,
                valor_filtro=key
            )

            if not credenciales_correo:
                # Fallback: usar primera fila
                credenciales_correo = LectorArchivos.leerCSV(
                    RUTAS_CONFIG['credenciales_correo'])
                if not credenciales_correo:
                    raise Exception("No se encontraron credenciales de correo")
                LogManager.escribir_log(
                    "INFO", "Usando primera fila de credenciales como fallback")

            fila_correo = credenciales_correo[0]

            if len(fila_correo) < 3:
                raise Exception("Credenciales de correo incompletas")

            servidor = fila_correo[0]
            correo = fila_correo[1]
            clave_correo = fila_correo[2]

            LogManager.escribir_log(
                "INFO", f"Conectando a {servidor} con usuario {correo}")

            # Conectar a IMAP
            mail = imaplib.IMAP4_SSL(servidor)
            mail.login(correo, clave_correo)
            mail.select("inbox")

            try:
                # Crear variantes del asunto para búsqueda más flexible
                variantes_asunto = [
                    asunto,  # Asunto exacto
                    asunto.replace("Código", "Codigo"),  # Sin acento
                    asunto.replace("código", "codigo"),  # Sin acento minúscula
                    asunto.replace("Nuevo token", "token"),  # Versión corta
                ]

                # Remover duplicados manteniendo orden
                variantes_asunto = list(dict.fromkeys(variantes_asunto))

                correos_marcados_total = 0

                for variante in variantes_asunto:
                    try:
                        # Buscar correos con esta variante del asunto
                        # Usar búsqueda sin comillas para mayor flexibilidad
                        search_command = f'SUBJECT "{variante}"'
                        result, data = mail.search(None, search_command)

                        if data and data[0]:
                            correo_ids = data[0].split()

                            # Solo marcar los últimos 5 correos con este asunto
                            ultimos_correos = correo_ids[-5:] if len(
                                correo_ids) > 5 else correo_ids

                            for email_id in ultimos_correos:
                                try:
                                    mail.store(email_id, '+FLAGS', '\\Seen')
                                    correos_marcados_total += 1
                                except Exception as e:
                                    LogManager.escribir_log(
                                        "DEBUG", f"Error marcando correo {email_id}: {str(e)}")

                    except Exception as e:
                        LogManager.escribir_log(
                            "DEBUG", f"Error buscando variante '{variante}': {str(e)}")
                        continue

            except Exception as e:
                LogManager.escribir_log(
                    "WARNING", f"Error marcando correos previos: {str(e)}")

             # BUCLE PRINCIPAL CON PROGRESO VISUAL
            LogManager.escribir_log("INFO", f"Buscando código de seguridad - Máximo {intentos} segundos...")

            for intento in range(intentos):
                try:
                    # MOSTRAR PROGRESO VISUAL EN LÍNEA
                    tiempo_restante = intentos - intento
                    progreso = int((intento / intentos) * 20)  # Barra de 20 caracteres
                    barra = "█" * progreso + "░" * (20 - progreso)
                    porcentaje = int((intento / intentos) * 100)
                    
                    # Mostrar en consola con \r para sobrescribir la línea
                    mensaje = f"\r🔍 Buscando código: [{barra}] {intento+1}/{intentos} intentos - {tiempo_restante}s restantes"
                    print(mensaje, end="", flush=True)

                    # Buscar correos no leídos con el asunto específico
                    codigo_encontrado = None

                    for variante in variantes_asunto:
                        try:
                            # Buscar correos no leídos con esta variante del asunto
                            search_command = f'(UNSEEN SUBJECT "{variante}")'
                            result, data = mail.search(None, search_command)

                            if not data or not data[0]:
                                continue

                            ids = data[0].split()

                            # Procesar correos del más reciente al más antiguo
                            for email_id in reversed(ids):
                                try:

                                    # Obtener el correo completo
                                    result, data = mail.fetch(
                                        email_id, "(RFC822)")

                                    if not data or not data[0] or not data[0][1]:
                                        continue

                                    mensaje = email.message_from_bytes(
                                        data[0][1])

                                    # Verificar asunto específicamente
                                    subject = mensaje.get("Subject", "")
                                    if subject:
                                        try:
                                            # Decodificar asunto
                                            decoded_subject = email.header.decode_header(subject)[
                                                0]
                                            if isinstance(decoded_subject[0], bytes):
                                                encoding = decoded_subject[1] or 'utf-8'
                                                subject = decoded_subject[0].decode(
                                                    encoding, errors='ignore')
                                            else:
                                                subject = str(
                                                    decoded_subject[0])
                                        except Exception as e:
                                            LogManager.escribir_log(
                                                "DEBUG", f"Error decodificando asunto: {str(e)}")
                                            subject = str(subject)

                                        # VERIFICACIÓN ESTRICTA DEL ASUNTO
                                        asunto_email_lower = subject.lower().strip()
                                        asunto_buscado_lower = asunto.lower().strip()
                                        variante_lower = variante.lower().strip()

                                        # Verificar coincidencia exacta o parcial del asunto
                                        coincide_asunto = (
                                            asunto_buscado_lower in asunto_email_lower or
                                            variante_lower in asunto_email_lower or
                                            asunto_email_lower in asunto_buscado_lower
                                        )

                                        if not coincide_asunto:
                                            continue

                                        print("/n")
                                        LogManager.escribir_log(
                                            "SUCCESS", f"✅ Correo con asunto correcto encontrado: '{subject}'")

                                    # Extraer contenido del correo
                                    cuerpo = ""

                                    try:
                                        if mensaje.is_multipart():
                                            for part in mensaje.walk():
                                                if part.get_content_type() in ["text/plain", "text/html"]:
                                                    try:
                                                        payload = part.get_payload(
                                                            decode=True)
                                                        if payload:
                                                            # Intentar decodificar con diferentes encodings
                                                            for encoding in ['utf-8', 'latin-1', 'ascii', 'cp1252']:
                                                                try:
                                                                    cuerpo = payload.decode(
                                                                        encoding)
                                                                    break
                                                                except (UnicodeDecodeError, LookupError):
                                                                    continue
                                                            else:
                                                                # Último recurso
                                                                cuerpo = payload.decode(
                                                                    'utf-8', errors='ignore')

                                                            if cuerpo.strip():
                                                                break
                                                    except Exception as e:
                                                        continue
                                        else:
                                            # Correo simple
                                            try:
                                                payload = mensaje.get_payload(
                                                    decode=True)
                                                if payload:
                                                    for encoding in ['utf-8', 'latin-1', 'ascii', 'cp1252']:
                                                        try:
                                                            cuerpo = payload.decode(
                                                                encoding)
                                                            break
                                                        except (UnicodeDecodeError, LookupError):
                                                            continue
                                                    else:
                                                        cuerpo = payload.decode(
                                                            'utf-8', errors='ignore')
                                            except Exception as e:
                                                continue

                                    except Exception as e:
                                        continue

                                    if not cuerpo.strip():
                                        continue

                                    # Buscar código de 6 dígitos
                                    patrones = [
                                        # Seguridad: 847797
                                        r'(?:seguridad|security)[\s:]*(\d{6})',
                                        # código: 123456
                                        r'(?:código|codigo|code|token|clave|otp)[\s:]*(\d{6})',
                                        # 123456 es su código
                                        r'(\d{6})[\s]*(?:es|is)[\s]*(?:su|your|el|the)?[\s]*(?:código|codigo|code|token)',
                                        # cualquier secuencia de 6 dígitos
                                        r'\b(\d{6})\b',
                                    ]

                                    for i, patron in enumerate(patrones):
                                        try:
                                            matches = re.findall(
                                                patron, cuerpo, re.IGNORECASE)
                                            if matches:
                                                for match in matches:
                                                    if isinstance(match, str) and len(match) == 6 and match.isdigit():
                                                        codigo_encontrado = match
                                                        break
                                                if codigo_encontrado:
                                                    break
                                        except Exception as e:
                                            continue

                                    if codigo_encontrado:
                                        # COMPLETAR BARRA AL 100% Y MOSTRAR ÉXITO
                                        barra_completa = "█" * 20
                                        mensaje_final = f"\r✅ Código encontrado: [{barra_completa}] {codigo_encontrado} - Encontrado en {intento+1}/{intentos} intentos"
                                        print(mensaje_final, flush=True)
                                        print()  # Nueva línea
                                        
                                        LogManager.escribir_log("SUCCESS", f"🎉 Código de seguridad obtenido: {codigo_encontrado}")
                                        mail.logout()
                                        return codigo_encontrado
                                    
                                except Exception as e:
                                    continue

                            # Si encontramos código, salir del bucle de variantes
                            if codigo_encontrado:
                                break

                        except Exception as e:
                            continue

                    # Si encontramos código, salir del bucle de intentos
                    if codigo_encontrado:
                        break

                except Exception as e:
                    pass

                # Esperar antes del siguiente intento
                if intento < intentos - 1:
                    time.sleep(espera)

            # MOSTRAR RESULTADO FINAL SI NO SE ENCONTRÓ
            barra_completa = "█" * 20
            mensaje_final = f"\r❌ Búsqueda completada: [{barra_completa}] 0/{intentos} - Código no encontrado"
            print(mensaje_final, flush=True)
            print()  # Nueva línea

            # Si llegamos aquí, no se encontró el código
            LogManager.escribir_log(
                "ERROR", f"❌ No se encontró código de seguridad con asunto '{asunto}' después de {intentos} segundos")
            return None

        except Exception as e:
            # Limpiar línea de progreso en caso de error
            print(f"\r❌ Error: {str(e)}" + " " * 50, flush=True)
            print()  # Nueva línea
            
            LogManager.escribir_log(
                "ERROR", f"❌ Error crítico obteniendo código del correo: {str(e)}")
            import traceback
            LogManager.escribir_log(
                "DEBUG", f"Stack trace: {traceback.format_exc()}")
            return None


# ==================== GESTIÓN DE CONFIGURACIONES ====================


class ConfiguracionManager:
    """Clase para manejar archivos de configuración"""

    @staticmethod
    def leer_configuracion(ruta_csv, clave_config):
        """
        Lee una configuración específica del archivo CSV

        Args:
            ruta_csv: Ruta al archivo CSV de configuraciones
            clave_config: Clave de configuración a buscar

        Returns:
            list: Fila de configuración o lista vacía si no se encuentra
        """
        try:
            datos = LectorArchivos.leerCSV(ruta_csv)

            for fila in datos:
                if len(fila) >= 1 and fila[0] == clave_config:
                    LogManager.escribir_log(
                        "SUCCESS", f"Configuración '{clave_config}' encontrada")
                    return fila

            LogManager.escribir_log(
                "WARNING", f"Configuración '{clave_config}' no encontrada")
            return []

        except Exception as e:
            LogManager.escribir_log(
                "ERROR", f"Error leyendo configuración '{clave_config}': {str(e)}")
            return []

    @staticmethod
    def actualizar_configuracion(ruta_csv, clave_config, nuevo_valor):
        """
        Actualiza una configuración en el archivo CSV

        Args:
            ruta_csv: Ruta al archivo CSV
            clave_config: Clave de la configuración a actualizar (ej: "Fecha desde")
            nuevo_valor: Nuevo valor para la configuración

        Returns:
            bool: True si la actualización fue exitosa
        """
        try:
            datos = LectorArchivos.leerCSV(ruta_csv)
            actualizado = False

            for i, fila in enumerate(datos):
                if len(fila) >= 2 and fila[0] == clave_config:
                    datos[i][1] = nuevo_valor
                    actualizado = True
                    break

            if actualizado:
                # Guardar cambios
                with open(ruta_csv, 'w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerows(datos)

                LogManager.escribir_log(
                    "SUCCESS", f"Configuración {clave_config} actualizada a: {nuevo_valor}")
                return True
            else:
                LogManager.escribir_log(
                    "WARNING", f"Configuración {clave_config} no encontrada")
                return False

        except Exception as e:
            LogManager.escribir_log(
                "ERROR", f"Error actualizando configuración {clave_config}: {str(e)}")
            return False

    @staticmethod
    def validar_archivos_configuracion(rutas_config):
        """
        Valida que todos los archivos de configuración existan

        Args:
            rutas_config: Diccionario con las rutas de configuración

        Returns:
            dict: Diccionario con el estado de cada archivo
        """
        resultados = {}

        for nombre, ruta in rutas_config.items():
            if ruta.endswith('.csv'):
                existe = os.path.exists(ruta)
                resultados[nombre] = existe

                if existe:
                    LogManager.escribir_log(
                        "SUCCESS", f"Archivo de configuración encontrado: {nombre}")
                else:
                    LogManager.escribir_log(
                        "ERROR", f"Archivo de configuración NO encontrado: {nombre} - {ruta}")
            else:
                # Para carpetas
                existe = os.path.exists(ruta)
                resultados[nombre] = existe

                if not existe:
                    try:
                        os.makedirs(ruta, exist_ok=True)
                        LogManager.escribir_log(
                            "SUCCESS", f"Carpeta creada: {nombre} - {ruta}")
                        resultados[nombre] = True
                    except Exception as e:
                        LogManager.escribir_log(
                            "ERROR", f"Error creando carpeta {nombre}: {str(e)}")

        return resultados

    @staticmethod
    def leer_configuraciones(ruta_csv, banco):
        """
        Lee configuraciones para un banco específico

        Args:
            ruta_csv: Ruta del archivo CSV
            banco: Nombre del banco a buscar

        Returns:
            list: Fila de configuración del banco
        """
        try:
            with open(ruta_csv, 'r', encoding='utf-8') as file:
                import csv
                reader = csv.reader(file)
                next(reader)  # Saltar encabezado
                for row in reader:
                    if row[0].strip().lower() == banco.strip().lower():
                        LogManager.escribir_log(
                            "SUCCESS", f"Configuración encontrada para banco: {banco}")
                        return row

            raise Exception(
                f"No se encontró configuración para el banco: {banco}")

        except Exception as e:
            LogManager.escribir_log(
                "ERROR", f"Error leyendo configuraciones para {banco}: {str(e)}")
            raise

    @staticmethod
    def leer_configuraciones_por_id(ruta_csv, id_busqueda):
        """
        Lee configuraciones por ID específico

        Args:
            ruta_csv: Ruta del archivo CSV
            id_busqueda: ID de configuración a buscar

        Returns:
            list: Fila de configuración del ID
        """
        try:
            with open(ruta_csv, 'r', encoding='utf-8') as file:
                import csv
                reader = csv.reader(file)
                next(reader)  # Saltar encabezado
                for row in reader:
                    if row[-1].strip() == id_busqueda.strip():
                        LogManager.escribir_log(
                            "SUCCESS", f"Configuración encontrada para ID: {id_busqueda}")
                        return row

            raise Exception(
                f"No se encontró configuración para el ID: {id_busqueda}")

        except Exception as e:
            LogManager.escribir_log(
                "ERROR", f"Error leyendo configuraciones para ID {id_busqueda}: {str(e)}")
            raise

    @staticmethod
    def actualizar_configuraciones_fecha():
        """Actualiza las configuraciones de fecha para la próxima ejecución"""
        try:
            LogManager.escribir_log(
                "INFO", "Actualizando configuraciones de fecha...")

            # Calcular nuevas fechas (hoy y mañana)
            hoy = date.today()
            ayer = hoy - timedelta(days=1)

            fecha_desde = ayer.strftime("%d/%m/%Y")  # Ayer
            fecha_hasta = hoy.strftime("%d/%m/%Y")   # Hoy

            # Actualizar configuraciones
            ConfiguracionManager.actualizar_configuracion(
                RUTAS_CONFIG['configuraciones'],
                "Fecha desde",
                fecha_desde
            )
            ConfiguracionManager.actualizar_configuracion(
                RUTAS_CONFIG['configuraciones'],
                "Fecha hasta",
                fecha_hasta
            )

            LogManager.escribir_log(
                "SUCCESS", f"Fechas actualizadas - Desde: {fecha_desde}, Hasta: {fecha_hasta}")
            return True

        except Exception as e:
            LogManager.escribir_log(
                "ERROR", f"Error actualizando configuraciones: {str(e)}")
            return False

# ==================== GESTIÓN DE SUBPROCESOS ====================


class SubprocesoManager:
    """Clase para manejar subprocesos de forma segura"""
    @staticmethod
    def ejecutar_bat_final():
        """Ejecuta el archivo BAT al finalizar el bot"""
        try:
            # Ruta al archivo BAT en el escritorio
            ruta_bat = RUTAS_CONFIG['bat_final']

            # Verificar si el archivo existe
            if not os.path.exists(ruta_bat):
                LogManager.escribir_log(
                    "WARNING", f"Archivo BAT no encontrado: {ruta_bat}")
                return False

            LogManager.escribir_log(
                "INFO", f"🔄 Ejecutando archivo BAT: {ruta_bat}")

            # Ejecutar el BAT y esperar a que termine
            resultado = subprocess.run(
                ruta_bat,
                shell=True,
                capture_output=False,  # No capturar output
                stdout=subprocess.DEVNULL,  # Suprimir stdout
                stderr=subprocess.DEVNULL,  # Suprimir stderr,
                timeout=300  # Timeout de 5 minutos
            )

            # Verificar el resultado
            if resultado.returncode == 0:
                LogManager.escribir_log(
                    "SUCCESS", "✅ Archivo BAT ejecutado exitosamente")

                return True
            else:
                LogManager.escribir_log(
                    "ERROR", f"❌ Error ejecutando BAT. Código: {resultado.returncode}")

                return False

        except subprocess.TimeoutExpired:
            LogManager.escribir_log(
                "ERROR", "❌ Timeout ejecutando archivo BAT (5 minutos)")
            return False
        except Exception as e:
            LogManager.escribir_log(
                "ERROR", f"❌ Error ejecutando archivo BAT: {str(e)}")
            return False

# ==================== EXPORTACIÓN DE FUNCIONES PRINCIPALES ====================

# Para mantener compatibilidad con código existente


def clickComponente(page, selector, intentos=5, timeout=30000, descripcion="elemento"):
    return ComponenteInteraccion.clickComponente(page, selector, intentos, timeout, descripcion)


def escribirComponente(page, selector, valor, intentos=5, timeout=15000, descripcion="campo"):
    return ComponenteInteraccion.escribirComponente(page, selector, valor, intentos, timeout, descripcion)


def leerComponente(page, selector, intentos=5, timeout=15000, descripcion="elemento"):
    return ComponenteInteraccion.leerComponente(page, selector, intentos, timeout, descripcion)


def leerValorInput(page, selector, intentos=5, timeout=15000, descripcion="input"):
    return ComponenteInteraccion.leerValorInput(page, selector, intentos, timeout, descripcion)


def esperarElemento(page, selector, timeout=30000, estado='visible', descripcion="elemento"):
    return ComponenteInteraccion.esperarElemento(page, selector, timeout, estado, descripcion)


def leerCSV(ruta_archivo, filtro_columna=None, valor_filtro=None):
    return LectorArchivos.leerCSV(ruta_archivo, filtro_columna, valor_filtro)


def leerExcel(ruta_archivo, hoja=0, data_only=True):
    return LectorArchivos.leerExcel(ruta_archivo, hoja, data_only)


def leerTxt(ruta_archivo, encoding='utf-8'):
    return LectorArchivos.leerTxt(ruta_archivo, encoding)


def escribirLog(nivel, mensaje):
    LogManager.escribir_log(nivel, mensaje)


def iniciar_playwright_navegador(headless=True, download_path=None, timeout=30000):
    manager = PlaywrightManager(headless, download_path, timeout)
    return manager.iniciar_navegador()


def cerrar_playwright_navegador(playwright, browser):
    if browser:
        browser.close()
    if playwright:
        playwright.stop()


def clickComponenteOpcional(page, selector, descripcion="elemento opcional", intentos=3, timeout=2000):
    return ComponenteInteraccion.clickComponenteOpcional(page, selector, descripcion, intentos, timeout)


def esperarConLoader(segundos, descripcion="Esperando", mostrar_progreso=True):
    return EsperasInteligentes.esperar_con_loader(segundos, descripcion, mostrar_progreso)


def esperarConLoaderSimple(segundos, descripcion="Esperando"):
    return EsperasInteligentes.esperar_con_loader_simple(segundos, descripcion)

# Funciones de base de datos


def consultarBD(query):
    return BaseDatos.consultarBD(query)


def ejecutarSQL(query):
    return BaseDatos.ejecutarSQL(query)


def insertarBD(query):
    return BaseDatos.insertarBD(query)


def verificarConexionBD(credenciales):
    return BaseDatos.verificarConexion(credenciales)

# Funciones de correo


def conectarIMAP(carpeta="inbox"):
    return CorreoManager.conectar_imap(carpeta)


def obtenerUltimoCorreo(carpeta="inbox"):
    return CorreoManager.obtener_ultimo_correo(carpeta)


def decodificarContenidoCorreo(correo):
    return CorreoManager.decodificar_contenido_correo(correo)

# Funciones de configuración


def leerConfiguracion(ruta_csv, clave_config):
    return ConfiguracionManager.leer_configuracion(ruta_csv, clave_config)


def actualizarConfiguracion(ruta_csv, id_config, nuevo_valor):
    return ConfiguracionManager.actualizar_configuracion(ruta_csv, id_config, nuevo_valor)


def validarArchivosConfiguracion(rutas_config):
    return ConfiguracionManager.validar_archivos_configuracion(rutas_config)
