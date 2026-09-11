## ADDED Requirements

### Requirement: Health check
El sistema SHALL exponer `GET /health` para comprobar que el servicio está operativo.

#### Scenario: Servicio operativo
- **WHEN** se solicita `GET /health`
- **THEN** responde `200` con un JSON que indica el estado del servicio
- **AND** no realiza ninguna llamada al proveedor LLM

### Requirement: Documentación automática de la API
El sistema SHALL publicar la documentación Swagger en `/docs`, con título y descripción de la API, y con los campos de request y response descritos en los schemas Pydantic.

#### Scenario: Swagger accesible
- **WHEN** se accede a `/docs`
- **THEN** se muestra la documentación con el título y la descripción de la API y el endpoint de estimación documentado

### Requirement: Documentación del proyecto para alguien nuevo
El `README.md` SHALL documentar la versión 1.0 y permitir que una persona que no conoce el proyecto entienda qué hace y lo ponga en marcha.

#### Scenario: Contenido del README
- **WHEN** se lee el `README.md`
- **THEN** explica qué hace el sistema, qué es la arquitectura CAG y por qué se usa aquí, el flujo completo (recibir transcripción, inyectar contexto, llamar al LLM, devolver respuesta), el setup con `uv`, las variables de entorno y un ejemplo de llamada con `curl`
- **AND** indica que la versión documentada es la 1.0

### Requirement: Verificación sin llamadas reales al LLM
El sistema SHALL incluir tests que cubran el health check y el endpoint de estimación con el cliente LLM mockeado, sin realizar llamadas reales a ningún proveedor.

#### Scenario: Tests con mock
- **WHEN** se ejecuta la suite de tests
- **THEN** pasa sin necesidad de API keys válidas y sin tráfico de red hacia los proveedores
