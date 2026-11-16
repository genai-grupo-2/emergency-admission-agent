# Informe · Agente de admisión de guardia (grupo 2)

Un apartado por parte de la misión ([mission.md](mission.md)). Cada integrante redacta su parte y Juan la integra acá.
**Las tablas no se escriben a mano**: las genera `python -m evaluacion.tablas` desde `corridas/`, y lo que todavía no se
corrió figura como «pendiente de correr» o «bloqueado». Cada número dice de qué corrida sale, y `condicion.json` de esa
corrida tiene el comando, el commit, el checkpoint y el prompt.

Estado al 5/11/2026: el agente, la optimización de prompt y la evaluación están implementados y probados sin GPU con
un modelo falso. **Todavía no hay ninguna corrida con el modelo real**, así que este informe no trae resultados.

## Parte 1 · Curado del historial

*A cargo de Cande (#1).* Su borrador está en `datos/INFORME_DATOS.md`, en la rama `cande/datos-historial`. Se integra
acá cuando esa rama entre a `main`.

## Parte 2 · Buscador (RAG)

*A cargo de Pía (#2).* Incluye `admision.evaluar_rag` al lado de la referencia BM25 de la cátedra (recall 0,875,
precisión 0,492, 580 tokens por consulta y 51 de 60 consultas completas).

Mientras tanto, `entrega.py` usa un BM25 provisorio con una sección por fragmento (`buscador/bm25.py`), sólo para que el
agente funcione. Con `python -m admision.evaluar_rag --entrega entrega.py --normas normas/original --consultas
rag/consultas_dev.jsonl` da recall 0,817, precisión 0,467, 617 tokens por consulta y 48 de 60 consultas completas
(commit `b2eb6c1`). No es el buscador del grupo: lo reemplaza el de Pía.

## Parte 3 · Optimización del prompt, antes de entrenar

*A cargo de Juan (#3).*

**Qué se optimiza.** El mensaje de sistema. El resto del formato queda fijo: el primer mensaje, las llamadas en JSON y
los resultados como `Resultado de <herramienta>:`. Es el mismo formato que usa Cande para las conversaciones de
entrenamiento, y así entrenamiento y evaluación ven la misma forma.

**Agente** (`agente/ciclo.py`):
- Usa el protocolo del ejemplo de la cátedra.
- Antes de gastar una llamada del caso, valida el nombre de la herramienta y que los argumentos sean un objeto.
- Cuando quedan 5 llamadas lo avisa, y con una sola acepta únicamente `registrar_decision`.
- Si el modelo o el entorno fallan en un caso, se cierra ese caso y el lote sigue.
- Lo cubren 15 pruebas con el entorno real del kit y un modelo guionado: `tests/test_agente_ciclo.py`.

**Estrategia** (`optimizacion/`):
- **Búsqueda local por bloques.** El prompt se arma con bloques: identidad, procedimiento, herramientas, formato, normas
  y costumbres. Cada bloque tiene variantes o se omite. La semilla `catedra` reproduce byte por byte el prompt del
  ejemplo, que es la línea de base.
- **Cómo avanza.** Desde la mejor semilla se prueban todos los candidatos que cambian un solo bloque, y la búsqueda se
  mueve mientras mejore el puntaje.
- **Puntaje.** `resueltos / episodios − λ · tokens / 1000`, con λ = 0,05 fijado antes de correr. Desempata la media de
  controles y después el largo.
- **Partición** (`optimizacion/particion.json`, semilla 42). Se parte por caso, y las tres normas de cada caso quedan del
  mismo lado. El optimizador usa 30 casos (90 episodios). Los otros 20 casos son la validación: el optimizador nunca los
  ve y se usan una sola vez, para la comparación antes/después. El test de la cátedra no se usa.
- **Decodificación greedy.** Cada candidato queda en `corridas/prompt/<nombre>/candidatos.jsonl`, también los que
  fallaron, con el prompt, las trazas completas, el commit, el hash de `uv.lock` y la partición.
- **Por qué no DSPy/GEPA.** El agente es un protocolo JSON de varios turnos con herramientas, que no encaja en un
  `dspy.Module` sin reescribirlo. Además, GEPA necesita un modelo que reflexione sobre los errores: el Gemma sin
  entrenar propone malas mutaciones, y un modelo externo choca con la regla de no usar servicios externos.

**Bloques sin números.** Ningún bloque trae números de las normas, porque en el test cambian. La única cifra es el
umbral de 75 años de la costumbre del voluntariado, que no figura en ninguna norma y que Cande infirió del historial
(`costumbres.md`, #1).

Largo de los prompts de partida:

<!-- tabla:semillas -->
| Semilla | Caracteres | Tokens (aprox., 4 caracteres por token) |
| --- | --- | --- |
| catedra | 2232 | 558 |
| catedra+costumbres | 2456 | 614 |
| compacto | 1903 | 476 |
<!-- /tabla:semillas -->

Antes y después, con el modelo sin entrenar, en los 20 casos de validación:

<!-- tabla:prompt -->
| Prompt | Resueltos (original) | Resueltos (b) | Resueltos (c) | Tokens del prompt (aprox.) | Contexto por caso (tokens aprox.) | Corrida |
| --- | --- | --- | --- | --- | --- | --- |
| Antes (cátedra) | pendiente de correr | pendiente de correr | pendiente de correr | pendiente de correr | pendiente de correr | pendiente de correr |
| Después (optimizado) | pendiente de correr | pendiente de correr | pendiente de correr | pendiente de correr | pendiente de correr | pendiente de correr |
<!-- /tabla:prompt -->

Pasos para completar esta parte (en Modal, ver README):
1. `modal run modal_app.py --comando "optimizacion.optimizar --nombre busqueda-01"`
2. `python -m optimizacion.congelar --corrida busqueda-01`
3. Las dos corridas de `evaluacion.evaluar` de la validación. Los comandos están en `optimizacion/comparar.py`.
4. `python -m evaluacion.tablas`
5. Entregar `prompts/optimizado.txt` a Cande para que regenere las conversaciones
   (`python -m datos.preparar --prompt prompts/optimizado.txt`) y a Juli para que entrene.

## Parte 4 · Entrenamiento

*Estrategia, corridas y checkpoints: a cargo de Juli (#4). Matriz comparativa: Juan (#3).*

Los 50 casos de práctica, resueltos por los 9 controles:

<!-- tabla:matriz -->
| Condición | Normas original | Normas b | Normas c | Corrida |
| --- | --- | --- | --- | --- |
| base | pendiente de correr | pendiente de correr | pendiente de correr | — |
| solo prompt | bloqueado: falta congelar el prompt 'optimizado' | bloqueado: falta congelar el prompt 'optimizado' | bloqueado: falta congelar el prompt 'optimizado' | — |
| solo entrenamiento | bloqueado: falta el checkpoint de Juli (#4) | bloqueado: falta el checkpoint de Juli (#4) | bloqueado: falta el checkpoint de Juli (#4) | — |
| ambos | bloqueado: falta el checkpoint de Juli (#4) | bloqueado: falta el checkpoint de Juli (#4) | bloqueado: falta el checkpoint de Juli (#4) | — |
| Referencia de la cátedra, sin entrenar | 12/50 | 15/50 | 12/50 | mission.md |
| Referencia de la cátedra, fine-tuning supervisado | 25/50 | 24/50 | 25/50 | mission.md |
<!-- /tabla:matriz -->

Acierto por control:

<!-- tabla:controles -->
Pendiente de correr: no hay corridas de la matriz todavía.
<!-- /tabla:controles -->

Regresiones frente a la base:

<!-- tabla:regresiones -->
Pendiente de correr: hacen falta la base y al menos otra condición.
<!-- /tabla:regresiones -->

## Parte 5 · Recursos y producción

*A cargo de Pía (#2).* VRAM, tiempo y costo por caso en la A100 de 40 GB, paralelismo, casos simultáneos en producción,
proyección de consumo, escalado y trabajos futuros.

## Trazabilidad de las corridas

<!-- tabla:trazabilidad -->
Todavía no hay corridas de evaluación en `corridas/eval/`.
<!-- /tabla:trazabilidad -->

## Experimentos que no funcionaron

Se documentan todos, no sólo el final. Por ahora no hay ninguno con el modelo real.
