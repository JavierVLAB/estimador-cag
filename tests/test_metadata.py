"""Pruebas de la extracción de `project_metadata`.

El proveedor se sustituye por un doble en todos los casos: ningún test debe
necesitar API keys ni salir a la red. Lo que se comprueba es el contrato del
extractor y, sobre todo, su degradación, que es donde está el riesgo real.
"""

from __future__ import annotations

import json

import pytest

from app.schemas.session import ProjectMetadata
from app.services import llm_service, metadata


class _GeneradorFalso:
    """Sustituto de `llm_service.generate_turn` que devuelve texto fijo."""

    def __init__(self, texto: str | Exception) -> None:
        self.texto = texto
        self.llamadas: list[dict] = []

    def __call__(self, *, system_prompt: str, messages: list[dict], **kwargs) -> object:
        self.llamadas.append({"system": system_prompt, "messages": messages, **kwargs})
        if isinstance(self.texto, Exception):
            raise self.texto
        return llm_service.CompletionResult(
            text=self.texto,
            model="gpt-4o-mini",
            provider="openai",
            usage=llm_service.TokenUsage(
                input_tokens=10, output_tokens=5, total_tokens=15
            ),
        )


@pytest.fixture
def generador(monkeypatch: pytest.MonkeyPatch):
    """Instala un generador falso y devuelve la fábrica para configurarlo."""

    def instalar(texto: str | Exception) -> _GeneradorFalso:
        falso = _GeneradorFalso(texto)
        monkeypatch.setattr(llm_service, "generate_turn", falso)
        return falso

    return instalar


# --- Interpretación de la respuesta ------------------------------------------


def test_un_json_limpido_se_interpreta() -> None:
    respuesta = json.dumps(
        {
            "project_name": "Portal de reservas",
            "assumed_team_size": 4,
            "mentioned_technologies": ["React"],
            "agreed_scope": "Solo disponibilidad",
        }
    )

    metadata_extraida = metadata._parsear(respuesta)

    assert metadata_extraida.project_name == "Portal de reservas"
    assert metadata_extraida.assumed_team_size == 4


def test_un_json_en_bloque_de_codigo_se_interpreta() -> None:
    respuesta = 'Aquí tienes:\n```json\n{"project_name": "Portal"}\n```'

    assert metadata._parsear(metadata._quitar_valla(respuesta)).project_name == "Portal"


def test_un_json_rodeado_de_texto_se_interpreta() -> None:
    respuesta = 'Hecho. {"project_name": "Portal", "agreed_scope": null} Fin.'

    assert metadata._parsear(metadata._quitar_valla(respuesta)).project_name == "Portal"


def test_un_campo_desconocido_se_ignora_en_lugar_de_romper() -> None:
    respuesta = '{"project_name": "Portal", "budget": "100k"}'

    assert metadata._parsear(respuesta).project_name == "Portal"


def test_una_lista_en_lugar_de_objeto_se_rechaza() -> None:
    with pytest.raises(ValueError):
        metadata._parsear("[1, 2, 3]")


def test_un_valor_de_tipo_incorrecto_se_rechaza() -> None:
    """`team_size` es int; un string debe fallar en la validación."""
    with pytest.raises(Exception):
        metadata._parsear('{"assumed_team_size": "muchos"}')


# --- Fusión con la metadata existente ----------------------------------------


def test_un_turno_aporta_hechos_nuevos(generador) -> None:
    generador(json.dumps({"project_name": "Portal de reservas", "assumed_team_size": 4}))

    resultado = metadata.extract_and_merge(
        transcript="Se llamará Portal de reservas, con 4 personas.",
        previous_metadata=ProjectMetadata(),
    )

    assert resultado.project_name == "Portal de reservas"
    assert resultado.assumed_team_size == 4


def test_un_dato_confirmado_antes_no_se_pierde_si_el_turno_no_lo_repite(
    generador,
) -> None:
    generador(json.dumps({"agreed_scope": "Solo disponibilidad"}))
    anterior = ProjectMetadata(project_name="Portal de reservas", assumed_team_size=4)

    resultado = metadata.extract_and_merge(
        transcript="Ahora con Redis.", previous_metadata=anterior
    )

    assert resultado.project_name == "Portal de reservas"
    assert resultado.assumed_team_size == 4
    assert resultado.agreed_scope == "Solo disponibilidad"


def test_un_dato_corregido_reemplaza_al_anterior(generador) -> None:
    generador(json.dumps({"assumed_team_size": 6}))
    anterior = ProjectMetadata(assumed_team_size=4)

    resultado = metadata.extract_and_merge(
        transcript="Mejor con 6 personas.", previous_metadata=anterior
    )

    assert resultado.assumed_team_size == 6


def test_las_tecnologias_se_acumulan_entre_turnos(generador) -> None:
    generador(json.dumps({"mentioned_technologies": ["Redis"]}))

    resultado = metadata.extract_and_merge(
        transcript="Redis también.",
        previous_metadata=ProjectMetadata(mentioned_technologies=["React"]),
    )

    assert resultado.mentioned_technologies == ["React", "Redis"]


# --- Degradación graciosa ----------------------------------------------------


def test_un_proveedor_que_falla_no_impide_la_metadata_anterior(generador) -> None:
    generador(llm_service.LLMServiceError("503 del proveedor"))
    anterior = ProjectMetadata(project_name="Portal")

    resultado = metadata.extract_and_merge(
        transcript="Algo nuevo.", previous_metadata=anterior
    )

    assert resultado.project_name == "Portal"


def test_una_respuesta_que_no_es_json_conserva_la_metadata_anterior(generador) -> None:
    generador("Perdona, no he podido entender la petición.")
    anterior = ProjectMetadata(project_name="Portal")

    resultado = metadata.extract_and_merge(
        transcript="Algo nuevo.", previous_metadata=anterior
    )

    assert resultado.project_name == "Portal"


def test_un_json_con_tipos_invalidos_conserva_la_metadata_anterior(generador) -> None:
    generador('{"assumed_team_size": "cuatro"}')
    anterior = ProjectMetadata(project_name="Portal")

    resultado = metadata.extract_and_merge(
        transcript="Con cuatro personas.", previous_metadata=anterior
    )

    assert resultado.project_name == "Portal"
    assert resultado.assumed_team_size is None


def test_una_respuesta_enormemente_larga_se_rechaza(generador) -> None:
    generador('{"agreed_scope": "' + "a" * 10_000 + '"}')
    anterior = ProjectMetadata(project_name="Portal")

    resultado = metadata.extract_and_merge(
        transcript="Algo enorme.", previous_metadata=anterior
    )

    assert resultado.project_name == "Portal"


def test_el_extractor_recibe_la_conversacion_anterior(generador) -> None:
    falso = generador(json.dumps({"project_name": "Portal"}))

    metadata.extract_and_merge(
        transcript="Redis.",
        previous_metadata=ProjectMetadata(),
        conversation="Turno 1: se llamó Portal.",
    )

    assert "Turno 1: se llamó Portal." in falso.llamadas[0]["messages"][0]["content"]


def test_el_extractor_pide_una_cota_menor_que_una_estimacion(generador) -> None:
    falso = generador(json.dumps({"project_name": "Portal"}))

    metadata.extract_and_merge(transcript="x", previous_metadata=ProjectMetadata())

    assert falso.llamadas[0]["max_output_tokens"] == 800