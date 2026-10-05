"""Contratos de la memoria conversacional.

`ProjectMetadata` es el conocimiento sobre el proyecto en curso; el historial
conversacional es otra cosa y vive en `app.services.sessions`. Aquí están los
tipos que cruzan la frontera HTTP, más la metadata porque el panel de la
interfaz la necesita devolver.
"""

from pydantic import BaseModel, Field

from app.schemas.estimation import TokenUsage


class ProjectMetadata(BaseModel):
    """Hechos conocidos del proyecto en curso.

    Todos los campos son opcionales porque en el primer turno el modelo aún no
    se ha comprometido con ningún hecho, y esa ausencia es un estado legítimo
    (ver `is_empty`) en lugar de un error.
    """

    project_name: str | None = Field(default=None, max_length=120)
    assumed_team_size: int | None = Field(default=None, ge=1, le=50)
    mentioned_technologies: list[str] = Field(default_factory=list)
    agreed_scope: str | None = Field(default=None, max_length=2000)

    def is_empty(self) -> bool:
        return (
            self.project_name is None
            and self.assumed_team_size is None
            and not self.mentioned_technologies
            and self.agreed_scope is None
        )

    def merge_with(self, update: "ProjectMetadata") -> "ProjectMetadata":
        """Combina la metadata extraída de un turno con la que ya había.

        Los escalares se sobrescriben cuando el turno trae un valor, y se
        preservan cuando el extractor devuelve `None`: `None` significa "no se
        ha dicho nada nuevo", no "olvida lo anterior". Las tecnologías, en
        cambio, se acumulan, porque añadir una pieza al stack no invalida las
        ya mencionadas.

        La comparación de tecnologías es sin distinguir mayúsculas para que
        `Postgres` y `postgres` no se acumulen como dos.
        """
        acumuladas = list(self.mentioned_technologies)
        vistas = {tecnologia.lower() for tecnologia in acumuladas}
        for tecnologia in update.mentioned_technologies:
            if tecnologia.lower() not in vistas:
                acumuladas.append(tecnologia)
                vistas.add(tecnologia.lower())

        return ProjectMetadata(
            project_name=update.project_name or self.project_name,
            assumed_team_size=update.assumed_team_size or self.assumed_team_size,
            mentioned_technologies=acumuladas,
            agreed_scope=update.agreed_scope or self.agreed_scope,
        )


class CreateSessionResponse(BaseModel):
    """Identificador de la sesión recién creada."""

    session_id: str = Field(description="UUID v4 de la sesión conversacional.")


class SessionEstimateResponse(BaseModel):
    """Estimación de un turno más el estado en que queda la sesión.

    Incluye la metadata y los turnos retenidos porque los necesita la interfaz
    para el panel lateral, y porque permite comprobar en los tests que la
    ventana deslizante se respeta sin instrumentar el servicio.
    """

    text: str = Field(description="Estimación generada en formato Markdown.")
    prompt_version: str = Field(description="Versión de la plantilla empleada.")
    model: str = Field(description="Modelo utilizado para generarla.")
    provider: str = Field(description="Proveedor que generó la estimación.")
    usage: TokenUsage = Field(description="Consumo de tokens de la llamada.")
    metadata: ProjectMetadata = Field(
        description="Hechos conocidos del proyecto tras este turno."
    )
    turns_kept: int = Field(
        description="Pares usuario/asistente que conserva el historial.",
        ge=0,
    )


class SessionInfoResponse(BaseModel):
    """Estado de una sesión, sin pasar por el proveedor."""

    session_id: str
    metadata: ProjectMetadata
    message_count: int = Field(ge=0)
    max_turns: int = Field(ge=1)