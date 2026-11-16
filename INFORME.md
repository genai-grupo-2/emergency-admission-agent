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
| Antes (cátedra) | 7/20 | 5/20 | 5/20 | 558 | 4539 | `prompt-antes` · prompt `f23f5921894f` · commit `7efb31e` |
| Después (optimizado) | 2/20 | 1/20 | 1/20 | 430 | 4656 | `prompt-despues` · prompt `f7e6674cd484` · commit `2d0b182` |
<!-- /tabla:prompt -->

**Dónde se corrió.** En Kaggle, con 2×T4 de 16 GB (`kaggle/correr.ipynb` y `correr_kaggle.py`), porque Modal no
habilita ninguna GPU sin una tarjeta cargada. Gemma 4 E4B en bf16 no entra en una T4, así que los pesos se reparten
entre las dos (`ADMISION_DEVICE_MAP=auto`). La T4 no tiene bf16 nativo: es más lenta que la A100 y generar en lote
puede mover algún caso. Cada corrida guarda en `corridas/entornos/` las GPU, el driver, las versiones de torch y
transformers, el commit, las variables y cuánto tardó. Esos tiempos no sirven para la Parte 5, que pide la A100.

**Cómo fue la búsqueda** (`corridas/prompt/busqueda-01/`, commit `03743a8`, lote 15):
- **Presupuesto.** Corrió 8 evaluaciones de 90 episodios, no las 24 previstas. En 2×T4 cada evaluación tardó entre 77 y
  102 minutos, la sesión de Kaggle corta a las 12 h y el optimizador no retoma una corrida cortada. Tardó 11,9 h.
- **Candidatos.** Ninguno falló. La semilla `catedra` resolvió 10/90 con 624 tokens (del tokenizador del modelo).
  La semilla `compacto` resolvió 18/90 con 521. Su mejor vecino fue el mismo prompt sin el bloque de identidad: 18/90
  con 485 tokens. Ese prompt se congeló en `prompts/optimizado.txt` (`python -m optimizacion.congelar --corrida
  busqueda-01`).
- **Frontera.** Quedaron dos puntos: sin procedimiento (9/90, 415 tokens) y el elegido (18/90, 485 tokens).

**Resultado: el prompt optimizado no generaliza.** En la validación (tabla de arriba) resolvió 4 de 60 episodios,
contra 17 de 60 del prompt de la cátedra, con el mismo protocolo. En los 50 casos (tabla de la Parte 4) también rinde
peor que la base en las tres normas. Lo que cae es el circuito tiempo-dependiente, su plazo y el box antes del
registro. Mejora la verificación de la afiliación. La ventaja de 18 contra 10 en la partición de optimización era
ruido: con 30 casos y el modelo sin entrenar, una diferencia así no alcanza para elegir.

**Decisión.** No se adopta el prompt optimizado. Juli entrena con el de la cátedra, que es el que ya usan las
conversaciones de Cande (`datos/prompts/sistema-usado.txt`, idéntico a `prompts/catedra.txt`). Elegir entre los dos
mirando la validación es usar la validación para decidir. Se hizo una sola vez, entre dos opciones ya congeladas, y
sin otra búsqueda. Una segunda búsqueda armada mirando los errores de validación sería optimizar sobre la validación.

## Parte 4 · Entrenamiento

*Estrategia, corridas y checkpoints: a cargo de Juli (#4). Matriz comparativa: Juan (#3).*

Los 50 casos de práctica, resueltos por los 9 controles. «base» y «solo prompt» no se volvieron a jugar: se armaron
con `python -m evaluacion.componer`, juntando los 30 casos de optimización que ya había jugado la búsqueda con los 20
de validación de `prompt-antes` y `prompt-despues`, y puntuando de nuevo. El mismo prompt y el mismo modelo en las dos
partes. Difieren en el lote (15 y 50) y en el commit, pero entre esos commits sólo cambiaron `corridas/` y `prompts/`.
La tabla de trazabilidad dice de dónde sale cada parte. Son corridas en Kaggle 2×T4, no en la A100 de la referencia
de la cátedra.

<!-- tabla:matriz -->
| Condición | Normas original | Normas b | Normas c | Corrida |
| --- | --- | --- | --- | --- |
| base | 10/50 | 9/50 | 8/50 | `corridas/eval/matriz-base` |
| solo prompt | 8/50 | 8/50 | 6/50 | `corridas/eval/matriz-solo-prompt` |
| solo entrenamiento | bloqueado: falta el checkpoint de Juli (#4) | bloqueado: falta el checkpoint de Juli (#4) | bloqueado: falta el checkpoint de Juli (#4) | — |
| ambos | bloqueado: falta el checkpoint de Juli (#4) | bloqueado: falta el checkpoint de Juli (#4) | bloqueado: falta el checkpoint de Juli (#4) | — |
| Referencia de la cátedra, sin entrenar | 12/50 | 15/50 | 12/50 | mission.md |
| Referencia de la cátedra, fine-tuning supervisado | 25/50 | 24/50 | 25/50 | mission.md |
<!-- /tabla:matriz -->

Acierto por control:

<!-- tabla:controles -->
| Condición | Normas | registro | numero_documento | box_antes_del_registro | circuito | plazo_circuito_min | cobertura | entidad_a_notificar | aviso_al_voluntariado | verificacion |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | original | 0.76 | 1.00 | 0.72 | 0.98 | 0.90 | 0.84 | 0.82 | 0.72 | 0.82 |
| base | b | 0.76 | 1.00 | 0.70 | 0.98 | 0.88 | 0.86 | 0.76 | 0.72 | 0.78 |
| base | c | 0.70 | 1.00 | 0.74 | 0.98 | 0.88 | 0.82 | 0.84 | 0.72 | 0.78 |
| solo prompt | original | 0.76 | 1.00 | 0.52 | 0.80 | 0.56 | 0.90 | 0.92 | 0.76 | 0.96 |
| solo prompt | b | 0.74 | 1.00 | 0.52 | 0.80 | 0.54 | 0.90 | 0.88 | 0.76 | 0.96 |
| solo prompt | c | 0.66 | 1.00 | 0.50 | 0.80 | 0.58 | 0.86 | 0.96 | 0.78 | 0.96 |
<!-- /tabla:controles -->

Regresiones frente a la base:

<!-- tabla:regresiones -->
| Condición | Normas | Resuelve la base y no esta | Resuelve esta y no la base |
| --- | --- | --- | --- |
| solo prompt | original | pev-010, pev-011, pev-017, pev-021, pev-024, pev-027, pev-030, pev-049, pev-050 | pev-012, pev-015, pev-028, pev-034, pev-037, pev-038, pev-042 |
| solo prompt | b | pev-011, pev-017, pev-021, pev-027, pev-030, pev-035, pev-049, pev-050 | pev-009, pev-015, pev-034, pev-037, pev-038, pev-041, pev-042 |
| solo prompt | c | pev-001, pev-012, pev-017, pev-021, pev-027, pev-049, pev-050 | pev-028, pev-034, pev-038, pev-041, pev-042 |
<!-- /tabla:regresiones -->

## Parte 5 · Recursos y producción

*A cargo de Pía (#2).* VRAM, tiempo y costo por caso en la A100 de 40 GB, paralelismo, casos simultáneos en producción,
proyección de consumo, escalado y trabajos futuros.

## Trazabilidad de las corridas

<!-- tabla:trazabilidad -->
| Corrida | Casos | Prompt (versión · sha256) | Modelo · revisión | Commit | Comando |
| --- | --- | --- | --- | --- | --- |
| `matriz-base` | todos | catedra · `f23f5921894f` | google/gemma-4-E4B-it · `4ecc2ba63bca` | `dfb9622` | `python -m evaluacion.componer --etiqueta matriz-base --partes corridas/prompt/busqueda-01/f23f5921894f corridas/eval/prompt-antes` (partes: `corridas/prompt/busqueda-01/f23f5921894f` @ `03743a8`, lote 15; `corridas/eval/prompt-antes` @ `7efb31e`, lote 50) |
| `matriz-solo-prompt` | todos | optimizado · `f7e6674cd484` | google/gemma-4-E4B-it · `4ecc2ba63bca` | `5c7d30d` | `python -m evaluacion.componer --etiqueta matriz-solo-prompt --partes corridas/prompt/busqueda-01/f7e6674cd484 corridas/eval/prompt-despues` (partes: `corridas/prompt/busqueda-01/f7e6674cd484` @ `03743a8`, lote 15; `corridas/eval/prompt-despues` @ `2d0b182`, lote 50) |
| `prompt-antes` | validacion | catedra · `f23f5921894f` | google/gemma-4-E4B-it · `4ecc2ba63bca` | `7efb31e` | `ADMISION_PROMPT=catedra python -m evaluacion.evaluar --etiqueta prompt-antes --casos validacion` |
| `prompt-despues` | validacion | optimizado · `f7e6674cd484` | google/gemma-4-E4B-it · `4ecc2ba63bca` | `2d0b182` | `ADMISION_PROMPT=optimizado python -m evaluacion.evaluar --etiqueta prompt-despues --casos validacion` |
<!-- /tabla:trazabilidad -->

## Experimentos que no funcionaron

Se documentan todos, no sólo el final.

- **Prompt optimizado por bloques** (Parte 3). Ganaba en la partición de optimización (18/90 contra 10/90) y perdió en
  validación (4/60 contra 17/60). No se adoptó. Corridas: `corridas/prompt/busqueda-01/`,
  `corridas/eval/prompt-antes/` y `corridas/eval/prompt-despues/`.
- **Correr en Modal** (A100 de 40 GB). Modal no habilita ninguna GPU, ni siquiera la T4, sin una tarjeta cargada. Se
  pasó a Kaggle 2×T4. `modal_app.py` queda para quien tenga la cuenta habilitada.
