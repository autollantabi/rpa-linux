# rpa-linux

Automatización bancaria multiplataforma para Linux usando Python y Playwright.

## Bancos soportados

- **Banco Pichincha**
- **Banco Produbanco**
- **Banco Bolivariano**

## Tecnologías utilizadas

- Python 3
- Playwright (automatización de navegador)
- Librerías estándar de Python (os, datetime, csv, etc.)

## Estructura del proyecto

- `BancoPichincha_Final.py`: Automatización completa de consultas y descargas usando Playwright.
- `BancoProdubanco_Final.py`: Automatización de operaciones bancarias y procesamiento de empresas con Playwright.
- `CooperativaJEP_Final.py`: Automatización de operaciones bancarias y procesamiento de empresas con Playwright..
- `CooperativaCREA_Final.py`: Automatización de operaciones bancarias y procesamiento de empresas con Playwright..
- `BancoBolivariano_Final.py`: Código sencillo en Python que solo lee y procesa archivos TXT descargados manualmente.
- `componentes_comunes.py`: Funciones y clases reutilizables: logs, manejo de archivos, helpers de Playwright, etc.
- `README.md`: Este archivo.

## Requisitos

- Python 3.8 o superior
- Playwright instalado:
  ```bash
  pip install playwright
  playwright install
  ```
- Acceso a los portales web de los bancos (credenciales válidas)
- Permisos para ejecutar scripts en Linux

## Uso

1. Clona este repositorio:
   ```bash
   git clone https://github.com/autollantabi/rpa-linux.git
   cd rpa-linux/bancos
   ```

2. Instala dependencias:
   ```bash
   pip install -r requirements.txt
   playwright install
   ```

3. Ejecuta el script del banco que necesites, por ejemplo:
   ```bash
   python BancoPichincha_Final.py
   ```

   Para Banco Bolivariano, solo necesitas tener el archivo TXT descargado y ejecutar:
   ```bash
   python BancoBolivariano_Final.py
   ```

## Notas

- El código para Banco Bolivariano **no automatiza el navegador**, solo procesa archivos TXT descargados manualmente.
- Los scripts para Pichincha y Produbanco usan Playwright para automatizar la navegación y descarga de movimientos.
- Los logs se guardan por banco y por ejecución en la carpeta `logs/`.
- Personaliza las rutas y credenciales en los archivos de configuración según tu entorno.

## Licencia

MIT

---

**Desarrollado por autollantabi**
