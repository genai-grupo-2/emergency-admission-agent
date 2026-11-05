# Análisis del RAG para el grupo — Pía, ítem 4

## Qué se midió

60 consultas de desarrollo de `rag/consultas_dev.jsonl`, con las normas
originales completas (incluidos distractores), BM25 k1=1.5 y b=0.75.
Las cifras salen de `resumen.json`; las tablas se regeneran en `INFORME.md`.
No se usó el test secreto ni un modelo. No hay resultados del agente todavía.

## Comparación y decisión provisional

La configuración actual (secciones, k=2) obtiene recall 0,817, precisión 0,467,
617 tokens estimados por consulta y 48/60 consultas con toda la evidencia.
Queda por debajo de la referencia publicada de cátedra: 0,875, 0,492,
580 tokens y 51/60. Ser ambos BM25 no garantiza resultados idénticos: no
disponemos de la implementación exacta de su buscador para atribuir la diferencia.

Secciones con k=4 logra 57/60 y recall 0,950, pero requiere 1.269 tokens
estimados por consulta y su precisión baja a 0,271. Es un candidato para
comparar con el agente, no una mejora gratuita.

Párrafos con k=4 reduce el contexto a 383 tokens, pero solo completa 45/60
consultas (recall 0,783). Con presupuestos de 256 y 512 tokens, los párrafos
recuperan más evidencia que las secciones: recall 0,708 frente a 0,600 y
0,767 frente a 0,692. Hay que distinguir este modo con recorte del top-k
que ve el agente: el entorno no aplica esos presupuestos automáticamente.

**Mantener provisionalmente secciones/k=2 para la integración existente.**
Comparar luego secciones/k=4 y párrafos/k=4 con el agente, midiendo casos
resueltos por los nueve controles, contexto, tiempo y costo. La calidad final
del agente decidirá la configuración; esta evaluación aislada no la demuestra.

## Variantes y límites

No se reportan métricas formales para b/c con estas esperadas: hay evidencia
numérica literal específica de original. Por ejemplo, d033 pide `P-ADM-2 = 67 años`,
que cambia en las otras variantes. `manifiesto.json` lista los IDs incompatibles.
Las pruebas del ítem 3 verifican carga de b/c y valores de una carpeta temporal.
La evaluación del agente con original/b/c sigue pendiente.

Las estimaciones de tokens siguen la regla del kit de cuatro caracteres por
token; no son mediciones del tokenizador ni de VRAM. Los resultados son de
desarrollo y las decisiones tomadas sobre ellos no prueban generalización.

## Cómo auditar

Ejecutar los comandos de `buscador/README.md`. Cada registro de
`recuperaciones.jsonl` identifica consulta, evidencia y ranking con texto íntegro.
Para cada top-k tomar los primeros k; para presupuestos aplicar el recorte
oficial. `oficial-seccion-k2.json` deja la salida del comando oficial.
`manifiesto.json` identifica entradas y código por SHA256; `commit_base`
es el commit previo a guardar este trabajo y no sustituye esos hashes.

Próximo responsable de integración: Juan. El constructor sigue siendo
`BuscadorBM25(ruta_normas, k_entorno=2)` y no requiere torch/transformers.
