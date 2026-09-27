"""Interfaz Streamlit del estimador CAG con una solicitud guiada.

La pantalla recoge los datos necesarios en un formulario y los envía al API de
estimaciones. La última estimación permanece visible después de cada recarga de
Streamlit.
"""

import time
from dataclasses import dataclass

import httpx
import streamlit as st
from pydantic import ValidationError

from app.config import settings as app_settings
from app.prompts.loader import render_estimation_prompt
from app.schemas.estimation import (
    DetailLevel,
    EstimationRequest,
    EstimationResponse,
    OutputFormat,
    ProjectType,
)

TITULO_APP = "Software Estimator"
ICONO_APP = ":material/calculate:"
MINIMUM_DESCRIPTION_LENGTH = 20
ESTIMATOR_API_URL = f"{app_settings.estimator_api_base_url.rstrip('/')}/api/v1/estimate"

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


def _o_guion(valor: int | None) -> str:
    return str(valor) if valor is not None else "—"


def _solicitud_de_ejemplo() -> EstimationRequest:
    """Devuelve una solicitud segura para consultar el prompt activo."""
    return EstimationRequest(
        description=(
            "Una empresa necesita una aplicación web para controlar su inventario "
            "en varios almacenes y dar acceso a personal de oficina y almacén."
        ),
        project_type=ProjectType.WEB_SAAS,
        detail_level=DetailLevel.MEDIUM,
        output_format=OutputFormat.PHASES_TABLE,
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
    system_prompt, user_prompt = render_estimation_prompt(
        _solicitud_de_ejemplo(), version=app_settings.llm_prompt_version
    )
    st.caption(
        f"Versión {app_settings.llm_prompt_version}. "
        "Se muestra con una solicitud de ejemplo."
    )
    st.subheader("Instrucciones del sistema")
    st.code(system_prompt, language="markdown")
    st.subheader("Mensaje con la solicitud")
    st.code(user_prompt, language="markdown")


# Streamlit ejecuta todo el archivo en cada interacción. Este estado contiene
# solo lo que debe persistir para la persona usuaria entre dichas ejecuciones.
st.session_state.setdefault("last_metrics", None)
st.session_state.setdefault("last_estimation", None)

with st.sidebar:
    if st.button("System prompt", icon=":material/description:", width="stretch"):
        mostrar_system_prompt()

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
    "Describe el proyecto y elige cómo quieres recibir una estimación de esfuerzo."
)

with st.form("estimation_request", border=True):
    description = st.text_area(
        "Descripción del proyecto",
        placeholder="Explica el objetivo, las funciones principales y cualquier restricción conocida.",
        height=180,
        max_chars=2_000,
        key="estimation_description",
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
    else:
        request = EstimationRequest(
            description=clean_description,
            project_type=project_type,
            detail_level=detail_level,
            output_format=output_format,
        )
        with result_slot:
            st.subheader("Estimación")
            inicio = time.perf_counter()
            try:
                respuesta = httpx.post(
                    ESTIMATOR_API_URL,
                    json=request.model_dump(mode="json"),
                    timeout=app_settings.llm_timeout_seconds,
                )
                respuesta.raise_for_status()
                estimacion = EstimationResponse.model_validate(respuesta.json())
                st.markdown(estimacion.text)
                exito = True
            except (httpx.HTTPError, ValidationError):
                st.error(
                    "No se pudo obtener la estimación del API. Comprueba que el backend "
                    "está arrancado e inténtalo de nuevo.",
                    icon=":material/error:",
                )
                exito = False
            finally:
                tiempo = time.perf_counter() - inicio

        if exito:
            st.session_state.last_estimation = UltimaEstimacion(
                text=estimacion.text,
                prompt_version=estimacion.prompt_version,
            )
            st.session_state.last_metrics = UltimaLlamada(
                model=estimacion.model,
                provider=estimacion.provider,
                input_tokens=estimacion.usage.input_tokens,
                output_tokens=estimacion.usage.output_tokens,
                total_tokens=estimacion.usage.total_tokens,
                seconds=tiempo,
            )
            # El panel lateral se mostró antes de la llamada; al recargar queda
            # sincronizado con la estimación y las métricas recién obtenidas.
            st.rerun()
elif ultima_estimacion := st.session_state.last_estimation:
    with result_slot:
        st.subheader("Estimación")
        st.caption(f"Prompt {ultima_estimacion.prompt_version}")
        st.markdown(ultima_estimacion.text)
