"""Pruebas del render de prompts versionados, sin llamar al LLM."""

import pytest
from jinja2 import UndefinedError

from app.prompts import loader
from app.prompts.loader import PROMPT_VERSION, render_estimation_prompt
from app.schemas.estimation import (
    DetailLevel,
    EstimationRequest,
    OutputFormat,
    ProjectType,
)


def _request(
    *,
    detail_level: DetailLevel = DetailLevel.MEDIUM,
    output_format: OutputFormat = OutputFormat.PHASES_TABLE,
    description: str = "Una descripción única del proyecto para esta prueba.",
) -> EstimationRequest:
    return EstimationRequest(
        description=description,
        project_type=ProjectType.WEB_SAAS,
        detail_level=detail_level,
        output_format=output_format,
    )


def test_la_descripcion_aparece_solo_en_el_bloque_de_usuario() -> None:
    description = "Proyecto único: portal de reservas con calendario compartido."

    system, user = render_estimation_prompt(_request(description=description))

    assert description not in system
    assert f"<project_description>\n{description}\n</project_description>" in user


def test_el_formato_por_fases_activa_la_instruccion_de_tabla() -> None:
    system, _ = render_estimation_prompt(
        _request(output_format=OutputFormat.PHASES_TABLE)
    )

    assert "tabla Markdown por fases" in system


def test_el_formato_por_partidas_activa_su_instruccion() -> None:
    system, _ = render_estimation_prompt(
        _request(output_format=OutputFormat.LINE_ITEMS)
    )

    assert "lista numerada de partidas concretas" in system
    assert "tabla Markdown por fases" not in system


def test_el_nivel_detallado_pide_supuestos_por_fase() -> None:
    system, _ = render_estimation_prompt(_request(detail_level=DetailLevel.DETAILED))

    assert "supuestos por fase" in system


def test_el_nivel_resumido_no_pide_supuestos_por_fase() -> None:
    system, _ = render_estimation_prompt(_request(detail_level=DetailLevel.SUMMARY))

    assert "supuestos por fase" not in system
    assert "Sé conciso" in system


def test_el_system_prompt_incluye_ejemplos_de_referencia() -> None:
    system, _ = render_estimation_prompt(_request())

    assert "<examples>" in system
    assert system.count("<example>") >= 2


def test_v2_incluye_referencias_adicionales_y_diversas() -> None:
    system, _ = render_estimation_prompt(_request(), version="v2")

    assert system.count("<example>") == 4
    assert "aplicación móvil" in system
    assert "ficheros CSV" in system


def test_v2_conserva_la_descripcion_en_el_mensaje_de_usuario() -> None:
    description = "Proyecto único: portal de reservas con calendario compartido."

    system, user = render_estimation_prompt(_request(description=description), version="v2")

    assert description not in system
    assert f"<project_description>\n{description}\n</project_description>" in user


def test_el_render_falla_si_una_plantilla_usa_una_variable_ausente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    template = loader._environment.from_string("{{ variable_que_no_existe }}")
    monkeypatch.setattr(loader._environment, "get_template", lambda _: template)

    with pytest.raises(UndefinedError):
        render_estimation_prompt(_request())


def test_la_version_por_defecto_es_v1() -> None:
    assert PROMPT_VERSION == "v1"
