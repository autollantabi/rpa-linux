from componentes_comunes import PlaywrightManager, EsperasInteligentes
from datetime import datetime
import os

def main():
    # Inicializar Playwright usando PlaywrightManager
    playwright_manager = PlaywrightManager(
        headless=True,
        download_path="/home/administrador/configBancos/descargas",
        timeout=60000
    )
    playwright, browser, context, page = playwright_manager.iniciar_navegador()
    
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
        
        # Navegar a la página
        print("Navigating to https://bancaempresas.pichincha.com...")
        page.goto("https://bancaempresas.pichincha.com/", timeout=180000, wait_until="networkidle")
        print("Navigation complete!")
        
        # Esperar un poco más
        EsperasInteligentes.esperar_con_loader_simple(5, "Esperando carga")
        
        # Take screenshot
        screenshot_path = os.path.join(
            "/home/administrador/configBancos/logs/screenshots",
            f"debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        )
        page.screenshot(path=screenshot_path)
        print(f"Screenshot saved to: {screenshot_path}")
        
        # Get HTML content
        html_content = page.content()
        html_path = os.path.join(
            "/home/administrador/configBancos/logs",
            f"debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        )
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"HTML content saved to: {html_path}")
        
        # Print some page info
        print(f"Page title: {page.title()}")
        print(f"Page URL: {page.url}")
        
        # Get all input elements
        print("\nFound input elements:")
        inputs = page.query_selector_all("input")
        for i, inp in enumerate(inputs):
            tag_name = inp.evaluate("el => el.tagName")
            input_id = inp.evaluate("el => el.id")
            name = inp.evaluate("el => el.name")
            type_attr = inp.evaluate("el => el.type")
            placeholder = inp.evaluate("el => el.placeholder")
            print(f"Input {i}: id='{input_id}', name='{name}', type='{type_attr}', placeholder='{placeholder}'")
            
    finally:
        playwright_manager.cerrar_navegador()

if __name__ == "__main__":
    main()
