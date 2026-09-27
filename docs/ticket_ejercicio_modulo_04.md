# Ticket — Módulo 04: del chat a una herramienta de estimación

**Fuente:** `docs/ejercicio_04.md`  
**Prioridad:** alta  
**Estado:** listo para implementar

## Qué vamos a conseguir

La aplicación dejará de pedir al usuario que escriba libremente en un chat. En su lugar tendrá un formulario que le guía para describir el proyecto y escoger el tipo de estimación que necesita.

Las instrucciones que usa la IA dejarán de estar escondidas dentro del código. Estarán en archivos separados, con una primera versión llamada `v1`, para poder mejorarlas más adelante sin desmontar la aplicación.

## Lo que ya funciona y vamos a conservar

- La aplicación ya genera estimaciones con OpenAI y Anthropic.
- La respuesta aparece poco a poco, no toda de golpe.
- Se muestran datos de la última estimación, como el modelo usado y el tiempo.
- Las claves de acceso están fuera del código.

## Lo que cambiaremos

1. **Definir los datos del formulario.**
   - Descripción del proyecto.
   - Tipo: aplicación móvil, producto web, herramienta interna o proceso de datos.
   - Nivel de detalle: breve, medio o detallado.
   - Formato de respuesta: tabla por fases, lista de tareas o explicación escrita.

2. **Crear el formulario.**
   - Sustituirá la caja de chat actual.
   - No dejará enviar una descripción demasiado corta.
   - Mantendrá el panel lateral, las métricas y la respuesta progresiva.

3. **Separar las instrucciones de la IA.**
   - Crear una carpeta de instrucciones `v1`.
   - Incluir una plantilla para las reglas generales, otra para el texto del usuario y otra con ejemplos.
   - Cambiar las reglas según el formato y el detalle elegidos en el formulario.

4. **Adaptar el servicio y la ruta de estimación.**
   - Recibir los cuatro datos del formulario.
   - Mandar por separado las reglas generales y la descripción del proyecto.
   - Devolver la estimación junto con la versión de instrucciones usada (`v1`).

5. **Añadir comprobaciones automáticas.**
   - Confirmar que la descripción entra correctamente en las instrucciones.
   - Confirmar que cada formato y nivel de detalle activa las indicaciones adecuadas.
   - Confirmar que la ruta rechaza datos incompletos o inválidos.
   - Ejecutar todas las pruebas sin usar claves ni servicios externos.

6. **Actualizar la guía del proyecto.**
   - Explicar cómo arrancar el servicio y abrir la interfaz.
   - Explicar cómo ejecutar las pruebas.

## No haremos en este ejercicio

- No cambiaremos a Ruby on Rails: seguimos con Streamlit.
- No añadiremos base de datos, usuarios, RAG ni nuevos tipos de caché.
- No obligaremos a la IA a responder en JSON todavía.
- No eliminaremos la respuesta progresiva ni los datos que ya muestra la interfaz.
- No crearemos una segunda versión de instrucciones (`v2`), proyectos de referencia adicionales ni registros avanzados: son extras para hacer solo si sobra tiempo.

## Cómo sabremos que está terminado

- El formulario tiene los cuatro campos y funciona.
- Las opciones elegidas cambian las instrucciones de la IA.
- Las instrucciones están fuera del código y tienen versión `v1`.
- La estimación sigue apareciendo poco a poco.
- Todas las pruebas pasan sin conectarse a ningún proveedor.
- El README explica cómo usarlo.

## Siguiente paso

Empezar por el contrato de datos y las opciones del formulario. Después conectaremos las plantillas y, por último, actualizaremos la interfaz y las pruebas.
