"""Extracción y actualización del `project_metadata` de una sesión.

Es una segunda llamada al proveedor, y eso tiene un coste: duplica la latencia
por turno. La alternativa barata, un regex sobre la respuesta, obligaría a
encajar un bloque de campos dentro de la estimación que el usuario lee, y esa
estimación es justamente lo que este servicio tiene que entregar limpio. Aquí
el bloque de datos va aparte.

La degradación es explícita: si el extractor falla o devuelve algo que no es
JSON interpretable, la estimación se entrega igual con la metadata anterior.
Perder un campo de contexto no justifica perder la respuesta que el usuario
pidió.
"""

from __future__ import annotations

import json
import logging
import re

from pydantic import ValidationError

from app.prompts.loader import render_metadata_extraction_prompt
from app.schemas.session import ProjectMetadata
from app.services import llm_service

logger = logging.getLogger(__name__)

# Tope generoso: la metadata consolidada son cuatro campos, y un modelo puede
# envolver el JSON en texto o en un bloque de código sin que valga la pena
# buscar más caracteres.
_MAX_JSON_CHARS = 4_000

_CAMPOS = ("project_name", "assumed_team_size", "mentioned_technologies", "agreed_scope")


def _quitar_valla(texto: str) -> str:
    """Saca el JSON de un bloque cercado o de un texto con explicaciones."""
    cercado = re.search(r"```(?:json)?\s*(.+?)\s*```", texto, re.DOTALL)
    if cercado:
        return cercado.group(1)
    # Un modelo puede devolver el objeto incrustado entre frases.
    objeto = re.search(r"\{.*\}", texto, re.DOTALL)
    return objeto.group(0) if objeto else texto.strip()


def _parsear(texto: str) -> ProjectMetadata:
    """Interpreta la respuesta del extractor como `ProjectMetadata`.

    Se filtran las claves desconocidas antes de validar: el modelo puede
    devolver campos extra y `ProjectMetadata` no los tiene, así que sin el
    filtro cada clave inventada sería un error de validación.
    """
    datos = json.loads(texto)
    if not isinstance(datos, dict):
        raise ValueError("El extractor no devolvió un objeto JSON.")

    desconocidas = set(datos) - set(_CAMPOS)
    if desconocidas:
        logger.info("El extractor devolvió campos ignorados: %s", sorted(desconocidas))

    return ProjectMetadata.model_validate(
        {campo: datos[campo] for campo in _CAMPOS if campo in datos}
    )


def extract_and_merge(
    *,
    transcript: str,
    previous_metadata: ProjectMetadata,
    conversation: str = "",
) -> ProjectMetadata:
    """Devuelve la metadata actualizada, o la anterior si el extractor falla.

    Nunca propaga una excepción del extractor: quien llama necesita una
    metadata válida siempre, y la anterior siempre lo es.
    """
    try:
        system_prompt, contenido_usuario = render_metadata_extraction_prompt(
            transcript=transcript, conversation=conversation
        )
        completion = llm_service.generate_turn(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": contenido_usuario}],
            # El JSON de cuatro campos no necesita la cota de una estimación
            # entera; bajarla acorta la espera sin arriesgar el truncamiento.
            max_output_tokens=800,
        )
        if len(completion.text) > _MAX_JSON_CHARS:
            raise ValueError(
                f"El extractor devolvió {len(completion.text)} caracteres, "
                f"por encima del máximo de {_MAX_JSON_CHARS}."
            )
        extraida = _parsear(_quitar_valla(completion.text))
    except (llm_service.LLMServiceError, ValidationError, ValueError) as exc:
        logger.warning("No se pudo extraer el project_metadata: %s", exc)
        return previous_metadata

    actualizada = previous_metadata.merge_with(extraida)
    logger.info(
        "project_metadata actualizada: %s",
        actualizada.model_dump(exclude_defaults=True) or "sin hechos nuevos",
    )
    return actualizada