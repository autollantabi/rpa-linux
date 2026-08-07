
from componentes_comunes import PlaywrightManager, EsperasInteligentes, LectorArchivos, RUTAS_CONFIG
from datetime import datetime
import os

def main():
    # Inicializar Playwright
    manager = PlaywrightManager(
        headless=True,
        download_path=RUTAS_CONFIG['descargas'],
        timeout=120000
    )
    playwright, browser, context, page = manager.iniciar_navegador()
    
    try:
        # Add anti-detection scripts
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
        
        # Navegar a la página de login
        url = "https://cashmanagement.produbanco.com/cashmanagement/index.html"
        print(f"Navigating to: {url}")
        page.goto(url, timeout=120000)
        page.wait_for_load_state("domcontentloaded", timeout=60000)
        EsperasInteligentes.esperar_con_loader_simple(5, "Esperando carga de página")
        
        # Tomar screenshot
        screenshot_dir = os.path.join(RUTAS_CONFIG['logs'], "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        screenshot_path = os.path.join(screenshot_dir, f"debug_produbanco_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        page.screenshot(path=screenshot_path)
        print(f"Screenshot saved to: {screenshot_path}")
        
        # Leer credenciales
        credenciales = LectorArchivos.leerCSV(
            RUTAS_CONFIG['credenciales_banco'],
            filtro_columna=0,
            valor_filtro="Produbanco"
        )
        
        if credenciales:
            usuario = credenciales[0][1]
            password = credenciales[0][2]
            print(f"Credenciales cargadas: usuario={usuario}")
            
            # Escribir usuario
            page.fill("//input[@id='username']", usuario)
            print("Usuario escrito")
            page.wait_for_timeout(1000)
            
            # Escribir password
            page.fill("//input[@id='password']", password)
            print("Contraseña escrita")
            
            # Screenshot después de credenciales
            screenshot_path2 = os.path.join(screenshot_dir, f"debug_produbanco_credenciales_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            page.screenshot(path=screenshot_path2)
            print(f"Screenshot credenciales saved to: {screenshot_path2}")
            
        else:
            print("No se encontraron credenciales para Produbanco")
        
    finally:
        manager.cerrar_navegador()

if __name__ == "__main__":
    main()
