"""Pruebas del render de plantillas.

`StrictUndefined` hace que una variable mal escrita reviente aquí, antes de
iniciar una llamada al proveedor. Estos tests son la red que lo comprueba.
"""

from __future__ import annotations

import pytest

from app.prompts.loader import (
    render_estimation_prompt,
    render_metadata_extraction_prompt,
    render_session_prompt,
)
from app.schemas.estimation import (
    DetailLevel,
    EstimationRequest,
    OutputFormat,
    ProjectType,
)
from app.schemas.session import ProjectMetadata

BASE = {
    "project_type": "web_app",
    "detail_level": "medium",
    "output_format": "phases_table",
}


# --- v1/v2, sin cambios de comportamiento ------------------------------------


def test_una_version_desconocida_falla() -> None:
    with pytest.raises(Exception):
        render_estimation_prompt(_request(), version="v99")


def test_el_render_devuelve_sistema_y_usuario_separados() -> None:
    system, user = render_estimation_prompt(_request(), version="v2")

    assert system and user
    assert system != user


# --- v3, con metadata --------------------------------------------------------


def test_la_metadata_conocida_aparece_en_el_system_prompt() -> None:
    metadata = ProjectMetadata(
        project_name="Portal de reservas",
        assumed_team_size=4,
        mentioned_technologies=["React", "Postgres"],
        agreed_scope="Solo el motor de disponibilidad",
    )

    system, _ = render_session_prompt(
        transcript="Hablamos del portal.", metadata=metadata, version="v3", **BASE
    )

    assert "Portal de reservas" in system
    assert "4 personas" in system
    assert "React, Postgres" in system
    assert "Solo el motor de disponibilidad" in system


def test_sin_metadata_el_bloque_dice_explicitamente_que_no_hay_datos() -> None:
    """El primer turno también lleva el bloque, para que el formato sea estable."""
    system, _ = render_session_prompt(
        transcript="Primera reunion.",
        metadata=ProjectMetadata(),
        version="v3",
        **BASE,
    )

    assert "<project_metadata>" in system
    assert "Todavía no se ha establecido ningún dato" in system
    assert "4 personas" not in system


def test_la_metadata_parcial_no_inventa_los_campos_ausentes() -> None:
    system, _ = render_session_prompt(
        transcript="Segunda reunion.",
        metadata=ProjectMetadata(project_name="Portal"),
        version="v3",
        **BASE,
    )

    assert "Portal" in system
    assert "Tamaño de equipo" not in system
    assert "Tecnologías" not in system


def test_la_transcripcion_del_turno_se_inyecta() -> None:
    _, user = render_session_prompt(
        transcript="Queremos integrar pasarela de pago.",
        metadata=ProjectMetadata(),
        version="v3",
        **BASE,
    )

    assert "pasarela de pago" in user


def test_un_adjunto_conserva_su_valla_al_rendereizar() -> None:
    _, user = render_session_prompt(
        transcript=(
            "Hablamos del portal.\n\n"
            "--- attachment: especificacion.pdf ---\n"
            "Trece milestones.\n"
            "--- end attachment ---"
        ),
        metadata=ProjectMetadata(),
        version="v3",
        **BASE,
    )

    assert "--- attachment: especificacion.pdf ---" in user
    assert "Trece milestones." in user


def test_v3_no_arrastra_los_ejemplos_de_otra_version_por_accidente() -> None:
    """Cada versión tiene su directorio; `include` debe apuntar al suyo."""
    system, _ = render_session_prompt(
        transcript="x", metadata=ProjectMetadata(), version="v3", **BASE
    )

    assert "<examples>" in system


# --- Extractor de metadata ---------------------------------------------------


def test_el_extractor_pide_las_cuatro_claves() -> None:
    system, user = render_metadata_extraction_prompt(transcript="Hablamos del portal.")

    for clave in (
        "project_name",
        "assumed_team_size",
        "mentioned_technologies",
        "agreed_scope",
    ):
        assert clave in system
    assert "Hablamos del portal." in user


def test_el_extractor_admite_la_conversacion_anterior() -> None:
    _, user = render_metadata_extraction_prompt(
        transcript="Ahora con Redis.",
        conversation="Turno 1: se llama Portal.",
    )

    assert "Turno 1: se llama Portal." in user
    assert "<conversation_so_far>" in user


def test_sin_conversacion_anterior_no_aparece_el_bloque_vacio() -> None:
    _, user = render_metadata_extraction_prompt(transcript="Ahora con Redis.")

    assert "<conversation_so_far>" not in user


def test_las_plantillas_del_extractor_no_se_confunden_con_las_de_estimacion() -> None:
    """Un `include` mal puesto haría que el extractor estimara, o al revés."""
    system, _ = render_metadata_extraction_prompt(transcript="x")

    assert "estimación realista" not in system
    assert "formato_solicitado" not in system


def _request() -> EstimationRequest:
    return EstimationRequest(
        description="Portal de reservas para un hotel.",
        project_type=ProjectType.WEB_SAAS,
        detail_level=DetailLevel.MEDIUM,
        output_format=OutputFormat.PHASES_TABLE,
    )