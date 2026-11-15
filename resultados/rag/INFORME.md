# Evaluación de desarrollo del RAG

Generado con `uv run --locked python -m buscador.evaluar --salida resultados/rag`.

## Resultados con normas originales

| Fragmentación | k | Recall | Precisión | Tokens/consulta | Consultas completas |
|---|---:|---:|---:|---:|---:|
| Referencia de cátedra (mission.md) | 2 | 0.875 | 0.492 | 580 | 51/60 |
| seccion | 1 | 0.65 | 0.717 | 298 | 35/60 |
| seccion | 2 | 0.817 | 0.467 | 617 | 48/60 |
| seccion | 3 | 0.833 | 0.317 | 931 | 49/60 |
| seccion | 4 | 0.95 | 0.271 | 1269 | 57/60 |
| parrafo | 1 | 0.483 | 0.517 | 94 | 27/60 |
| parrafo | 2 | 0.675 | 0.425 | 196 | 39/60 |
| parrafo | 3 | 0.758 | 0.356 | 292 | 43/60 |
| parrafo | 4 | 0.783 | 0.3 | 383 | 45/60 |

## Presupuestos fijos con normas originales

Los presupuestos usan hasta 20 resultados y recorte por caracteres del kit; no dependen de k_entorno.

| Fragmentación | Presupuesto | Recall | Precisión | Tokens/consulta | Consultas completas |
|---|---:|---:|---:|---:|---:|
| seccion | 256 | 0.6 | 0.458 | 255 | 33/60 |
| seccion | 512 | 0.692 | 0.346 | 510 | 39/60 |
| seccion | 1024 | 0.85 | 0.252 | 1020 | 50/60 |
| parrafo | 256 | 0.708 | 0.288 | 255 | 41/60 |
| parrafo | 512 | 0.767 | 0.207 | 509 | 44/60 |
| parrafo | 1024 | 0.883 | 0.133 | 1019 | 53/60 |

## Alcance y auditoría

Todas las métricas y desgloses por tipo de las variantes aplicables están en resumen.json.
Las variantes excluidas por evidencia literal incompatible se registran en manifiesto.json; no se cambian sus respuestas esperadas.
recuperaciones.jsonl conserva el ranking completo usado (hasta 20 fragmentos), su texto y la evidencia cubierta.
Para k_entorno se toman los primeros k; los presupuestos recortan el ranking como hace el evaluador oficial.
manifiesto.json registra los hashes de entradas y código. La selección se hace sobre desarrollo, no sobre test secreto.
Los tokens son una estimación por caracteres, no los del tokenizador de un modelo.
Estos resultados no miden casos resueltos por el agente, latencia GPU ni costo de inferencia.
