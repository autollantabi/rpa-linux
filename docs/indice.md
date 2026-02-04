# Índice de documentación

Índice de todos los documentos de la carpeta `docs/`, con propósito, cuándo usarlos, orden de lectura recomendado y uso como plantilla para otros repos.

---

## Tabla de documentos

| Documento | Propósito | Cuándo usarlo |
|-----------|-----------|----------------|
| [setup.md](setup.md) | Requisitos del sistema, variables de entorno, pasos para ejecutar localmente, errores comunes y resolución. | Primera vez que configuras el proyecto; errores al ejecutar o al conectar BD/correo/portales. |
| [arquitectura.md](arquitectura.md) | Arquitectura general, árbol de carpetas, responsabilidades, cómo añadir un banco o funcionalidad, patrones de diseño. | Entender la estructura del código; añadir un nuevo banco/cooperativa o un nuevo paso en un flujo. |
| [apis.md](apis.md) | Integraciones externas: portales (Playwright), correo IMAP, SQL Server, script de unión. No hay APIs REST de bancos. | Saber qué servicios externos usa el proyecto y dónde se configuran. |
| [flujo-funcional.md](flujo-funcional.md) | Flujos principales: login, OTP, descarga por empresa, cierre; Bolivariano (solo archivos); JEP modo manual; auth/permisos. | Entender paso a paso qué hace cada tipo de ejecución. |
| [guia-proyecto.md](guia-proyecto.md) | Onboarding: qué es el proyecto, cómo empezar, dónde está cada cosa, resumen de APIs, flujo para añadir funcionalidad, decisiones históricas, contacto. | Incorporación de un desarrollador nuevo; referencia rápida de “dónde está X”. |
| [decisiones-tecnicas.md](decisiones-tecnicas.md) | Justificación de tecnologías (Python, Playwright, SQL Server, CSV, etc.), alternativas y trade-offs. | Entender por qué está hecho así y qué limitaciones implica. |
| [despliegue.md](despliegue.md) | Proceso de “build”, configuración de ambientes, consideraciones para producción (cron, rutas, credenciales, ODBC, red). | Desplegar en un servidor nuevo o ajustar producción. |
| [pendientes.md](pendientes.md) | Mejoras sugeridas, deuda técnica detectada, suposiciones o partes no claras del proyecto. | Planificar mejoras; aclarar dudas; no olvidar tareas técnicas. |
| [indice.md](indice.md) | Este archivo: índice de documentos, orden de lectura, uso como plantilla. | Navegar la documentación; onboarding; replicar estructura en otro repo. |

---

## Orden de lectura recomendado (desarrollador nuevo)

1. **[README.md](../README.md)** — Visión general, stack, casos de uso, guía rápida y enlace al índice.
2. **[indice.md](indice.md)** (este documento) — Listado de docs y propósito de cada uno.
3. **[guia-proyecto.md](guia-proyecto.md)** — Onboarding: qué es el proyecto, cómo empezar, dónde está cada cosa.
4. **[setup.md](setup.md)** — Requisitos, variables, pasos para ejecutar y errores comunes.
5. **[arquitectura.md](arquitectura.md)** — Estructura del código y cómo añadir funcionalidad.
6. **[flujo-funcional.md](flujo-funcional.md)** — Flujos paso a paso (login, OTP, descarga, solo archivos).
7. **[apis.md](apis.md)** — Integraciones (portales, IMAP, BD, script final).
8. **[decisiones-tecnicas.md](decisiones-tecnicas.md)** — Por qué están elegidas las tecnologías y trade-offs.
9. **[despliegue.md](despliegue.md)** — Cuando vaya a desplegar o tocar producción.
10. **[pendientes.md](pendientes.md)** — Mejoras, deuda técnica y puntos no claros.

Para tareas concretas (ej. “añadir un banco”, “arreglar error de BD”), usar la tabla de documentos y abrir el que corresponda.

---

## Uso como plantilla para otro repositorio

Si quieres replicar esta estructura de documentación en otro proyecto:

1. **Crea la carpeta `docs/`** en la raíz del repo (no incluyas un README dentro de docs si sigues la misma convención).
2. **Archivos a crear (y adaptar contenido):**
   - `docs/setup.md` — Requisitos, variables de entorno, pasos de ejecución local, errores comunes.
   - `docs/arquitectura.md` — Arquitectura, carpetas, responsabilidades, cómo añadir módulos/pantallas, patrones.
   - `docs/apis.md` — Solo si el proyecto consume APIs externas; clientes, URLs, servicios que las usan, riesgos.
   - `docs/flujo-funcional.md` — Flujos principales del sistema (login, creación, edición, etc.) y auth/permisos si aplican.
   - `docs/guia-proyecto.md` — Onboarding, resumen del proyecto, dónde está cada cosa, flujo para añadir funcionalidad, decisiones históricas, contacto.
   - `docs/decisiones-tecnicas.md` — Justificación de tecnologías, alternativas, trade-offs.
   - `docs/despliegue.md` — Build, ambientes, consideraciones de producción.
   - `docs/pendientes.md` — Mejoras, deuda técnica, suposiciones o partes no claras.
   - `docs/indice.md` — Tabla documento / propósito / cuándo usarlo; orden de lectura recomendado; sección “Uso como plantilla”.
3. **En el README principal del repo:** Incluir una sección “Documentación” o “Índice de documentación” con enlace a `docs/indice.md` y una “Guía rápida de ejecución” que referencie `docs/setup.md`.
4. **Mantener coherencia:** Evitar duplicar información entre archivos; usar enlaces relativos entre docs (`[setup.md](setup.md)`).
5. **Redactar pensando en quien te reemplace:** Objetivo es que alguien nuevo pueda entender, ejecutar, mantener y ampliar el proyecto solo con esta documentación.

Puedes copiar este `indice.md` y la tabla de documentos, y sustituir los nombres de archivos y enlaces por los de tu proyecto.
