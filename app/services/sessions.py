"""Estado de sesión en memoria del proceso.

El store es un diccionario. No hay base de datos ni Redis, y esa volatilidad es
deliberada para esta fase: perder la conversación al reiniciar no rompe el
ejercicio, y persistizarla traería acoplamiento por lo que el enunciado no pide.
Lo que sí tiene consecuencias operativas, y conviene no olvidar, es que con
varios workers cada uno tiene su propio diccionario: dos peticiones que caigan
en workers distintos pueden no ver la misma sesión.

`llm_service` no importa nada de aquí. Este módulo no conoce al proveedor ni a
FastAPI.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from uuid import uuid4

from app.config import settings
from app.schemas.session import ProjectMetadata


class SessionNotFoundError(KeyError):
    """El `session_id` no está en el diccionario de sesiones."""


class ConversationHistory:
    """Historial de la conversación con ventana deslizante.

    Solo guarda pares usuario/asistente. El system prompt NO es un mensaje del
    historial: se re-renderiza en cada turno a partir del `project_metadata`
    vigente, así que guardarlo aquí obligaría a reescribirlo cada vez que la
    metadata cambiara y convertiría la "invariante" en una mentira.

    `append` no recorta por sí mismo y el recorte es un método aparte. Así hay
    un único sitio donde se decide qué se olvida, que es justo donde después
    encajarán el resumen acumulado y las anclas de la sesión en directo.
    """

    def __init__(self, max_turns: int) -> None:
        self.max_turns = max_turns
        self.messages: list[dict[str, str]] = []

    def append(self, *, user: str, assistant: str) -> None:
        """Añade un turno completo."""
        self.messages.append({"role": "user", "content": user})
        self.messages.append({"role": "assistant", "content": assistant})

    def trim(self) -> None:
        """Descarta los pares más antiguos al superar el límite.

        El sobrante se ajusta a par porque un historial que empiece por un
        mensaje de asistente rompe la alternancia de roles que asumen los
        proveedores.
        """
        maximo = self.max_turns * 2
        sobrante = len(self.messages) - maximo
        if sobrante <= 0:
            return
        if sobrante % 2 != 0:
            sobrante += 1
        del self.messages[:sobrante]

    def to_messages(self) -> list[dict[str, str]]:
        """Mensajes listos para el proveedor, sin el system prompt.

        El system prompt lo antepone quien llama, ya que depende del estado
        actual de la sesión y por eso no puede ser una entrada fija.
        """
        return list(self.messages)

    @property
    def turn_count(self) -> int:
        return len(self.messages) // 2


class Session:
    """Una sesión conversacional.

    `history` y `metadata` son cosas distintas a propósito: el historial es lo
    que se dijo, la metadata es lo que se sabe del proyecto. Solo la segunda
    sobrevive a los turnos que la ventana deslizante descarta, y es la que se
    inyecta en el prompt.
    """

    def __init__(self, max_turns: int) -> None:
        self.session_id: str = str(uuid4())
        self.history = ConversationHistory(max_turns)
        self.metadata = ProjectMetadata()
        self.created_at = datetime.now(timezone.utc)

    def record_turn(self, *, user: str, assistant: str) -> int:
        """Añade el turno ya generado y devuelve cuántos turnos quedan."""
        self.history.append(user=user, assistant=assistant)
        self.history.trim()
        return self.history.turn_count


class SessionStore:
    """Diccionario de sesiones con un lock.

    Los handlers son `def`, así que Starlette los ejecuta en el threadpool y dos
    peticiones pueden buscar sesiones a la vez. El lock protege el diccionario:
    sin él, un `create` y un `get` simultáneos sobre el mismo dict pierden
    consistencia en CPython.

    Lo que el lock NO protege es la mutación de una sesión ya resuelta. El
    `append` y el recorte de `record_turn` ocurren en el router, fuera de aquí.
    Hoy eso no rompe nada porque son dos operaciones sobre una lista y el GIL no
    las entrelaza, pero es una propriété accidental, no una garantía: si el
    historial llegara a crecer un resumen acumulado, o el recorte se volviera
    más complejo, haría falta un lock por sesión y no uno global.
    """

    def __init__(self, max_turns: int | None = None) -> None:
        self._max_turns = max_turns if max_turns is not None else settings.session_max_turns
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    @property
    def max_turns(self) -> int:
        return self._max_turns

    def create(self) -> Session:
        with self._lock:
            session = Session(max_turns=self._max_turns)
            self._sessions[session.session_id] = session
            return session

    def get_or_404(self, session_id: str) -> Session:
        """Devuelve la sesión o lanza `SessionNotFoundError`.

        No la recrea. Dejar que el endpoint de estimación fabricara una sesión
        ante un id desconocido dejaría a la interfaz conversando con un
        historial que el backend nunca vio, que es peor que un error claro.
        """
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session

    def clear(self) -> None:
        """Vacía el store. Existe para los tests."""
        with self._lock:
            self._sessions.clear()