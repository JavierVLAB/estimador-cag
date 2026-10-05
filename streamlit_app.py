"""Interfaz Streamlit del estimador con memoria conversacional.

La pantalla mantiene una sesión abierta: cada envío es un turno más de la misma
conversación, no una petición aislada. El identificador de sesión se conserva en
`session_state` y el backend guarda el historial.

El estado de la conversación vive en memoria del proceso del servidor, así que
se pierde al reiniciarlo. Eso no es un detalle: la interfaz comprueba que la
sesión siga existiendo y, si no, abre una nueva sin perder lo que la persona
había escrito.
"""

import time
from dataclasses import dataclass

import httpx
import streamlit as st
from pydantic import ValidationError

from app.config import settings as app_settings
from app.prompts.loader import SESSION_PROMPT_VERSION, render_session_prompt
from app.schemas.estimation import (
    DetailLevel,
    OutputFormat,
    ProjectType,
)
from app.schemas.session import ProjectMetadata

TITULO_APP = "Software Estimator"
ICONO_APP = ":material/calculate:"
MINIMUM_DESCRIPTION_LENGTH = 20
API_BASE = f"{app_settings.estimator_api_base_url.rstrip('/')}/api/v1"
SESSIONS_URL = f"{API_BASE}/sessions"
EXTENSIONES_ADMITIDAS = ["pdf", "docx"]

PROJECT_TYPE_LABELS = {
    ProjectType.MOBILE_APP: "Aplicación móvil",
    ProjectType.WEB_SAAS: "Aplicación web o SaaS",
    ProjectType.INTERNAL_TOOL: "Herramienta interna",
    ProjectType.DATA_PIPELINE: "Proceso o canal de datos",
}
DETAIL_LEVEL_LABELS = {
    DetailLevel.SUMMARY: "Resumen",
    DetailLevel.MEDIUM: "Intermedio",
    DetailLevel.DETAILED: "Detallado",
}
OUTPUT_FORMAT_LABELS = {
    OutputFormat.PHASES_TABLE: "Tabla por fases",
    OutputFormat.LINE_ITEMS: "Lista de partidas",
    OutputFormat.NARRATIVE: "Texto por fases",
}


@dataclass(frozen=True)
class UltimaLlamada:
    """Métricas de la última estimación generada, para el panel lateral."""

    model: str
    provider: str
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    seconds: float


@dataclass(frozen=True)
class UltimaEstimacion:
    """Resultado que debe seguir visible tras la recarga de Streamlit."""

    text: str
    prompt_version: str


@dataclass(frozen=True)
class RespuestaDeTurno:
    """Respuesta del backend tras un turno, con lo que hay que recordar."""

    text: str
    prompt_version: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    metadata: ProjectMetadata
    turns_kept: int


def _o_guion(valor: int | None) -> str:
    return str(valor) if valor is not None else "—"


def _crear_sesion() -> str | None:
    """Abre una sesión conversacional y devuelve su identificador.

    Devuelve `None` en lugar de propagar el fallo: sin sesión no hay nada que
    mostrar, pero la pantalla debe seguir explicando qué ha pasado en vez de
    romperse con una excepción.
    """
    try:
        respuesta = httpx.post(SESSIONS_URL, timeout=app_settings.llm_timeout_seconds)
        respuesta.raise_for_status()
        return str(respuesta.json()["session_id"])
    except (httpx.HTTPError, KeyError, ValueError):
        return None


def _enviar_turno(
    *,
    session_id: str,
    description: str,
    project_type: str,
    detail_level: str,
    output_format: str,
    archivos: list,
) -> tuple[httpx.Response | None, str]:
    """Envía un turno. Devuelve la respuesta y el `session_id` a usar después.

    El `session_id` puede cambiar: si el backend responde 404 porque la sesión se
    perdió al reiniciar, se abre una nueva y se reintenta una vez con la misma
    transcripción. Perder lo que la persona había escrito por un reinicio del
    servidor sería un fallo de la interfaz, no del usuario.

    Los archivos viajan como lista plana de tuplas: `httpx` no admite una lista
    de archivos como valor de una clave del diccionario.
    """
    campos = {
        "description": description,
        "project_type": project_type,
        "detail_level": detail_level,
        "output_format": output_format,
    }

    def enviar(destino: str) -> httpx.Response:
        if not archivos:
            # Sin adjuntos no hace falta multipart; el endpoint acepta también
            # el formulario urlencoded cuando no recibe ningún archivo.
            return httpx.post(
                f"{SESSIONS_URL}/{destino}/estimate",
                data=campos,
                timeout=app_settings.llm_timeout_seconds,
            )
        partes: list[tuple[str, object]] = [("files", (archivo.name, archivo.getvalue(), "application/octet-stream")) for archivo in archivos]
        return httpx.post(
            f"{SESSIONS_URL}/{destino}/estimate",
            data=campos,
            files=partes,
            timeout=app_settings.llm_timeout_seconds,
        )

    respuesta = enviar(session_id)
    if respuesta.status_code == 404:
        nueva = _crear_sesion()
        if nueva is not None:
            return enviar(nueva), nueva
    return respuesta, session_id


def _leer_turno(respuesta: httpx.Response) -> RespuestaDeTurno:
    cuerpo = respuesta.json()
    uso = cuerpo.get("usage", {})
    return RespuestaDeTurno(
        text=cuerpo["text"],
        prompt_version=cuerpo["prompt_version"],
        model=cuerpo["model"],
        provider=cuerpo["provider"],
        input_tokens=uso.get("input_tokens"),
        output_tokens=uso.get("output_tokens"),
        total_tokens=uso.get("total_tokens"),
        metadata=ProjectMetadata.model_validate(cuerpo.get("metadata", {})),
        turns_kept=cuerpo.get("turns_kept", 0),
    )


st.set_page_config(
    page_title=TITULO_APP,
    page_icon=ICONO_APP,
    layout="centered",
)

st.html(
    """
    <style>
    [data-testid="stMainBlockContainer"] {
        padding-top: 3rem;
    }
    </style>
    """
)


@st.dialog("Prompt activo", width="large")
def mostrar_system_prompt() -> None:
    """Muestra las instrucciones que recibe el modelo en un turno de sesión."""
    system_prompt, user_prompt = render_session_prompt(
        transcript="Transcripción de la reunión.",
        project_type=ProjectType.WEB_SAAS.value,
        detail_level=DetailLevel.MEDIUM.value,
        output_format=OutputFormat.PHASES_TABLE.value,
        metadata=ProjectMetadata(),
        version=SESSION_PROMPT_VERSION,
    )
    st.caption(
        f"Versión {SESSION_PROMPT_VERSION}, la que usan los turnos de sesión. "
        "Se muestra con una transcripción de ejemplo y sin datos de proyecto."
    )
    st.subheader("Instrucciones del sistema")
    st.code(system_prompt, language="markdown")
    st.subheader("Mensaje del turno")
    st.code(user_prompt, language="markdown")


# Streamlit ejecuta todo el archivo en cada interacción. Este estado contiene
# solo lo que debe persistir para la persona usuaria entre esas ejecuciones.
st.session_state.setdefault("session_id", None)
st.session_state.setdefault("session_metadata", ProjectMetadata())
st.session_state.setdefault("turns_kept", 0)
st.session_state.setdefault("last_metrics", None)
st.session_state.setdefault("last_estimation", None)
st.session_state.setdefault("session_error", None)
st.session_state.setdefault("form_generation", 0)

# La sesión se abre al cargar, no al enviar: así el backend puede rejectar un id
# desconocido desde el primer turno.
if st.session_state.session_id is None:
    st.session_state.session_id = _crear_sesion()
    st.session_state.session_error = (
        None if st.session_state.session_id else "No se pudo abrir una sesión en el backend."
    )


def _panel_de_sesion() -> None:
    """Muestra los datos del proyecto que el backend ha ido extrayendo."""
    metadata: ProjectMetadata = st.session_state.session_metadata
    st.subheader("Contexto del proyecto")

    if metadata.is_empty():
        # Estado vacío de verdad, no un fallo: el primer turno aún no ha fijado
        # ningún hecho y conviene decirlo en lugar de mostrar campos en blanco.
        st.caption("Todavía no hay datos del proyecto. Aparecerán tras el primer turno.")
        return

    if metadata.project_name:
        st.caption(f"**Proyecto:** {metadata.project_name}")
    if metadata.assumed_team_size:
        st.caption(f"**Equipo:** {metadata.assumed_team_size} personas")
    if metadata.mentioned_technologies:
        st.caption(f"**Tecnologías:** {', '.join(metadata.mentioned_technologies)}")
    if metadata.agreed_scope:
        st.caption(f"**Alcance:** {metadata.agreed_scope}")

    st.divider()
    # El límite lo fija el backend en su configuración. La interfaz lee la misma
    # constante porque comparte el módulo de settings; el valor informativo para
    # la persona usuaria es cuántos turnos quedan, no el número en sí.
    st.caption(
        f"**Turnos conservados:** {st.session_state.turns_kept} "
        f"de {app_settings.session_max_turns}"
    )


with st.sidebar:
    if st.button("System prompt", icon=":material/description:", width="stretch"):
        mostrar_system_prompt()

    if st.button("Nueva conversación", icon=":material/add:", width="stretch"):
        nueva = _crear_sesion()
        st.session_state.session_id = nueva
        st.session_state.session_metadata = ProjectMetadata()
        st.session_state.turns_kept = 0
        st.session_state.session_error = (
            None if nueva else "No se pudo abrir una sesión en el backend."
        )
        st.session_state.last_estimation = None
        st.session_state.last_metrics = None
        st.rerun()

    if st.session_state.session_error:
        st.warning(st.session_state.session_error, icon=":material/warning:")

    _panel_de_sesion()

    with st.expander("Parámetros de entrada", expanded=False):
        st.caption(f"**Proveedor:** {app_settings.llm_provider}")
        st.caption(f"**Modelo:** {app_settings.llm_model}")
        st.caption(f"**Máx. tokens de salida:** {app_settings.llm_max_output_tokens}")
        st.caption(f"**Tiempo máximo:** {app_settings.llm_timeout_seconds:.0f} s")
        st.caption(f"**Reintentos:** {app_settings.llm_max_retries}")

    with st.expander("Parámetros de salida", expanded=True):
        ultima_llamada: UltimaLlamada | None = st.session_state.last_metrics
        ultima_estimacion: UltimaEstimacion | None = st.session_state.last_estimation
        if ultima_llamada:
            st.caption(f"**Modelo:** {ultima_llamada.model} ({ultima_llamada.provider})")
            st.caption(
                f"**Tokens:** {_o_guion(ultima_llamada.input_tokens)} entrada · "
                f"{_o_guion(ultima_llamada.output_tokens)} salida · "
                f"{_o_guion(ultima_llamada.total_tokens)} total"
            )
            st.caption(f"**Tiempo:** {ultima_llamada.seconds:.2f} s")
            if ultima_estimacion:
                st.caption(f"**Versión del prompt:** {ultima_estimacion.prompt_version}")
        else:
            st.caption("Todavía no hay ninguna llamada.")

st.title(TITULO_APP, icon=ICONO_APP)
st.caption(
    "Describe el proyecto y elige cómo quieres recibir una estimación. "
    "Cada envío añade un turno a la conversación."
)

with st.form("estimation_request", border=True):
    description = st.text_area(
        "Descripción del proyecto",
        placeholder="Explica el objetivo, las funciones principales y cualquier restricción conocida.",
        height=180,
        max_chars=2_000,
        # El sufijo fuerza un widget nuevo tras cada envío: sin él Streamlit
        # conserva el texto porque el `key` sigue registrado en session_state.
        key=f"estimation_description_{st.session_state.form_generation}",
    )
    project_type = st.selectbox(
        "Tipo de proyecto",
        options=list(ProjectType),
        format_func=PROJECT_TYPE_LABELS.__getitem__,
        key="estimation_project_type",
    )
    detail_level = st.selectbox(
        "Nivel de detalle",
        options=list(DetailLevel),
        format_func=DETAIL_LEVEL_LABELS.__getitem__,
        key="estimation_detail_level",
    )
    output_format = st.selectbox(
        "Formato de la estimación",
        options=list(OutputFormat),
        format_func=OUTPUT_FORMAT_LABELS.__getitem__,
        key="estimation_output_format",
    )
    archivos = st.file_uploader(
        "Documentación adjunta (opcional)",
        type=EXTENSIONES_ADMITIDAS,
        accept_multiple_files=True,
        key=f"estimation_attachments_{st.session_state.form_generation}",
    )
    submitted = st.form_submit_button(
        "Generar estimación",
        icon=":material/auto_awesome:",
        type="primary",
    )

result_slot = st.container()

if submitted:
    clean_description = description.strip()
    if len(clean_description) < MINIMUM_DESCRIPTION_LENGTH:
        result_slot.error(
            "Describe el proyecto con al menos 20 caracteres.",
            icon=":material/error:",
        )
    elif st.session_state.session_id is None:
        result_slot.error(
            "No hay ninguna sesión abierta en el backend. Recarga la página para "
            "reintentarlo.",
            icon=":material/error:",
        )
    else:
        with result_slot:
            st.subheader("Estimación")
            inicio = time.perf_counter()
            try:
                respuesta, session_id_usada = _enviar_turno(
                    session_id=st.session_state.session_id,
                    description=clean_description,
                    project_type=project_type.value,
                    detail_level=detail_level.value,
                    output_format=output_format.value,
                    archivos=archivos or [],
                )
                if respuesta is None:
                    raise httpx.HTTPError("sin respuesta")
                if respuesta.status_code == 404:
                    raise httpx.HTTPStatusError(
                        "404 Not Found",
                        request=httpx.Request("POST", SESSIONS_URL),
                        response=respuesta,
                    )
                respuesta.raise_for_status()
                turno = _leer_turno(respuesta)
                st.markdown(turno.text)
                exito = True
            except (httpx.HTTPError, ValidationError, KeyError):
                st.error(
                    "No se pudo obtener la estimación del API. Comprueba que el backend "
                    "está arrancado e inténtalo de nuevo.",
                    icon=":material/error:",
                )
                exito = False
            finally:
                tiempo = time.perf_counter() - inicio

        if exito:
            # Descarta el texto y los adjuntos enviados: el turno ya está en el
            # historial del backend y dejarlos invites a reenviarlo por error.
            st.session_state.form_generation += 1
            st.session_state.session_id = session_id_usada
            st.session_state.session_metadata = turno.metadata
            st.session_state.turns_kept = turno.turns_kept
            st.session_state.last_estimation = UltimaEstimacion(
                text=turno.text,
                prompt_version=turno.prompt_version,
            )
            st.session_state.last_metrics = UltimaLlamada(
                model=turno.model,
                provider=turno.provider,
                input_tokens=turno.input_tokens,
                output_tokens=turno.output_tokens,
                total_tokens=turno.total_tokens,
                seconds=tiempo,
            )
            # El panel lateral se mostró antes de la llamada; al recargar queda
            # sincronizado con la estimación, el contexto y las métricas nuevas.
            st.rerun()
elif ultima_estimacion := st.session_state.last_estimation:
    with result_slot:
        st.subheader("Estimación")
        st.caption(f"Prompt {ultima_estimacion.prompt_version}")
        st.markdown(ultima_estimacion.text)