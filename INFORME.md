# Informe · Agente de admisión de guardia (grupo 2)

Un apartado por parte de la misión ([mission.md](mission.md)). Cada integrante redacta su parte y Juan la integra acá.
**Las tablas no se escriben a mano**: las genera `python -m evaluacion.tablas` desde `corridas/`, y lo que todavía no se
corrió figura como «pendiente de correr» o «bloqueado». Cada número dice de qué corrida sale, y `condicion.json` de esa
corrida tiene el comando, el commit, el checkpoint y el prompt.

Estado al 5/11/2026: el agente, la optimización de prompt y la evaluación están implementados y probados sin GPU con
un modelo falso. **Todavía no hay ninguna corrida con el modelo real**, así que este informe no trae resultados.

## Parte 1 · Curado del historial

*A cargo de Cande (#1).* Código en `datos/`, comandos y formatos en [datos/README.md](datos/README.md). Todo lo que
sigue sale de scripts del repositorio y se comprueba con `python -m datos.verificar`.

**Fuentes e integridad** (`python -m datos.inspeccionar`, salida en `datos/diagnostico.json`):
- Se usaron las 2.000 admisiones de `historial/historial.csv`, sus 2.000 trazas y las 800 trazas de referencia de
  `entrenamiento/trazas.jsonl`. No se cargan las respuestas de los casos de práctica ni el test.
- Los 2.000 IDs son únicos y coinciden en orden, fecha, operador y ficha entre el CSV y las trazas. No hay filas ni
  trazas duplicadas por contenido.
- Hay identificadores de paciente repetidos (191 grupos en el historial y 34 en la referencia). No son admisiones
  duplicadas, pero las particiones los mantienen juntos.

**Clasificación** (`python -m datos.clasificar`):
- **Norma escrita primero.** Las normas se implementaron como comprobaciones sin modelo (`datos/normas.py`), con los
  valores leídos de `normas/original/parametros.yaml` y las precedencias de documento extranjero urgente, edad para el
  box antes del registro, ART, afiliación con terminación reservada y reducción del plazo por ambulancia. Una fila que
  viola una norma es `error`, aunque también se aparte de una costumbre.
- **Costumbre después.** En las 1.760 filas sin violaciones escritas se buscan las costumbres. La que se aparta de una
  costumbre es `ruido`, y el resto es `correcta`.
- **Sin etiquetas dudosas.** Ante circuitos simultáneos, categorías desconocidas o umbrales empatados, el proceso se
  detiene y pide revisión. No quedó ningún caso sin resolver.

| Tipo | Filas |
| --- | --- |
| correcta | 1.600 |
| error | 240 |
| ruido | 160 |

`historial_clasificado.csv` tiene las columnas `id,tipo` y los 2.000 IDs en el orden original. El motivo de cada
etiqueta (norma, campo, valor esperado y observado) está en `datos/clasificacion_detalle.jsonl`. Ejemplo: `H-0010`
consignó 10 minutos para el ECG, y por llegar en ambulancia correspondían 5 (NOR-TDE-01 y NOR-TDE-04).

**Costumbres** ([costumbres.md](costumbres.md); todos los IDs de apoyo y los contraejemplos en
`datos/evidencia_costumbres.json`). Se pidió como mínimo 20 ejemplos y 80 % de coincidencia en cada grupo.

| Costumbre | Coincidencia | Comparación |
| --- | --- | --- |
| Avisar al voluntariado si el paciente tiene al menos 75 años y llega sin acompañante | 1.609 de 1.760 (167 de 186 donde corresponde avisar; 1.442 de 1.574 en el resto) | No avisar nunca: 1.461. Umbral de 76 años: 1.599 |
| Con obra social y prepaga a la vez, verificar la prepaga (fuera de accidentes laborales, donde va la ART por norma) | 163 de 172 | Las normas no fijan prioridad entre las dos |

El umbral de 75 años se obtuvo comparando todas las edades observadas; no es un parámetro de las normas. La segunda
costumbre se mira en la entidad verificada y no en la cobertura final, que puede quedar en `sin_cobertura` por una
afiliación inactiva o reservada.

**Conversaciones de entrenamiento** (`python -m datos.preparar`, salidas en `datos/conversaciones/` y
`datos/manifiesto.json`):
- **Selección.** Las 1.600 trazas `correcta` más las 800 de referencia: 2.400 conversaciones. Se excluyeron los 240
  errores y los 160 ruidos, sin reemplazarlos por respuestas corregidas. No se agregaron datos sintéticos.
- **Formato.** El del agente (Parte 3): mensaje de sistema, pedido inicial, llamadas JSON del asistente y resultados
  como mensajes del usuario. Termina en `registrar_decision`, sin observación posterior. Los valores de las normas de
  cada traza se conservan, así el modelo aprende a buscarlos y no a memorizarlos.
- **Prompt.** El de la cátedra, huella `f23f5921894f`: la misma de las corridas `prompt-antes` y `matriz-base`. Como el
  prompt optimizado no se adoptó (Parte 3), no hubo que regenerar las conversaciones.
- **Particiones.** Semilla 42 y 10 % de validación como objetivo. Se agrupa por paciente y por huella de conversación,
  y cada grupo queda entero de un lado: 2.176 de entrenamiento (1.448 del historial y 728 de referencia) y 224 de
  validación (152 y 72), sin IDs, pacientes ni huellas compartidas. Esta validación es para seguir el entrenamiento; no
  es la partición de 20 casos de práctica de la Parte 3.
- **Tamaño.** Entre 7.474 y 15.186 caracteres por conversación. Los tokens con el tokenizador del modelo los mide Juli
  al entrenar (#4).

**Límites.** Las etiquetas son derivadas: no hay etiquetas oficiales contra las que medir su exactitud. Las costumbres
se eligieron explorando el mismo historial, así que sus porcentajes no son una evaluación independiente. El CSV no
registra minutos de atención ni eventos posteriores, y no se deducen incumplimientos de lo que no está.

**Reproducción.** `python -m datos.preparar` regenera todo y `python -m datos.verificar` contrasta las huellas de
fuentes, código y salidas, cada mensaje contra su traza y el reparto contra la semilla. Lo cubren 42 pruebas
(`tests/test_*_datos.py`). Verificado sobre `main` en `eef6cc9`.

**Demo.** Pendiente del checkpoint de Juli (#4). Los candidatos ya están elegidos por las características del caso, sin
mirar las respuestas esperadas (`python -m datos.candidatos_demo`, plan en [datos/DEMO.md](datos/DEMO.md)).

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

**Estrategia (Juli, #4).** Fine-tuning supervisado con LoRA sobre las conversaciones de Cande, con el prompt de la cátedra
(no el optimizado, por la decisión de la Parte 3). Se calcula la pérdida sólo sobre las respuestas del asistente, es decir,
la herramienta y sus argumentos, y no sobre el prompt ni sobre los resultados de las herramientas, que vienen del entorno. El
modelo base es el mismo Gemma 4 E4B con la misma revisión que usa el agente; los adaptadores se fusionan en bf16 y esos pesos
son los que se publican y los que evalúa Juan, para que cada número corresponda a lo que carga la cátedra. El checkpoint se
elige por la pérdida sobre 40 de las 224 conversaciones de la partición de validación de Cande (al azar, con la semilla; los
índices están en el manifiesto); el test secreto y los 50 casos de práctica no intervienen. Antes
de entrenar se comprueba que el mensaje de sistema de cada conversación coincide byte a byte con el prompt, que
entrenamiento y validación no comparten ids, grupos ni huellas, y que ninguna conversación reproduce un caso de práctica.

Se entrena en Kaggle 2×T4, no en la A100 de 40 GB de la consigna, porque Modal no habilita GPU sin tarjeta. Por eso los tiempos,
la VRAM y el costo de estas corridas no se usan en la Parte 5. Comandos, reanudación y qué queda registrado:
[`entrenar/README.md`](entrenar/README.md). Todas las decisiones, con su motivo y su consecuencia:
[`entrenar/DECISIONES.md`](entrenar/DECISIONES.md).

**Corrida entregada: `sft-catedra-01`, paso 80.** Se entrenó con una **submuestra de 640 de las 2.176 conversaciones de
train (elegidas al azar, semilla 42), una época, 8 conversaciones por paso = 80 pasos**, y no con las 2 épocas sobre todo el
conjunto que se había planeado: en las 2×T4 se midieron ~72 tokens/s, el plan completo (~13 M de tokens) habría tardado ~50 h
contra sesiones de 12 h y una cuota de 30 h por semana. La corrida duró 7 h 55 min (~8,5 h de cuota) y la pérdida de validación
bajó de 0,031 (paso 20) a 0,0093 (40), 0,0053 (60) y **0,0042 (80, el elegido)**. Lo que se pierde por usar una submuestra lo
dirá la matriz; no está medido.

| | |
|---|---|
| W&B | [`sft-catedra-01`](https://forge.coreweave.com/wandb/gen-ai-grupo-2/emergency-admission-agent/runs/1y5xd2de) (run `1y5xd2de`) |
| Datos | `datos/conversaciones/train.jsonl` sha256 `75a438fa384f…` (y `validacion.jsonl`), prompt `catedra`, semilla 42, commit `55f5e12` |
| Manifiesto | `corridas/entrenamiento/sft-catedra-01/manifiesto.json`, entorno `corridas/entornos/kaggle-20261118-005300.json` |
| Hugging Face (privado) | `genai-grupo-2/emergency-admission-agent` @ `292c8137984283d426de735309d108459b5e51f9` (pesos fusionados bf16, paso 80) |
| Carga | `ADMISION_MODELO_REPO=genai-grupo-2/emergency-admission-agent ADMISION_MODELO_REVISION=292c8137984283d426de735309d108459b5e51f9` |

Los pasos 20, 40 y 60 existen como adaptadores en el mismo repo (`adaptadores/sft-catedra-01/`) pero no se evaluaron ni se
citan. Corridas que fallaron (dos ensayos por un error de dispositivos al repartir el modelo entre GPU) y el ensayo que
sí pasó están en [`entrenar/DECISIONES.md`](entrenar/DECISIONES.md) y en W&B. La fila «solo
entrenamiento» de la matriz es este checkpoint con el prompt de la cátedra (`evaluacion/matriz.json`). La fila «ambos» **no
se hizo**: pedía un segundo checkpoint entrenado con el prompt optimizado, y ese prompt se descartó en la Parte 3 porque
perdía en validación (4/60 contra 17/60). Entrenarlo igual habría costado otras ~8 h de cuota de Kaggle para una condición
que ya sabíamos peor.

**Verificación de carga** (`python -m entrenar.verificar_carga`, sesión limpia de Kaggle 2×T4, sin reentrenar, `corridas/entrenamiento/verificacion-292c8137984.json`): `entrega.construir_agente()` con la revisión publicada carga el modelo **una sola vez** (116,8 s, pico de VRAM 8,71 y 6,37 GiB en las dos GPU) y la primera respuesta es el JSON de `leer_triage`. Falta correrlo en la A100 de 40 GB que pide la consigna, que no tenemos.

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
| solo entrenamiento | pendiente de correr | pendiente de correr | pendiente de correr | — |
| ambos | no hecho: el prompt optimizado se descartó en la Parte 3 y no hay segundo checkpoint | no hecho: el prompt optimizado se descartó en la Parte 3 y no hay segundo checkpoint | no hecho: el prompt optimizado se descartó en la Parte 3 y no hay segundo checkpoint | — |
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
- **Entrenar 2 épocas sobre todo el conjunto** (Parte 4). Se descartó antes de lanzarlo: ~50 h de GPU contra 30 h de cuota
  semanal y sesiones de 12 h. Se entrenó con 640 conversaciones y una época.
- **Dos ensayos de entrenamiento fallidos** (`sft-catedra-01-ensayo`): `RuntimeError: indices should be either on cpu or on the
  same device as the indexed tensor (cuda:1)`, por el índice de `logits_to_keep` al repartir el modelo en dos GPU. Detalle y
  arreglo en [`entrenar/DECISIONES.md`](entrenar/DECISIONES.md).
- **Correr en Modal** (A100 de 40 GB). Modal no habilita ninguna GPU, ni siquiera la T4, sin una tarjeta cargada. Se
  pasó a Kaggle 2×T4. `modal_app.py` queda para quien tenga la cuenta habilitada.
