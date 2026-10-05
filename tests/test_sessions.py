"""Pruebas del estado de sesión: fusión de metadata y ventana deslizante."""

from __future__ import annotations

import pytest

from app.schemas.session import ProjectMetadata
from app.services.sessions import (
    ConversationHistory,
    Session,
    SessionNotFoundError,
    SessionStore,
)


# --- Fusión de metadata ------------------------------------------------------


def test_una_metadata_sin_hechos_esta_vacia() -> None:
    assert ProjectMetadata().is_empty()


def test_un_solo_hecho_hace_que_no_este_vacia() -> None:
    assert not ProjectMetadata(project_name="Portal de reservas").is_empty()


def test_un_escalar_nuevo_corrige_el_anterior() -> None:
    anterior = ProjectMetadata(project_name="Portal de reservas")

    combinada = anterior.merge_with(ProjectMetadata(project_name="Portal de reservas v2"))

    assert combinada.project_name == "Portal de reservas v2"


def test_un_escalar_ausente_preserva_el_valor_anterior() -> None:
    """`None` significa "no se ha dicho nada nuevo", no "olvídalo"."""
    anterior = ProjectMetadata(assumed_team_size=4)

    combinada = anterior.merge_with(ProjectMetadata(project_name="Portal"))

    assert combinada.assumed_team_size == 4


def test_las_tecnologias_se_acumulan_sin_duplicar() -> None:
    anterior = ProjectMetadata(mentioned_technologies=["React", "Postgres"])

    combinada = anterior.merge_with(ProjectMetadata(mentioned_technologies=["postgres", "Redis"]))

    assert combinada.mentioned_technologies == ["React", "Postgres", "Redis"]


def test_fusionar_no_altera_la_metadata_original() -> None:
    anterior = ProjectMetadata(mentioned_technologies=["React"])

    anterior.merge_with(ProjectMetadata(mentioned_technologies=["Redis"]))

    assert anterior.mentioned_technologies == ["React"]


# --- Ventana deslizante ------------------------------------------------------


def test_el_historial_arranca_vacio() -> None:
    historial = ConversationHistory(max_turns=6)

    assert historial.to_messages() == []
    assert historial.turn_count == 0


def test_un_turno_aporta_dos_mensajes() -> None:
    historial = ConversationHistory(max_turns=6)

    historial.append(user="transcripción", assistant="estimación")

    mensajes = historial.to_messages()
    assert [m["role"] for m in mensajes] == ["user", "assistant"]
    assert historial.turn_count == 1


def test_la_ventana_descarta_los_pares_mas_antiguos() -> None:
    historial = ConversationHistory(max_turns=2)

    for indice in range(4):
        historial.append(user=f"pregunta {indice}", assistant=f"respuesta {indice}")
        historial.trim()

    contenidos = [m["content"] for m in historial.to_messages()]
    assert contenidos == ["pregunta 2", "respuesta 2", "pregunta 3", "respuesta 3"]


def test_la_ventana_nunca_supera_el_limite() -> None:
    historial = ConversationHistory(max_turns=3)

    for indice in range(20):
        historial.append(user=f"pregunta {indice}", assistant=f"respuesta {indice}")
        historial.trim()

    assert historial.turn_count == 3
    assert len(historial.to_messages()) == 6


def test_el_recorte_conserva_la_alternancia_de_roles() -> None:
    """Un historial que empiece por `assistant` rompe lo que asumen los SDK."""
    historial = ConversationHistory(max_turns=2)

    for indice in range(5):
        historial.append(user=f"pregunta {indice}", assistant=f"respuesta {indice}")
        historial.trim()

    roles = [m["role"] for m in historial.to_messages()]
    assert roles == ["user", "assistant", "user", "assistant"]


def test_el_historial_no_guarda_el_system_prompt() -> None:
    """El system prompt se antepone en cada llamada, no vive en el historial."""
    historial = ConversationHistory(max_turns=6)
    historial.append(user="pregunta", assistant="respuesta")

    assert all(m["role"] != "system" for m in historial.to_messages())


# --- Sesión y store ----------------------------------------------------------


def test_crear_una_sesion_devuelve_identificadores_distintos() -> None:
    store = SessionStore(max_turns=6)

    primera = store.create()
    segunda = store.create()

    assert primera.session_id != segunda.session_id


def test_una_sesion_nueva_no_tiene_historial_ni_metadata() -> None:
    session = Session(max_turns=6)

    assert session.history.to_messages() == []
    assert session.metadata.is_empty()


def test_registrar_un_turno_devuelve_cuantos_quedan() -> None:
    session = Session(max_turns=2)

    assert session.record_turn(user="a", assistant="b") == 1
    assert session.record_turn(user="c", assistant="d") == 2
    assert session.record_turn(user="e", assistant="f") == 2


def test_una_sesion_inexistente_no_se_recrea_silenciosamente() -> None:
    store = SessionStore(max_turns=6)

    with pytest.raises(SessionNotFoundError):
        store.get_or_404("no-existe")


def test_el_store_usa_el_limite_que_se_le_pasa() -> None:
    store = SessionStore(max_turns=2)

    session = store.create()
    session.record_turn(user="a", assistant="b")
    session.record_turn(user="c", assistant="d")
    session.record_turn(user="e", assistant="f")

    assert session.history.turn_count == 2
    assert store.max_turns == 2