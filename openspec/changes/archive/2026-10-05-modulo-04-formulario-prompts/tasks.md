## 1. Contrato y dependencia de plantillas

- [x] 1.1 Añadir Jinja2 a las dependencias del proyecto y definir los enums y modelos Pydantic de la petición/respuesta de estimación.
- [x] 1.2 Migrar el router al contrato tipado, incluyendo la versión de prompt y la validación de campos obligatorios, valores permitidos y longitud de descripción.

## 2. Prompts versionados

- [x] 2.1 Crear `app/prompts/estimation/v1/` con las plantillas de sistema, usuario y ejemplos plausibles.
- [x] 2.2 Implementar el cargador Jinja2 con variables obligatorias, limpieza de espacios y selección de versión `v1`.
- [x] 2.3 Añadir pruebas del render: bloque de descripción, variantes por formato y detalle, inclusión de ejemplos y fallo ante variables ausentes.

## 3. Servicio de IA y endpoint

- [x] 3.1 Adaptar la generación normal para recibir la petición tipada y entregar al proveedor el sistema y el usuario por separado.
- [x] 3.2 Adaptar la generación normal usada por `POST /api/v1/estimate` para reutilizar exactamente el mismo render versionado y conservar el control de errores, tokens y proveedores.
- [x] 3.3 Actualizar las pruebas de servicio y endpoint con dobles locales, verificando el nuevo body, la versión de prompt y los mensajes separados.

## 4. Interfaz Streamlit

- [x] 4.1 Sustituir la entrada de chat por un formulario con los cuatro campos, valores guiados y validación local de la descripción.
- [x] 4.2 Conectar el formulario mediante `POST /api/v1/estimate`, enviar el body tipado y mostrar la respuesta completa, incluidos los metadatos disponibles en el panel lateral.
- [x] 4.3 Verificar manualmente una estimación válida y los mensajes de error de una descripción insuficiente, un fallo HTTP y un fallo de proveedor.

## 5. Documentación y verificación final

- [x] 5.1 Actualizar el README con el nuevo contrato, el uso del formulario y el comando de pruebas.
- [x] 5.2 Ejecutar `uv run pytest`, registrar los resultados y corregir cualquier regresión observada.
- [x] 5.3 Confirmar que la interfaz usa el endpoint exigido y registrar las comprobaciones manuales antes de cerrar el cambio.

### Notas de verificación (2026-10-05)

Las comprobaciones de 4.2, 4.3 y 5.3 se automatizaron con `streamlit.testing.v1.AppTest`
en vez de quedarse en una lista manual: `AppTest` ejecuta la interfaz en proceso, así
que verifican el mismo camino sin arrancar el servidor y sin llamadas reales.

- 4.2 — `test_el_formulario_envia_la_solicitud_al_api`: comprueba la URL, el body
  tipado y que la estimación se pinta.
- 4.3 — `test_una_descripcion_insuficiente_no_llega_al_api`,
  `test_un_fallo_http_se_muestra_como_error_de_conexion`,
  `test_un_fallo_de_proveedor_no_expone_el_detalle_interno`.
- 5.3 — las cuatro pruebas anteriores usan `AppTest`, que carga
  `streamlit_app.py` real: la interfaz y el endpoint exigido quedan verificados.

Antes de archivar se corrigió una especificación obsoleta: los escenarios fijaban
`prompt_version = "v1"` en literal, cuando la versión es configurable y `v2` ya
estaba soportada y cubierta por `tests/test_llm_service.py`.
