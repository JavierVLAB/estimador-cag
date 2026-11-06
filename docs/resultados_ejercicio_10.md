# Ejercicio 10 — Resultados: búsqueda híbrida y reranking

Medición del 2026-11-06 en local (Docker sobre Mac, CPU). Salida cruda: `odd/s10/measure_retrieval_run1.md`.

## Montaje

- **Corpus:** 15 presupuestos y 52 chunks, uno por componente, en inglés.
- **Golden set:** `evals/retrieval/golden_set.json`, con 5 consultas en inglés anotadas a mano antes de medir. Un presupuesto es relevante si un estimador lo usaría como referencia para al menos un entregable principal del proyecto.
- **Métricas:** precision@5 a nivel de chunk. Cada chunk cuenta como acierto si su presupuesto es relevante, de modo que dos chunks del mismo presupuesto cuentan dos veces. Recall@5 a nivel de presupuesto.
- **Latencia:** mediana de 3 ejecuciones por consulta, medida dentro del proceso. No incluye el embedding de la consulta, que es igual en las cuatro configuraciones y tarda 244 ms de mediana.
- **Parámetros:** recall de 50 candidatos antes del reranking, RRF con `k = 60` y reranker `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`.
- **Rama léxica:** `tsvector` con configuración `'english'` y consulta OR de lexemas.

## Tabla comparativa

| Config. | Búsqueda | Reranking | precision@5 | recall@5 | Latencia mediana | Latencia máx. |
|---|---|---|---|---|---|---|
| A | Vectorial | No | 0,88 | 0,73 | 2,3 ms | 21,5 ms |
| B | Híbrida | No | **0,92** | **0,83** | 4,2 ms | 8,2 ms |
| C | Vectorial | Sí | 0,84 | 0,67 | 1.646,6 ms | 1.787,8 ms |
| D | Híbrida | Sí | 0,84 | 0,67 | 1.524,3 ms | 1.767,2 ms |

## Detalle por consulta (precision@5)

| Consulta | A | B | C | D |
|---|---|---|---|---|
| q1 Tienda gourmet | 1,00 | 1,00 | 1,00 | 1,00 |
| q2 Telemedicina HL7 FHIR | 0,80 | 1,00 | 1,00 | 1,00 |
| q3 Créditos a pymes (paráfrasis) | 0,80 | 0,80 | 0,80 | 0,80 |
| q4 Mantenimiento predictivo | 0,80 | 0,80 | 0,80 | 0,80 |
| q5 Logística de reparto | 1,00 | 1,00 | 0,60 | 0,60 |

## Qué explica los números

- **La híbrida gana en la consulta con más términos exactos.** En q2 (HL7, FHIR, EHR), la fusión mete el presupuesto 010 en el top 5 en lugar de 012, y la precisión pasa de 0,80 a 1,00. Cuesta unos 2 ms.
- **El reranker no aporta precisión y hunde q5.** Al puntuar los 52 chunks con la consulta de logística, solo los tres componentes de 007 reciben una puntuación aceptable (entre −0,9 y −3,0). Del cuarto en adelante, todos puntúan por debajo de −7,8, y los componentes de pagos de 003 quedan por delante de la gestión de almacén de 014. El modelo está entrenado con MS MARCO, que son preguntas cortas frente a pasajes. Con una descripción que mezcla tres necesidades distintas, solo reconoce una, y el resto del orden es ruido.
- **C y D son idénticas.** Con 52 chunks, recuperar 50 candidatos es recuperar casi todo el corpus, así que el reranker reordena el mismo conjunto venga de la rama vectorial o de la híbrida.
- **El reranking cuesta unos 1,5 s por consulta** en CPU dentro de Docker: 50 pares por consulta. Es seis veces más que lo que cita la lección (255 ms), probablemente por la CPU virtualizada.
- **La muestra es pequeña.** Cada consulta pesa 0,20 de precisión en la media, así que una diferencia de 0,04 es un solo chunk. Las tendencias sirven para decidir aquí, pero no para generalizar.

## Conclusiones

Usaría la configuración B, búsqueda híbrida sin reranking. Es la única que mejora la precisión y la exhaustividad frente a la vectorial pura (0,92 frente a 0,88 de precision@5, y 0,83 frente a 0,73 de recall@5) y apenas añade 2 ms, despreciables frente a los 244 ms del embedding de la consulta y los segundos que tarda la generación. En este caso el reranking no justifica su latencia. El problema no es tanto el coste, porque 1,5 s serían asumibles dentro de una estimación que tarda varios segundos, como que no hay ganancia: la precisión baja de 0,88 a 0,84. Este cross-encoder, entrenado con preguntas cortas, no sabe puntuar descripciones de proyecto con varias necesidades, y con 52 chunks el recall amplio no tiene nada que rescatar. Volvería a evaluarlo si el corpus crece hasta miles de chunks, o si la consulta se descompone en necesidades individuales antes de reranquear.
