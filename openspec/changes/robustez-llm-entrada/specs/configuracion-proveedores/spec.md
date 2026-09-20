## ADDED Requirements

### Requirement: Configuración de timeout, reintentos y límite de salida
El sistema SHALL construir los clientes LLM con `timeout` y `max_retries` configurables desde `Settings`, y SHALL acotar el tamaño de la respuesta con `max_tokens` configurable.

#### Scenario: Clientes con timeout y reintentos
- **WHEN** se construye un cliente OpenAI o Anthropic
- **THEN** el cliente se crea con `timeout = settings.llm_timeout_seconds` y `max_retries = settings.llm_max_retries`

#### Scenario: Límite de tokens de salida configurable
- **WHEN** se llama al proveedor LLM
- **THEN** la petición incluye `max_tokens = settings.llm_max_output_tokens`

#### Scenario: Variables documentadas sin valores reales
- **WHEN** se consulta `.env.example`
- **THEN** aparecen `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES` y `LLM_MAX_OUTPUT_TOKENS` sin valores reales

### Requirement: Sin código muerto en la configuración
El sistema SHALL no mantener constantes definidas que no se usan en ningún punto del código.

#### Scenario: Constante eliminada
- **WHEN** se revisa `config.py`
- **THEN** no existe `MODELOS_RECOMENDADOS` ni ningún referente a ella en `app/`