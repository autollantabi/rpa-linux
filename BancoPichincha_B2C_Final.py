# -*- coding: utf-8 -*-
"""
BANCO PICHINCHA - AUTOMATIZACIÓN B2C: BYPASS DE SESIÓN Y MOVIMIENTO HUMANO
"""
from datetime import datetime
import time
import sys
import os
import random
from componentes_comunes import (
    PlaywrightManager,
    ComponenteInteraccion,
    EsperasInteligentes,
    LectorArchivos,
    RUTAS_CONFIG,
    esperarConLoaderSimple
)

# ==================== CONFIGURACIÓN GLOBAL ====================

NOMBRE_BANCO = "Banco Pichincha B2C"
# REVERTIR A URL DE AUTORIZACIÓN B2C (Necesaria para inicializar la sesión OAuth correctamente)
URL_LOGIN = "https://login.empresas.pichincha.com/account.empresas.pichincha.com/b2c_1a_businessbanking_signin/oauth2/v2.0/authorize?client_id=08d3b5d8-82d3-4098-9eaf-ec7c430ac63c&scope=openid%20https%3A%2F%2Flogin.empresas.pichincha.com%2Fbusinessbanking%2Fapi%2Faccess%20openid%20profile%20offline_access&redirect_uri=https%3A%2F%2Fbancaempresas.pichincha.com&client-request-id=019d1c2b-05e6-7f58-b954-f0b0ba83d63e&response_mode=fragment&response_type=code&x-client-SKU=msal.js.browser&x-client-VER=3.28.1&client_info=1&code_challenge=4G2SIQmywe7OHX5YQddNgxVYQfS1taH79RzgWWWmJ5Q&code_challenge_method=S256&nonce=019d1c2b-05e7-7041-aa2b-da9425dc4189&state=eyJpZCI6IjAxOWQxYzJiLTA1ZTYtNzQ5ZC04NzkyLTNiMDA3NDhhMzJkZSIsIm1ldGEiOnsiaW50ZXJhY3Rpb25TypeIjoicmVkaXJlY3QifX0%3D"

# ==================== UTILIDADES ====================

def escribir_log_terminal(mensaje, nivel="INFO"):
    """Imprime logs directamente en la terminal"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{nivel}] {mensaje}")

def simular_movimiento_mouse(page, target_locator):
    """Mueve el mouse por la pantalla de forma curva hacia el elemento"""
    try:
        box = target_locator.bounding_box()
        if not box: return
        
        target_x = box['x'] + box['width'] / 2
        target_y = box['y'] + box['height'] / 2
        
        # Iniciar desde posición aleatoria
        curr_x = random.randint(0, 800)
        curr_y = random.randint(0, 600)
        
        # Mover en 5 pasos para simular trayectoria
        pasos = 5
        for i in range(pasos):
            page.mouse.move(
                curr_x + (target_x - curr_x) * (i+1) / pasos,
                curr_y + (target_y - curr_y) * (i+1) / pasos
            )
            time.sleep(0.1)
    except:
        pass

def cerrar_popup_entendido_robusto(page):
    """Intenta cerrar el popup 'Entendido' con simulación de mouse"""
    escribir_log_terminal("Iniciando búsqueda robusta de botón 'Entendido'...", "INFO")
    
    selectores = [
        "//button[contains(text(), 'Entendido')]",
        "//button[.//span[contains(text(), 'Entendido')]]",
        "//a[contains(text(), 'Entendido')]",
        "text=Entendido",
        "[aria-label*='Entendido']",
        "button:has-text('Entendido')"
    ]
    
    # Intentar en página y frames
    for _ in range(2): # 2 pasadas
        for frame in [page] + page.frames:
            for selector in selectores:
                try:
                    loc = frame.locator(selector)
                    if loc.count() > 0 and loc.first.is_visible(timeout=2000):
                        escribir_log_terminal(f"¡Botón detectado con: {selector}!", "SUCCESS")
                        simular_movimiento_mouse(page, loc.first)
                        loc.first.hover()
                        time.sleep(1)
                        loc.first.click()
                        time.sleep(3)
                        return True
                except: continue
    
    escribir_log_terminal("No se detectó el botón 'Entendido'.", "WARNING")
    return False

def interactuar_componente_robusto(page, selectores, accion="click", valor=None, descripcion="elemento", min_delay=100, max_delay=250):
    """Busca un componente en Frames y Página con movimiento de mouse y escritura humana"""
    escribir_log_terminal(f"Buscando {descripcion}...", "INFO")
    
    for context in [page] + page.frames:
        for selector in selectores:
            try:
                loc = context.locator(selector)
                if loc.count() > 0 and loc.first.is_visible(timeout=5000):
                    escribir_log_terminal(f"¡{descripcion.upper()} detectado!", "SUCCESS")
                    
                    # Simular comportamiento humano
                    simular_movimiento_mouse(page, loc.first)
                    loc.first.hover()
                    time.sleep(random.uniform(0.5, 1.5))
                    
                    if accion == "click":
                        loc.first.click()
                    elif accion == "escribir":
                        loc.first.click()
                        loc.first.fill("")
                        time.sleep(0.5)
                        loc.first.type(valor, delay=random.randint(min_delay, max_delay))
                    return True
            except: continue
                
    escribir_log_terminal(f"No se pudo interactuar con {descripcion}.", "ERROR")
    return False

def realizar_login_b2c_completo(page):
    """Ejecuta la secuencia de login con bypass de sesión y sigilo conductual"""
    try:
        escribir_log_terminal(f"=== BANCO PICHINCHA B2C -> BYPASS DE SESIÓN ===", "INFO")

        # Sigilo de Fingerprint
        page.add_init_script("""
            delete Object.getPrototypeOf(navigator).webdriver;
            Object.defineProperty(navigator, 'languages', { get: () => ['es-ES', 'es'] });
        """)

        # 1. Cargar Credenciales
        credenciales_filas = LectorArchivos.leerCSV(RUTAS_CONFIG['credenciales_banco'], filtro_columna=0, valor_filtro="Banco Pichincha")
        if not credenciales_filas:
            escribir_log_terminal("Faltan credenciales en el CSV.", "ERROR")
            return False
            
        usuario = credenciales_filas[0][1]
        password = credenciales_filas[0][2]
        escribir_log_terminal(f"Usuario: {usuario[:3]}*** / Pass: {password[:3]}***", "INFO")

        # 2. Navegación
        page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "es-ES,es;q=0.9",
        })

        # Configuración de reintentos y tiempos de escritura
        config_intentos = [
            {"min": 100, "max": 250}, # Intento 1: Normal
            {"min": 250, "max": 450}, # Intento 2: Más lento
            {"min": 50, "max": 150}   # Intento 3: Más rápido/Nervioso
        ]

        for i in range(3):
            intento = i + 1
            escribir_log_terminal(f"--- INTENTO DE LOGIN {intento}/3 ---", "INFO")
            
            escribir_log_terminal(f"Navegando a la URL DE AUTORIZACIÓN (Full B2C Flow)...", "INFO")
            page.goto(URL_LOGIN, wait_until="networkidle", timeout=90000)
            time.sleep(random.uniform(5, 10))

            # 3. Popup 'Entendido'
            cerrar_popup_entendido_robusto(page)

            # 4. Usuario
            sel_user = ["#signInName", "#email", "input[type='email']", "#username"]
            tiempos = config_intentos[i]
            if not interactuar_componente_robusto(page, sel_user, accion="escribir", valor=usuario, 
                                                 descripcion="campo usuario", min_delay=tiempos["min"], max_delay=tiempos["max"]):
                continue

            time.sleep(random.uniform(1.5, 4.0)) # Pausa humana entre campos

            # 5. Contraseña
            sel_pass = ["#password", "input[type='password']", "[name='Password']"]
            if not interactuar_componente_robusto(page, sel_pass, accion="escribir", valor=password, 
                                                 descripcion="campo contraseña", min_delay=tiempos["min"], max_delay=tiempos["max"]):
                continue
                
            time.sleep(random.uniform(1.0, 2.5))

            # 6. Ingresar
            sel_btn = ["#next", "#continue", "button[type='submit']", "//button[contains(text(), 'Ingresar')]"]
            if interactuar_componente_robusto(page, sel_btn, accion="click", descripcion="botón Ingresar"):
                escribir_log_terminal("Verificando resultado del login...", "INFO")
                time.sleep(10)
                
                # Detectar error de bot
                error_detectado = False
                mensajes_error = ["A ocurrido un error", "intetelo de nuevo mas tarde", "Ha ocurrido un error"]
                for msg in mensajes_error:
                    if page.get_by_text(msg, exact=False).count() > 0:
                        escribir_log_terminal(f"¡ERROR DETECTADO: '{msg}'! Posible detección de bot.", "WARNING")
                        error_detectado = True
                        break
                
                if error_detectado:
                    if intento < 3:
                        espera_retry = random.randint(5, 13)
                        escribir_log_terminal(f"Reintentando en {espera_retry} segundos con parámetros diferentes...", "INFO")
                        time.sleep(espera_retry)
                        continue
                    else:
                        escribir_log_terminal("Se alcanzó el máximo de reintentos.", "ERROR")
                        break # Salir del loop de reintentos
                
                # Si no hay error visible, asumimos éxito o al menos avance

                if not os.path.exists("Capturas"): os.makedirs("Capturas")
                screenshot_path = f"Capturas/b2c_session_debug_{int(time.time())}.png"
                time.sleep(5)
                page.screenshot(path=screenshot_path, full_page=True)
                escribir_log_terminal(f"RESULTADO: {os.path.abspath(screenshot_path)}", "SUCCESS")
                return True
        
        return False

    except Exception as e:
        escribir_log_terminal(f"Falla: {str(e)}", "ERROR")
        return False

# ==================== MAIN ====================

def main():
    manager = None
    try:
        if 'DISPLAY' not in os.environ: os.environ['DISPLAY'] = ':99'
        manager = PlaywrightManager(headless=False)
        _, _, _, page = manager.iniciar_navegador()
        realizar_login_b2c_completo(page)
    except Exception as e:
        escribir_log_terminal(f"Falla crítica: {str(e)}", "ERROR")
    finally:
        if manager: manager.cerrar_navegador()

if __name__ == "__main__":
    main()
