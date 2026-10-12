# estimador-cag — rama de la sesión 06

En esta rama el código **no es nuestro**: es el `estimator/` de la rama `session_06` del repo del curso (`LIDR-academy/ai-engineering`), copiado a la raíz. Nuestro estimador propio hasta la sesión 5 vive en la rama `pre-session-05`.

Se cambió de base porque el ejercicio 06 da por hecho piezas que nuestro estimador no tenía (summarizer, anclas, tier dinámico, caché, Actor-Critic-Boss, wrapper con latencia y coste, framework de evals).

Antes de proponer cambios, leer `docs/ejercicio_06.md`. El enunciado define el alcance.

## Qué pide el ejercicio

Medir, no construir. El código de `evals/stress/` ya viene en la rama de referencia. El entregable es:

* `evals/stress/results.csv`, generado por el runner contra un servidor real.
* `evals/stress/REPORT.md`, con los huecos del esqueleto rellenados con los números del CSV.

No optimizar el CAG ni mover constantes: invalidaría la comparación con RAG que se hace en el directo.

## Diferencias con el README

El `README.md` es el original del curso y dice `cd estimator`. Aquí el código está en la raíz, así que ese paso sobra.

## Límites operativos

* El servidor y `docker compose` los arranca Javi, no el agente.
* Nunca leer ni escribir `.env`.
* No hacer llamadas reales a un LLM sin autorización explícita. El runner del stress test las hace.
* No instalar, eliminar o actualizar dependencias sin discutirlo antes.
