# rpa-linux

Automatización bancaria multiplataforma para Linux usando Python y Playwright.

## Bancos soportados

- **Banco Pichincha**
- **Banco Guayaquil**
- **Banco Produbanco**
- **Banco Bolivariano**
- **Cooperativa JEP**
- **Cooperativa CREA**

## Tecnologías utilizadas

- Python 3
- Playwright (automatización de navegador)
- Librerías estándar de Python (os, datetime, csv, etc.)

## Estructura del proyecto

### Automatización Playwright (Navegador Virtual)

- **Bancos:**
  - `BancoPichincha_Final.py`: Automatización completa de consultas y descargas usando Playwright.
  - `BancoProdubanco_Final.py`: Automatización de operaciones bancarias y procesamiento de empresas con Playwright.
  - `BancoGuayaquil_Final.py`: Automatización de operaciones bancarias y procesamiento de empresas con Playwright.
  - `BancoBolivariano_Final.py`: *Solo lee y procesa archivos TXT descargados manualmente, no usa navegador virtual.*

- **Cooperativas:**
  - `CooperativaJEP_Final.py`: Automatización de operaciones bancarias y procesamiento de empresas con Playwright.
  - `CooperativaCREA_Final.py`: Automatización de operaciones bancarias y procesamiento de empresas con Playwright.

### Bash de ejecución

- `bashBolivariano.sh`, `bashGuayaquil.sh`, `bashPichincha.sh`, `bashProdubanco.sh`, `bashCREA.sh`, `bashJEP.sh`: Scripts bash para lanzar la automatización en un navegador virtual (headless) para cada banco/cooperativa. **Excepto Bolivariano**, que solo ejecuta el script Python para procesar el archivo TXT.

### Componentes comunes

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
   pip install playwright pyodbc openpyxl imapclient
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

## Librerías necesarias

Instala las siguientes librerías antes de ejecutar el proyecto:

- playwright
- pyodbc
- openpyxl
- imapclient
- email (incluida en la librería estándar de Python)
- csv (incluida en la librería estándar de Python)
- re (incluida en la librería estándar de Python)
- threading (incluida en la librería estándar de Python)
- signal (incluida en la librería estándar de Python)
- os (incluida en la librería estándar de Python)
- sys (incluida en la librería estándar de Python)
- time (incluida en la librería estándar de Python)
- json (incluida en la librería estándar de Python)
- functools (incluida en la librería estándar de Python)
- datetime (incluida en la librería estándar de Python)

Puedes instalar las dependencias externas con:

```bash
pip install playwright pyodbc openpyxl imapclient
playwright install
```

## Licencia

MIT

---

**Desarrollado por Diego Barbecho**
**GitProfile: https://github.com/BrujoFurioso22**

