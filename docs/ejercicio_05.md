# ✍️ Ejercicio — memoria conversacional y contexto enriquecido 🔴

**Autor:** Antonio Perez  
**Curso:** AI Engineering 2026/09  
**Fuente:** https://training.lidr.co/posts/ai-engineering-202609-%E2%9C%8D%EF%B8%8F-ejercicio-memoria-conversacional-y-contexto-enriquecido%F0%9F%94%B4

> ⏱ La fecha límite es lunes, 5 de octubre al final del día.

Hasta la sesión 04 hemos tratado al estimator como un sistema transaccional: una transcripción entra, una estimación sale. Funciona bien para el caso de «quiero estimar este proyecto y olvidarme», pero no para lo que de verdad pasa en una empresa: una conversación iterativa donde el cliente refina el alcance, añade nueva información, sube documentos complementarios, y espera que el sistema recuerde sobre qué proyecto estamos hablando.

Antes del directo, vamos a corregir ese vacío con dos cambios concretos. Primero, el estimator va a mantener memoria conversacional dentro de una misma sesión: el contexto del proyecto en curso se preserva entre turnos sin reenviar todo el historial bruto en cada llamada. Segundo, va a aceptar adjuntos: PDFs y documentos Word que enriquecen la transcripción con especificaciones técnicas, propuestas previas o diagramas de arquitectura. Sobre esa base, el directo construirá las piezas avanzadas — compresión de memoria con anclas, tier dinámico y, en la segunda hora, el patrón Actor-Critic-Boss.

El ejercicio es exigente pero acotado. Si te quedas a medias, llega al directo con lo que tengas: arrancamos con un breve repaso de soluciones y a partir de ahí seguimos juntos. Pero quien acabe completo va a poder concentrarse en lo nuevo en lugar de hacer ingeniería estándar mientras intenta seguir el directo.

## Punto de partida

Lo que tienes al final de la sesión 04:

- Servicio IA en FastAPI con wrapper de proveedores que abstrae OpenAI y Anthropic, caching, streaming y observabilidad básica con structlog.
- Endpoint principal del estimator que recibe parámetros tipados (formulario, no chat libre) y una transcripción, y devuelve una estimación estructurada validada por schema Pydantic.
- Templates Jinja2 versionados para los prompts.
- Guardrails programáticos sobre la salida.
- Cliente Streamlit con formulario que produce los parámetros tipados.

Si en sesión 03 elegiste un stack distinto a Streamlit para el cliente, traduce los pasos de cliente a tu stack: el patrón es idéntico, solo cambian las APIs. Recuerda que frontend y backend de negocio son libres, y que el código del servicio IA es siempre Python con FastAPI.

## Objetivos de aprendizaje

Al terminar este ejercicio deberías poder defender en una conversación técnica:

- La diferencia operativa entre historial (el array `messages` que viaja a la API en cada llamada) y memoria (el conocimiento sobre el proyecto en curso que se preserva y reutiliza).
- Por qué la ventana deslizante es la estrategia por defecto razonable cuando arrancas, y qué problemas concretos te empuja a sustituirla.
- Cómo separar limpiamente la gestión del historial conversacional de la gestión de los hechos del proyecto (`project_metadata`).
- Las dos formas canónicas de procesar adjuntos: enviarlos directamente al LLM multimodal vs extraer texto localmente con pypdf/PyMuPDF. Cuándo elegir cada una.
- Cómo gestionar `multipart/form-data` con FastAPI cuando hay parámetros tipados y archivos en la misma petición.

## Lo que entra en el ejercicio

- **Sesión conversacional con identificador.** Un nuevo endpoint `POST /sessions` que crea una sesión vacía y devuelve un `session_id`. Las peticiones de estimación llevarán este identificador.
- **Memoria conversacional con ventana deslizante.** El servicio IA mantiene en memoria del proceso (un diccionario, sin BBDD) el historial de mensajes asociado a cada `session_id`, conservando los últimos N turnos.
- **`project_metadata` separado del historial.** Un diccionario por sesión que captura los hechos relevantes del proyecto en curso (nombre, equipo asumido, tecnologías mencionadas, alcance acordado). Se inyecta en el system prompt en cada turno, vive aparte del historial.
- **Endpoint multi-turno.** Un nuevo endpoint `POST /sessions/{session_id}/estimate` que acepta una transcripción más una lista opcional de adjuntos, y devuelve la estimación. El historial y el `project_metadata` se actualizan automáticamente con cada llamada.
- **Adjuntos.** Soporte para PDFs y documentos Word adjuntos en `multipart/form-data`. Implementas uno de los dos caminos a tu elección:
  - **Camino A (multimodal directo):** subir el PDF directamente al LLM usando la Files API de OpenAI o Anthropic. Más simple, menos código, acoplado al proveedor multimodal.
  - **Camino B (extracción local):** extraer texto localmente con pypdf o PyMuPDF para PDFs y python-docx para Word, y enviar el texto extraído como parte del prompt. Más control, independiente del proveedor, prepara el terreno para el chunking de RAG en el módulo 3.

## Lo que no entra

- Estrategia de resumen acumulativo o estrategia híbrida con anclas — se construyen en el directo.
- Tier dinámico derivado de contexto en runtime — se construye en el directo.
- Persistencia de la memoria entre reinicios del servicio — un diccionario en memoria del proceso es suficiente para esta fase.
- Búsqueda web integrada y function calling para BBDD del backend de negocio — aparecen en el material teórico pero no se implementan aquí.
- Cualquier pieza del patrón Actor-Critic-Boss — segunda hora del directo.

## Pasos guiados

Cada paso enuncia el objetivo. Los detalles de implementación los decides tú; la solución completa está en una rama del repositorio (`solutions/session-05`) por si te bloqueas.

### Paso 1 — Modelar el estado de la sesión

Crea un módulo `sessions.py` en el servicio IA con dos estructuras:

- `ConversationHistory`: una lista limitada de mensajes con la lógica de ventana deslizante. Cuando supera N turnos, descarta los más antiguos preservando siempre el system prompt.
- `ProjectMetadata`: un Pydantic model con campos como `project_name`, `assumed_team_size`, `mentioned_technologies` (lista), `agreed_scope` (texto libre).

Ambas estructuras viven dentro de una clase `Session` indexada por `session_id` en un diccionario en memoria del proceso. Sin BBDD, sin Redis. Documenta brevemente en docstrings por qué aceptas esa volatilidad en esta fase.

### Paso 2 — Endpoint para crear sesiones

Añade `POST /sessions` que devuelve `{"session_id": "..."}`. El identificador puede ser un UUID v4. Si el cliente quiere reutilizar memoria entre páginas, el `session_id` viaja en cada petición posterior.

### Paso 3 — Soporte de adjuntos en el endpoint principal

Implementa el camino que hayas elegido (A o B). Define el endpoint `POST /sessions/{session_id}/estimate` aceptando `multipart/form-data` con dos campos:

- `transcript`: el texto de la transcripción (string).
- `attachments`: lista opcional de `UploadFile` con la documentación complementaria.

Si vas por el camino A, usa la Files API del proveedor que prefieras y referencia los archivos en el bloque de contenido del mensaje. Si vas por el camino B, extrae el texto en el servicio IA y concaténalo al transcript con un separador claro (`--- attachment: filename.pdf ---`) antes de pasarlo al prompt.

Documenta en el README qué camino elegiste y por qué.

### Paso 4 — Inyección de `project_metadata` en el system prompt

Modifica el template Jinja2 del system prompt para que reciba un bloque `<project_metadata>` con los hechos conocidos del proyecto. Si el `project_metadata` está vacío (primera llamada de la sesión), el bloque también lo está.

Después de cada respuesta del LLM, actualiza el `project_metadata` extrayendo los hechos relevantes de la nueva interacción. Para esta fase puedes hacerlo de dos maneras:

- **Heurística simple:** parsea la respuesta del LLM buscando patrones (regex o lógica básica) para extraer nombre del proyecto, tecnologías mencionadas, etc.
- **LLM extractor:** una segunda llamada al LLM con un prompt específico que devuelve un JSON con los campos del `ProjectMetadata`.

Cualquiera de las dos es válida. La heurística es más barata y rápida; el extractor es más robusto pero añade una llamada por turno. Justifica tu decisión en el README.

### Paso 5 — Gestión del historial con ventana deslizante

Implementa la lógica de ventana deslizante en `ConversationHistory`. Sugerencias:

- Mantén el system prompt como invariante (siempre presente).
- Define `MAX_TURNS = 6` como valor por defecto (ajustable por configuración). Un turno es un par user+assistant.
- Cuando se supera el límite, descarta los pares más antiguos.
- Expón un método `to_messages_list()` que devuelva el array `messages` listo para pasar a la API del LLM, con el system prompt regenerado a partir del `project_metadata` actual.

### Paso 6 — Adaptar el cliente

Ajusta tu cliente (Streamlit o el stack que estés usando) para:

- Crear una sesión al cargar la página y guardar el `session_id` en la `session_state`.
- Mostrar un campo de texto para la transcripción y un selector múltiple de archivos.
- Mostrar el `project_metadata` actual en un panel lateral o expandible (útil para debugging y para que el alumno vea la separación entre memoria y historial).
- Mantener un botón «Nueva conversación» que llame de nuevo a `POST /sessions` y resetee el estado.

### Paso 7 — Tests mínimos

Añade dos o tres tests de integración con pytest y `httpx.AsyncClient`:

1. Una sesión que enlaza dos peticiones y verifica que el `project_metadata` se actualiza correctamente.
2. Una petición con un PDF adjunto que verifica que el contenido del documento influye en la estimación (puede ser un test cualitativo: comprueba que un campo concreto del output cambia cuando se añade el adjunto).
3. Un test que envía 8 turnos a la misma sesión y verifica que el historial efectivo enviado al LLM nunca supera los `MAX_TURNS` configurados.

## Criterios de «hecho»

El ejercicio está completo cuando:

- `POST /sessions` crea una sesión y devuelve un `session_id`.
- `POST /sessions/{session_id}/estimate` acepta `multipart/form-data` con transcripción y adjuntos opcionales, y devuelve una estimación que respeta el schema Pydantic existente.
- Tras varios turnos en la misma sesión, el LLM responde con coherencia respecto al proyecto en curso (no «se olvida» del nombre del proyecto entre turnos).
- El `project_metadata` se actualiza visiblemente entre turnos.
- El historial respeta el límite de la ventana deslizante.
- Hay README breve indicando qué camino de adjuntos elegiste y por qué, y cómo extraes el `project_metadata`.
- Los tests del Paso 7 pasan en local.

## Entregable

- Una rama `pre-session-05` en tu repositorio con todos los cambios.
- README breve actualizando cómo se levanta, cómo se ejecutan los tests, qué camino de adjuntos has elegido y cómo extraes el `project_metadata`.
- Captura o GIF de la nueva interfaz mostrando una conversación de al menos tres turnos con el panel de `project_metadata` visible (opcional, pero ayuda en la review en directo).

Envía por mail a george@lidr.co el enlace a la rama (URL completa de GitHub, GitLab o el servicio que uses). El plazo es estricto: necesitamos margen para revisar las entregas y preparar el material de la sesión basándonos en los problemas reales que hayáis encontrado.

Asegúrate de que la rama es accesible (público o, si es privado, con permisos para el revisor que se te indicará en el canal del programa). Es preferible para el transcurso del programa que sea un repositorio público ya que varios mentores necesitarán acceso.

**Repositorio:** https://github.com/LIDR-academy/ai-engineering/tree/session_5
