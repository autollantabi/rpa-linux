# RPA Bancos — Automatización bancaria multiplataforma

Automatización bancaria para Linux que descarga movimientos y los registra en base de datos, usando **Python** y **Playwright**. Pensada para que cualquier desarrollador pueda entender, ejecutar, mantener y ampliar el proyecto sin depender del autor original.

---

## Descripción general

Este proyecto automatiza la consulta y descarga de movimientos bancarios de varios bancos y cooperativas en Ecuador. Los scripts inician sesión en los portales web (o procesan archivos ya descargados), descargan movimientos por empresa, normalizan los datos y los insertan en SQL Server. Al finalizar, se ejecuta un script de unión de datos (`UNION_BANCOS_run.sh`).

- **Repositorio:** [autollantabi/rpa-linux](https://github.com/autollantabi/rpa-linux) (carpeta `bancos`).

---

## Problema que resuelve

- Evitar la descarga manual de movimientos en cada banco/cooperativa.
- Centralizar movimientos en una base de datos para reportes y conciliación.
- Ejecutar el proceso de forma programada (cron) en servidor Linux sin intervención.

---

## Tipo de aplicación

- **Backend / automatización (RPA):** scripts Python que se ejecutan en Linux (por cron o manualmente). No hay interfaz web ni API expuesta; la interacción es con portales web vía Playwright y con archivos/BD locales.

---

## Stack tecnológico

| Componente        | Tecnología |
|-------------------|------------|
| Lenguaje          | Python 3.8+ |
| Automatización web| Playwright (Chromium) |
| Base de datos     | SQL Server (pyodbc) |
| Archivos          | CSV, Excel (openpyxl), TXT |
| Correo (OTP)      | IMAP (imapclient / estándar) |
| Entorno headless  | Xvfb (Linux) |
| Orquestación      | Scripts Bash + cron |

---

## Casos de uso principales

1. **Descarga automática por banco:** ejecutar cada banco/cooperativa en su horario (cron): login → código por correo (si aplica) → descarga de movimientos por empresa → inserción en BD → script final.
2. **Procesamiento solo archivos:** Banco Bolivariano (TXT) y JEP en modo manual (Excel): leer archivos de una carpeta, normalizar e insertar en BD.
3. **Unión de datos:** tras cada ejecución exitosa se lanza `UNION_BANCOS_run.sh` para consolidar datos (ruta configurada en `componentes_comunes.RUTAS_CONFIG`).

---

## Guía rápida de ejecución

1. Requisitos y variables: ver [docs/setup.md](docs/setup.md).
2. Ejecución local con scripts Bash (recomendado en Linux):
   ```bash
   ./bashGuayaquil.sh
   ./bashProdubanco.sh
   ./bashBolivariano.sh
   ./bashJEP.sh
   # Modo manual JEP (archivos ya descargados):
   ./bashJEP_manual.sh
   ```
3. Ejecución directa con Python (desde la carpeta `bancos`):
   ```bash
   source /ruta/al/venv/bin/activate
   python BancoGuayaquil_Final.py
   python CooperativaJEP_Final.py --manual
   python BancoBolivariano_Final.py
   ```

Para requisitos del sistema, variables de entorno, pasos detallados y errores comunes, consultar **[docs/setup.md](docs/setup.md)**.

---

## Índice de documentación

Toda la documentación técnica está en la carpeta **`docs/`**. Índice y orden de lectura recomendado: **[docs/indice.md](docs/indice.md)**.

---

## Bancos y cooperativas soportados

| Entidad              | Tipo        | Automatización |
|----------------------|-------------|----------------|
| Banco Pichincha      | Banco       | Playwright (actualmente limitado por 2FA por celular) |
| Banco Guayaquil      | Banco       | Playwright (login, código correo, movimientos por empresa) |
| Banco Produbanco     | Banco       | Playwright (login, código correo, movimientos) |
| Banco Bolivariano    | Banco       | Solo procesamiento de archivos TXT (sin navegador) |
| Cooperativa JEP      | Cooperativa | Playwright + modo manual (Excel) |
| Cooperativa CREA     | Cooperativa | Playwright (obsoleto: la cooperativa ya no existe) |

---

## Licencia

MIT.

---

**Desarrollado por Diego Barbecho** — [GitHub](https://github.com/diegobarpdev)
