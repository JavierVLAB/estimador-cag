"""Interfaz conversacional Streamlit del estimador CAG.

Permite pegar la transcripción de una reunión y ver la estimación token a
token mientras el modelo la genera. Reutiliza el mismo servicio, prompt y
configuración que el endpoint HTTP: el CAG no se duplica en la interfaz.
El historial es solo visual; cada estimación es independiente.
"""

import time
from dataclasses import dataclass

import streamlit as st

from app.config import settings as app_settings
from app.context.examples import ESTIMATION_EXAMPLES
from app.services.llm_service import (
    LLMServiceError,
    build_system_prompt,
    generate_estimation_stream,
)

TITULO_APP = "Wrapper de estimación"
ICONO_APP = ":material/calculate:"


@dataclass(frozen=True)
class UltimaLlamada:
    """Métricas de la última estimación generada, para mostrar en el sidebar."""

    model: str
    provider: str
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    seconds: float


def _o_guion(valor: int | None) -> str:
    return str(valor) if valor is not None else "—"


st.set_page_config(
    page_title=TITULO_APP,
    page_icon=ICONO_APP,
    layout="centered",
)


@st.dialog("System prompt activo", width="large")
def mostrar_system_prompt() -> None:
    st.markdown(build_system_prompt())


@st.dialog("Estimaciones de referencia (contexto CAG)", width="large")
def mostrar_ejemplos() -> None:
    for ejemplo in ESTIMATION_EXAMPLES:
        with st.expander(ejemplo.name):
            st.caption(ejemplo.meeting_summary)
            st.markdown(ejemplo.estimation)


# El historial y las métricas viven en session_state porque Streamlit re-ejecuta
# el script completo con cada interacción; sin esto se perderían en cada turno.
if "messages" not in st.session_state:
    st.session_state.messages = []

if "last_metrics" not in st.session_state:
    st.session_state.last_metrics = None

# El sidebar se renderiza en el panel lateral independientemente de dónde
# aparezca en el script; va antes del chat para leer el código de arriba abajo.
with st.sidebar:
    st.subheader("Contexto CAG")
    if st.button("System prompt", icon=":material/description:", width="stretch"):
        mostrar_system_prompt()
    if st.button("Ejemplos", icon=":material/library_books:", width="stretch"):
        mostrar_ejemplos()

    st.subheader("Parámetros del proveedor", icon=":material/tune:")
    with st.container(border=True):
        st.caption(f"**Proveedor:** {app_settings.llm_provider}")
        st.caption(f"**Modelo:** {app_settings.llm_model}")
        st.caption(f"**Máx. tokens de salida:** {app_settings.llm_max_output_tokens}")
        st.caption(f"**Timeout:** {app_settings.llm_timeout_seconds:.0f} s")
        st.caption(f"**Reintentos:** {app_settings.llm_max_retries}")
        st.caption("La temperatura no se fija: usa el valor por defecto del SDK del proveedor.")

    st.subheader("Última estimación", icon=":material/monitoring:")
    ultima: UltimaLlamada | None = st.session_state.last_metrics
    if ultima:
        with st.container(border=True):
            st.caption(f"**Modelo:** {ultima.model} ({ultima.provider})")
            st.caption(
                f"**Tokens:** {_o_guion(ultima.input_tokens)} entrada · "
                f"{_o_guion(ultima.output_tokens)} salida · "
                f"{_o_guion(ultima.total_tokens)} total"
            )
            st.caption(f"**Tiempo:** {ultima.seconds:.2f} s")
    else:
        st.caption("Todavía no hay ninguna llamada.")

st.title(TITULO_APP, icon=ICONO_APP)
st.caption(
    "Escribe la transcripción de una reunión para obtener una estimación de esfuerzo "
    "generada por IA, usando como referencia estimaciones reales anteriores."
)

for mensaje in st.session_state.messages:
    with st.chat_message(mensaje["role"]):
        st.markdown(mensaje["content"])

if transcripcion := st.chat_input(
    "Escribe la transcripción de la reunión", height=60
):
    st.session_state.messages.append({"role": "user", "content": transcripcion})
    with st.chat_message("user"):
        st.markdown(transcripcion)

    with st.chat_message("assistant"):
        # El tiempo se mide en la interfaz, no en el servicio: el stream
        # consume la salida aquí, alrededor de la iteración de st.write_stream.
        inicio = time.perf_counter()
        flujo = generate_estimation_stream(transcripcion)
        try:
            texto = st.write_stream(flujo)
            exito = True
        except LLMServiceError:
            st.error("El proveedor LLM no pudo generar la estimación.", icon=":material/error:")
            exito = False
        finally:
            tiempo = time.perf_counter() - inicio

        if exito:
            # Solo las respuestas completas entran en el historial; una
            # respuesta fallida se muestra como error y desaparece al re-render.
            st.session_state.messages.append({"role": "assistant", "content": texto})
            st.session_state.last_metrics = UltimaLlamada(
                model=flujo.model,
                provider=flujo.provider,
                input_tokens=flujo.usage.input_tokens if flujo.usage else None,
                output_tokens=flujo.usage.output_tokens if flujo.usage else None,
                total_tokens=flujo.usage.total_tokens if flujo.usage else None,
                seconds=tiempo,
            )
            # El sidebar ya se renderizó al principio de este script run con las
            # métricas anteriores; sin este rerun, las nuevas solo se verían
            # después de la siguiente interacción del usuario.
            st.rerun()