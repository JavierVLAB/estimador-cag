# configuracion-proveedores

## Purpose

Cargar la configuración desde el entorno y seleccionar el proveedor LLM (OpenAI o Anthropic) con su modelo correspondiente.

## Requirements

### Requirement: Configuración centralizada desde el entorno
El sistema SHALL cargar su configuración mediante `pydantic-settings` en `app/config.py`, que SHALL ser el único punto del código que lee variables de entorno.

#### Scenario: Variables soportadas
- **WHEN** se carga la configuración
- **THEN** expone `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `LLM_PROVIDER`, `LLM_MODEL`, `APP_ENV` y `LOG_LEVEL`

#### Scenario: Valores por defecto
- **WHEN** no se definen `LLM_PROVIDER`, `LLM_MODEL`, `APP_ENV` ni `LOG_LEVEL`
- **THEN** toman los valores `openai`, `gpt-4o-mini`, `development` y `DEBUG` respectivamente

#### Scenario: Ningún otro módulo lee el entorno
- **WHEN** se revisan los módulos de `app/`
- **THEN** solo `config.py` accede a variables de entorno

### Requirement: Secretos fuera del código
El sistema SHALL leer las API keys exclusivamente del entorno y SHALL no incluirlas en código, tests, logs ni documentación.

#### Scenario: .env.example sin valores reales
- **WHEN** se consulta `.env.example`
- **THEN** lista todas las variables necesarias con valores vacíos o de ejemplo evidentes, sin credenciales reales

#### Scenario: El .env real no se versiona
- **WHEN** se revisa `.gitignore`
- **THEN** `.env` está excluido del control de versiones

### Requirement: Selección de proveedor LLM
El sistema SHALL soportar OpenAI y Anthropic, seleccionando el proveedor según `LLM_PROVIDER`.

#### Scenario: Proveedor OpenAI
- **WHEN** `LLM_PROVIDER` es `openai`
- **THEN** la estimación se solicita a OpenAI con el modelo indicado en `LLM_MODEL` (por defecto `gpt-4o-mini`)
- **AND** la respuesta indica `provider` igual a `openai`

#### Scenario: Proveedor Anthropic
- **WHEN** `LLM_PROVIDER` es `anthropic`
- **THEN** la estimación se solicita a Anthropic con el modelo configurado (`claude-haiku-4-5` como modelo previsto para este proveedor)
- **AND** la respuesta indica `provider` igual a `anthropic`

#### Scenario: Proveedor no soportado
- **WHEN** `LLM_PROVIDER` tiene un valor distinto de `openai` o `anthropic`
- **THEN** el sistema falla con un error claro que indica los valores admitidos

### Requirement: Gestión del proyecto con uv
El proyecto SHALL declarar sus dependencias en `pyproject.toml` y ejecutarse con `uv`, sobre Python 3.11 o superior.

#### Scenario: Dependencias declaradas
- **WHEN** se consulta `pyproject.toml`
- **THEN** incluye `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `python-dotenv`, `openai` y `anthropic`, y las dependencias de test

#### Scenario: Arranque del servidor
- **WHEN** se ejecuta `uv run uvicorn app.main:app --reload`
- **THEN** la aplicación arranca sin errores
