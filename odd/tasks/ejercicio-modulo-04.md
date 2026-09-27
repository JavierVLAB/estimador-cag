# Ejercicio módulo 04 — Formulario y prompts versionados

## Objetivo

Completar el ejercicio del módulo 04 sobre la base existente: sustituir la entrada tipo chat por un formulario guiado, mover las instrucciones de la IA a plantillas versionadas y hacer que Streamlit use `POST /api/v1/estimate`, mostrando la respuesta completa.

## Alcance autorizado

- Adaptar el contrato de estimación, el servicio, el endpoint y Streamlit.
- Crear plantillas Jinja2 versionadas y sus pruebas.
- Actualizar el README con las instrucciones de uso y pruebas.

## Fuera de alcance

- Rehacer el proyecto con Ruby on Rails u otra tecnología.
- Salida JSON estructurada, guardrails, caché semántica, RAG, autenticación o base de datos.
- Cambiar proveedores, añadir guardrails, caché semántica, RAG, autenticación o base de datos.
- Ninguno de los tres extras inicialmente diferidos: la persona usuaria los autorizó el 27-09-2026.

## Configuración de pruebas

- TDD: no establecido en el proyecto; se harán comprobaciones funcionales ordinarias.
- Runner: `uv run pytest`.
- Espejo Engram: pendiente; no hay acceso a ese almacenamiento en esta sesión.

## Entrega

- Estrategia: ask-on-risk.
- Previsión inicial: unas 250 líneas modificadas, sin archivos generados. Ampliación autorizada: unas 180 líneas adicionales.
- Rama actual: `S04-IA_Avanzados`. El enunciado pide entregar una rama llamada `pre-session-04`; su creación queda pendiente de decisión de la persona usuaria.

## Tareas

- [x] M04-01 — Definir el nuevo contrato tipado.
  - Ruta: delegated (preparación y lectura ya delegadas); evidencia: afecta esquema, router, servicio, interfaz y pruebas.
  - Crear los campos `description`, `project_type`, `detail_level` y `output_format`, con valores limitados y validación de longitud.
  - Mantener una respuesta compatible con la aplicación e incluir la versión del prompt.
  - Comprobar que faltas, valores inválidos y textos demasiado cortos reciben un error claro.

- [x] M04-02 — Crear las instrucciones versionadas.
  - Ruta: delegated; evidencia: son varios archivos de plantilla y su cargador.
  - Crear `v1` con instrucciones generales, formato de salida, nivel de detalle y ejemplos plausibles.
  - Garantizar que se pueda solicitar una futura versión sin cambiar el resto de la aplicación.
  - Comprobar que el cargador detecta nombres mal escritos en las plantillas.

- [x] M04-03 — Conectar las instrucciones al servicio de IA.
  - Ruta: delegated; evidencia: cambia la generación normal, los proveedores y las pruebas relacionadas.
  - Enviar las instrucciones generales y la descripción como dos partes separadas.
- Conservar OpenAI, Anthropic, errores y métricas de la respuesta normal.
  - Comprobarlo con sustitutos locales de los proveedores, sin claves ni red.

- [x] M04-04 — Adaptar el endpoint de estimación.
  - Ruta: inline si queda limitado a router y contrato; si requiere cambios no mecánicos adicionales, delegated.
  - Aceptar el formulario tipado y devolver el texto con la versión `v1`.
  - Comprobar la validación y que las dos partes del mensaje llegan por separado al servicio.

- [x] M04-05 — Sustituir el chat por el formulario Streamlit.
  - Ruta: delegated; evidencia: interfaz y conexión con el servicio cambian de forma no mecánica.
- Mostrar descripción, tipo de proyecto, nivel de detalle y formato de resultado.
- Enviar los cuatro valores mediante `POST /api/v1/estimate`, mostrar la respuesta completa y conservar el panel lateral y métricas disponibles.
- Comprobar manualmente que el formulario no envía una descripción insuficiente y que una petición válida usa el endpoint.

- [x] M04-06 — Añadir pruebas del ejercicio.
  - Ruta: delegated; evidencia: nuevas pruebas de plantillas, contrato y endpoint.
  - Verificar que la descripción aparece dentro de su bloque.
  - Verificar que el formato y el nivel de detalle cambian las instrucciones correctas.
  - Ejecutar `uv run pytest` sin acceder a proveedores externos.

- [x] M04-07 — Actualizar documentación y preparar entrega.
  - Ruta: inline; cambio documental mecánico tras verificar los pasos anteriores.
- Explicar cómo levantar el servicio, abrir la interfaz y ejecutar pruebas.
- Confirmar que no hay claves en el código, que Streamlit usa el endpoint exigido y registrar las comprobaciones realizadas.

- [x] M04-08 — Crear y habilitar el prompt versionado `v2`.
  - Ruta: delegated; evidencia: plantillas, cargador/configuración, servicio y pruebas cambian de manera coordinada.
  - Mantener `v1` disponible y seleccionar `v2` mediante configuración del backend, sin que Streamlit construya ni envíe prompts al proveedor.
- Comprobar la selección explícita de versión y que las variantes mantienen los mensajes system/user separados.
  - Evidencia: `uv run pytest -q` — 42 correctas el 27-09-2026.

- [x] M04-09 — Ampliar las estimaciones de referencia.
  - Ruta: delegated; evidencia: ejemplos versionados y pruebas de render.
  - Añadir ejemplos plausibles y diversos a `v2`, sin incluir información sensible o identificable.
- Comprobar que se incluyen en el prompt de sistema y nunca sustituyen la descripción del usuario.
  - Evidencia: la suite verifica cuatro ejemplos `v2` y la separación de mensajes.

- [x] M04-10 — Registrar metadatos avanzados de cada prompt.
  - Ruta: delegated; evidencia: servicio, configuración, documentación y pruebas.
  - Registrar versión, proveedor, modelo, huella criptográfica y tamaño del prompt; no registrar la descripción ni el texto completo del prompt para proteger datos de usuario.
- Comprobar que el registro se emite al generar una estimación sin exponer contenido sensible.
  - Evidencia: prueba de registro confirma versión, proveedor, modelo, SHA-256 y tamaños, y la ausencia de descripción e instrucciones.

## Criterios de aceptación

1. La interfaz muestra un formulario con las cuatro entradas requeridas.
2. La descripción y las tres opciones llegan al servicio y condicionan el resultado.
3. Las instrucciones viven en archivos `v1`, no dentro de un texto fijo en Python.
4. Streamlit envía el formulario a `POST /api/v1/estimate`, muestra la respuesta completa y conserva los metadatos de respuesta disponibles.
5. Las pruebas de plantilla y endpoint no llaman a servicios externos.
6. El README permite arrancar y comprobar el proyecto.

## Estado y siguiente paso

Implementadas y verificadas M04-01 a M04-10. Streamlit usa `POST /api/v1/estimate` y no importa SDKs de proveedores; el backend selecciona `v1` o `v2` con `LLM_PROMPT_VERSION`. Prueba observada el 27-09-2026: `PYTHONDONTWRITEBYTECODE=1 uv run pytest -q` — 42 correctas, con un aviso externo de deprecación de Starlette. Unidad de trabajo: `feat: complete module 4 estimation prompts` en la rama `S04-IA_Avanzados`. La evaluación nativa la clasifica como riesgo medio y exige seleccionar explícitamente los artefactos OpenSpec sin seguimiento antes de iniciar la revisión; se mantienen fuera de este commit. El espejo Engram sigue pendiente porque no está disponible en esta sesión.
