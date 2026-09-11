# estimador-cag

Servicio FastAPI que recibe la transcripción de una reunión y devuelve una estimación de software generada por un LLM.

Es el Proyecto 1 del curso AI Engineering 2026/09 (Sesión 2).

Antes de proponer cambios, leer `docs/ejercicio.md`. El enunciado define el alcance y tiene prioridad sobre mejoras o extensiones no solicitadas.

## Arquitectura

Este proyecto usa **CAG deliberadamente**: todo el contexto necesario viaja en cada llamada al modelo.

No hay:

* base de datos
* retrieval
* vector store
* persistencia
* caché

Esto no es deuda técnica pendiente. Los datos de referencia son pequeños y caben en contexto. El objetivo del ejercicio es trabajar la calidad del prompt antes de evolucionar a RAG en módulos posteriores.

No introducir estas capas ni rediseñar la arquitectura salvo que el enunciado o Javi lo pidan explícitamente.

Si detectas una limitación arquitectónica relevante, señálala y detente antes de cambiar el enfoque.

## Estructura

La estructura base la fija el enunciado y no se modifica sin discutirlo:

```text
app/
├── main.py          # aplicación FastAPI, health check, montaje de routers
├── config.py        # Settings con pydantic-settings, lee .env
├── routers/         # endpoints HTTP
├── services/        # lógica de negocio y llamadas al LLM
└── context/         # datos estáticos inyectados en el prompt
```

La separación es intencional aunque el ejercicio pudiera resolverse en menos archivos.

Mantén los cambios dentro de esta estructura salvo necesidad explícita.

## Stack

* Python 3.11+
* `uv` como gestor de paquetes
* FastAPI + uvicorn
* `pydantic-settings`
* Proveedor seleccionable mediante `LLM_PROVIDER`
* OpenAI: `gpt-4o-mini`
* Anthropic: `claude-haiku-4-5`

No sustituir herramientas, librerías o modelos por preferencias propias sin una razón ligada al ejercicio.

## Comandos

```bash
uv sync
uv run uvicorn app.main:app --reload
```

El servidor lo ejecuta Javi, no el agente.

## Límites operativos

* Nunca arrancar servidores, watchers o procesos de larga duración.
* Nunca leer ni escribir `.env`.
* Documentar variables nuevas en `.env.example`, sin valores reales.
* Nunca introducir API keys o secretos en código, tests, logs o documentación.
* La configuración debe pasar por `config.py`.
* No realizar llamadas reales a un LLM sin autorización explícita.
* No instalar, eliminar o actualizar dependencias sin discutirlo antes.

## Forma de trabajo

Respeta el modo actual de la tarea.

Si estamos analizando, diseñando o planificando, no empieces a modificar código. “Continúa” significa continuar en el modo actual, no pasar automáticamente a implementación.

No interpretes una preferencia, una opción elegida o una discusión técnica como autorización para implementar.

Mantén el cambio mínimo necesario para el objetivo actual. Evita refactors, limpieza lateral o mejoras no relacionadas.

Si falta información que cambia materialmente la solución, señálalo antes de asumirla.

## OpenSpec

OpenSpec está inicializado en `openspec/`.

Antes de implementar cualquier cambio de código:

1. Leer `docs/ejercicio.md`.
2. Leer las specs relevantes de `openspec/`.
3. Crear el change con `/opsx:propose`.
4. Esperar aprobación explícita.
5. Solo entonces modificar código.

Aprobar una idea, decir “me gusta la opción A” o pedir que continúes no autoriza por sí mismo a escribir código.

## Convenciones de código

* Código claro, legible y auditable.
* Seguir las convenciones existentes del proyecto.
* Archivos cortos y responsabilidades claras.
* Comentarios y docstrings en español cuando aporten valor.
* Explicar el **por qué**, no describir código evidente.
* Preferir soluciones simples frente a abstracciones prematuras.

## Verificación

No afirmar que algo funciona solo porque el código parece correcto.

Después de implementar:

* ejecutar las comprobaciones locales apropiadas
* usar tests o mocks antes que llamadas reales al LLM
* verificar primero la parte modificada
* ampliar la validación solo si aporta valor

Si algo falla, inspeccionar la causa antes de hacer cambios adicionales.

No modificar varias cosas especulativamente para intentar hacer desaparecer un error.
