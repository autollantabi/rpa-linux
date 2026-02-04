# APIs e integraciones externas

El proyecto **no consume APIs REST propias de los bancos**. La interacción con los portales es vía **navegador automatizado (Playwright)** y, para códigos OTP, vía **IMAP**. A continuación se describen las integraciones reales.

---

## Resumen de integraciones

| Integración | Tipo | Uso |
|------------|------|-----|
| Portales web bancos/cooperativas | Playwright (HTTP implícito) | Login, navegación, descarga de movimientos |
| Servidor de correo | IMAP (SSL) | Obtención del código de seguridad (OTP) |
| SQL Server | pyodbc (TDP) | Registro de ejecuciones, inserción de movimientos |
| Script externo | Subprocess | `UNION_BANCOS_run.sh` al finalizar |

---

## 1. Portales web (Playwright)

No hay cliente HTTP manual; Playwright abre Chromium y realiza las peticiones al cargar y al interactuar con las páginas.

| Entidad | URL de login / entorno | Servicios que la usan | Riesgos / dependencias |
|--------|------------------------|------------------------|-------------------------|
| Banco Guayaquil | `https://empresas.bancoguayaquil.com/BancaEmpresas/login` | `BancoGuayaquil_Final.py` | Cambios de diseño o de dominio rompen selectores. |
| Banco Produbanco | `https://cashmanagement.produbanco.com/cashmanagement/index.html` | `BancoProdubanco_Final.py` | Igual. |
| Banco Pichincha | `https://cashmanagement.pichincha.com/loginNR/#/loginNR/auth/login` | `BancoPichincha_Final.py` | 2FA por celular limita la automatización completa. |
| Cooperativa JEP | `https://jepvirtual.jep.coop/empresas/signinEmpresas.jsf` | `CooperativaJEP_Final.py` | Página lenta; timeouts largos en navegación. |
| Cooperativa CREA | `https://ws.crea.fin.ec/...` (URL larga con parámetros) | `CooperativaCREA_Final.py` | Obsoleto: la cooperativa ya no existe. |

- **Cabeceras / User-Agent:** Definidos en `PlaywrightManager.iniciar_navegador()` en `componentes_comunes.py` (User-Agent tipo Chrome en Linux, opciones `--no-sandbox`, etc.).
- **Endpoints:** No hay listado de “endpoints”; el flujo es navegación a URLs y clics/formularios. Las URLs concretas están en el diccionario `URLS` de cada `*_Final.py`.
- **Riesgo:** Cualquier cambio en el HTML o en el flujo del portal puede obligar a actualizar selectores (XPath/CSS) en el script correspondiente.

---

## 2. Correo IMAP (código OTP)

- **Cliente:** `imaplib` (estándar) y uso desde `CorreoManager` en `componentes_comunes.py`.
- **Configuración:** Credenciales en `configBancos/config/credencialesCorreo.csv`. La primera columna actúa como key (ej. `mail.maxximundo.com`); se usa en `CorreoManager.conectar_imap(carpeta, key)` y `CorreoManager.obtener_codigo_correo(..., key=...)`.
- **Servicios que la usan:** Banco Guayaquil, Banco Produbanco, Banco Pichincha, Cooperativa JEP (y CREA si se ejecutara). Cada uno llama a `CorreoManager.obtener_codigo_correo()` con el `asunto` que envía el banco (ej. "Nuevo token", "Código de Seguridad").
- **Flujo:** Conexión IMAP SSL → selección de inbox → búsqueda por asunto → lectura del último correo (o correos recientes) → extracción de un código de 6 dígitos por regex → devolución del código al script para rellenar el formulario.
- **Riesgos:** Cambio de asunto o formato del correo; filtros antispam; credenciales IMAP incorrectas o servidor no accesible.

---

## 3. SQL Server (pyodbc)

- **Cliente:** `pyodbc` en `BaseDatos` (`componentes_comunes.py`). Connection string usa `ODBC Driver 18 for SQL Server` y `TrustServerCertificate=yes`.
- **Configuración:** `configBancos/config/credencialesDB.csv` (servidor, base de datos, usuario, contraseña). No hay variable de entorno; la ruta del CSV viene de `RUTAS_CONFIG['credenciales_bd']`.
- **Servicios que la usan:** Todos los `*_Final.py` (consulta de `MAX(idAutomationRun)`, INSERT en `AutomationRun` y `AutomationLog`, INSERT en tabla de movimientos tipo `RegistrosBancos`).
- **Endpoints representativos:** No aplica; son consultas SQL directas (SELECT, INSERT, UPDATE) contra tablas como `AutomationRun`, `AutomationLog` y la tabla de movimientos del banco (nombre en constante `DATABASE` de cada script).
- **Riesgos:** Cambio de esquema o nombres de tablas; credenciales o red; versión del driver ODBC en el servidor Linux.

---

## 4. Script de unión (subprocess)

- **Ejecución:** `SubprocesoManager.ejecutar_bat_final()` en `componentes_comunes.py` ejecuta la ruta en `RUTAS_CONFIG['bat_final']` (por defecto `/home/administrador/Escritorio/UNION_BANCOS_0.1/UNION_BANCOS/UNION_BANCOS_run.sh`) con `subprocess.run(..., timeout=300)`.
- **Servicios que la usan:** Todos los scripts que terminan correctamente (y en algunos casos también en fallo) llaman a este script al final.
- **Riesgos:** Ruta incorrecta o script inexistente; permisos; que el script externo falle o tarde más de 5 minutos.

---

## Resumen para quien mantiene el proyecto

- No hay documentación de APIs REST de bancos porque no se usan.
- Cualquier cambio en portales (URLs, selectores, flujos) se refleja en el `*_Final.py` correspondiente.
- Credenciales y rutas están en CSV y en `RUTAS_CONFIG`; no hay variables de entorno obligatorias para APIs (ver [setup.md](setup.md)).
