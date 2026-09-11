"""Contexto estático inyectado en el prompt (el "conocimiento" del sistema).

Este módulo es el núcleo de la arquitectura CAG: en lugar de recuperar
ejemplos de una base de datos, viajan enteros en cada llamada al modelo.
Cabe hacerlo porque son pocos y pequeños.

Contiene solo datos: no importa configuración, servicios ni FastAPI.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EstimationExample:
    """Una estimación histórica usada como referencia para el modelo.

    Se tipa en lugar de usar un diccionario para que el formato quede
    documentado y un error al escribir un campo se detecte al importar.
    """

    meeting_summary: str
    """Qué pedía el cliente en la reunión original."""

    estimation: str
    """La estimación que se entregó, en markdown."""


# Dos ejemplos de tipologías distintas a propósito: un proyecto completo desde
# cero y una integración acotada sobre un sistema existente. Si ambos fueran
# del mismo tipo, el modelo aprendería ese tipo de proyecto en lugar del
# formato de la estimación.
ESTIMATION_EXAMPLES: list[EstimationExample] = [
    EstimationExample(
        meeting_summary=(
            "El cliente, una distribuidora de material eléctrico con tres almacenes, "
            "necesita una plataforma web de gestión de inventario para sustituir sus "
            "hojas de cálculo. Pide alta y baja de productos, control de stock por "
            "almacén, usuarios con permisos distintos para almacén y oficina, y un "
            "panel con métricas de rotación. No tienen diseño previo ni equipo técnico "
            "interno. Mencionaron que necesitan importar el catálogo actual desde Excel."
        ),
        estimation="""## Estimación: Plataforma de Gestión de Inventario

### Desglose de tareas

1. Diseño UI/UX (wireframes y diseño visual): 40 h
2. Backend API (CRUD de productos y stock por almacén): 60 h
3. Autenticación y roles (almacén / oficina): 20 h
4. Importación del catálogo desde Excel: 16 h
5. Dashboard con métricas de rotación: 30 h
6. Testing y QA: 25 h
7. Despliegue y puesta en producción: 12 h

**Total estimado: 203 horas**
**Equipo recomendado: 2 desarrolladores full-stack + 1 diseñador UX (media jornada)**
**Duración estimada: 7-9 semanas**

### Supuestos

- El catálogo a importar viene en un único formato de Excel consistente.
- No se integra con el ERP actual en esta fase.

### Riesgos

- La calidad de los datos del Excel puede alargar la tarea de importación.
- Los permisos por almacén pueden crecer en complejidad si aparecen más perfiles.
""",
    ),
    EstimationExample(
        meeting_summary=(
            "El cliente ya tiene una tienda online en Shopify funcionando. Quiere "
            "sincronizar automáticamente los pedidos con su sistema de facturación "
            "(Holded) para dejar de introducirlos a mano. Volumen aproximado de 200 "
            "pedidos al mes. Pidió también un aviso por email cuando una sincronización "
            "falle. El plazo que manejan es de un mes."
        ),
        estimation="""## Estimación: Integración Shopify - Holded

### Desglose de tareas

1. Análisis de las APIs de Shopify y Holded y mapeo de campos: 12 h
2. Servicio de sincronización de pedidos: 32 h
3. Gestión de errores y reintentos: 14 h
4. Notificación por email ante fallo de sincronización: 8 h
5. Testing con pedidos reales en entorno de pruebas: 16 h
6. Despliegue y monitorización básica: 10 h

**Total estimado: 92 horas**
**Equipo recomendado: 1 desarrollador backend**
**Duración estimada: 3-4 semanas**

### Supuestos

- El cliente dispone de credenciales de API en ambos sistemas.
- Los pedidos siguen una estructura homogénea (sin casos especiales de facturación).

### Riesgos

- Los límites de peticiones de la API de Holded pueden obligar a encolar la sincronización.
- Las devoluciones y abonos no están incluidos; si entran en alcance, suman unas 20 h.
""",
    ),
]
