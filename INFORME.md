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
  es la partición de 20 casos de práctica de la Parte 3. Son las finales: `sft-catedra-01` entrenó con estos mismos
  archivos (#4) y el manifiesto dice «final» desde el 18/11/2026.
- **Tamaño.** Entre 7.474 y 15.186 caracteres por conversación. Los tokens con el tokenizador del modelo los mide Juli
  al entrenar (#4).

**Límites.** Las etiquetas son derivadas: no hay etiquetas oficiales contra las que medir su exactitud. Las costumbres
se eligieron explorando el mismo historial, así que sus porcentajes no son una evaluación independiente. El CSV no
registra minutos de atención ni eventos posteriores, y no se deducen incumplimientos de lo que no está.

**Reproducción.** `python -m datos.preparar` regenera todo y `python -m datos.verificar` contrasta las huellas de
fuentes, código y salidas, cada mensaje contra su traza y el reparto contra la semilla. Lo cubren 49 pruebas
(`tests/test_*_datos.py` sin las de entrenamiento, y `tests/test_casos_demo.py`). Verificado sobre `main` en `1ddc245`.

**Demo.** Con el checkpoint final `sft-catedra-01` (`292c8137`) sobre normas `b`, en 14 casos de práctica elegidos por
la nota de triage, sin mirar las respuestas esperadas (`python -m datos.candidatos_demo` y `python -m datos.casos_demo`):
8 tiempo-dependientes que llegan en ambulancia y 6 donde decide una costumbre. Corrida `corridas/demo/b-sft-catedra-01/`
en Kaggle 2×T4, commit `dfa9e78`. **6 de 14 aprueban los 9 controles.** El circuito es correcto en los 8
tiempo-dependientes y 5 quedan completos: el modelo busca la sección del circuito y la de ambulancia y calcula el plazo
con los valores de `b` (en `pev-026` no restó la reducción por ambulancia). La costumbre de la doble credencial se
aplicó (`pev-050`). **La del voluntariado no se aplicó en ninguno de los 6 casos que la requieren**: el modelo nunca
marcó el aviso. Es un ejemplo poco frecuente: sólo 53 de las 640 conversaciones con que se entrenó (8,3 %) terminan
con el aviso, y 209 de las 2.176 del conjunto completo (9,6 %). Puede que no haya alcanzado para aprenderlo, pero no se
probó. Para el Loom se muestran `pev-011` (dolor torácico en ambulancia: 15
− 3 = 12 minutos en `b`) y `pev-050` (doble credencial: verifica la prepaga). Detalle por caso en
[datos/DEMO.md](datos/DEMO.md). Son 14 casos elegidos, no una evaluación: la evaluación es la matriz de la Parte 4.

## Parte 2 · Buscador (RAG)

*A cargo de Pía (#2).*

**Qué buscador usa el agente.** `buscador/bm25.py`: BM25 propio, sin dependencias, fuera de `admision/`. Parte del BM25
inicial de Juan y Pía le agregó validaciones (consultas vacías o sin coincidencias devuelven `[]`, argumentos inválidos
fallan), normalización de tildes y un modo opcional de fragmentos por párrafo. Lee las 20 secciones y los valores de
`parametros.yaml` sólo desde la carpeta que recibe, distractoras incluidas; ningún número normativo queda en el código.
Las pruebas (`tests/test_buscador*.py`, sin GPU ni credenciales) lo comprueban en `original`, `b`, `c` y en una carpeta
temporal con un parámetro cambiado. `entrega.py` lo construye con el bloque `buscador` de `configuracion.json`: una
sección por fragmento, `k_entorno=2`, `k1=1,5`, `b=0,75`. Es el mismo código con que se corrieron las tres filas de la
matriz (Parte 4).

**Evaluación, antes del agente.** 60 consultas de `rag/consultas_dev.jsonl` sobre `normas/original`, con las funciones
del evaluador oficial (`python -m buscador.evaluar --salida resultados/rag`). La fila sección/k=2 coincide con
`python -m admision.evaluar_rag --entrega buscador/entrega_rag.py --normas normas/original --consultas
rag/consultas_dev.jsonl`. Los tokens son la estimación del kit (cuatro caracteres por token), no los del tokenizador.

| Configuración | Recall | Precisión | Tokens/consulta | Consultas completas |
|---|---:|---:|---:|---:|
| Referencia BM25 de la cátedra (k=2) | 0,875 | 0,492 | 580 | 51/60 |
| **Sección, k=2 (la que usa el agente)** | **0,817** | **0,467** | **617** | **48/60** |
| Sección, k=4 | 0,950 | 0,271 | 1.269 | 57/60 |
| Párrafo, k=4 | 0,783 | 0,300 | 383 | 45/60 |

Con sección/k=2 recupera toda la evidencia en las consultas directas (recall 1,0) y distractoras (1,0), casi toda en
las numéricas (0,917) y las de dos secciones (0,875), y falla en las coloquiales (0,25): cuando la consulta no usa las
palabras de la norma, BM25 no la encuentra. Queda por debajo de la referencia de la cátedra (3 consultas completas
menos); no tenemos su implementación para explicar la diferencia.

Con presupuestos fijos de 256 y 512 tokens, los párrafos recuperan más que las secciones (recall 0,708 contra 0,600 y
0,767 contra 0,692), pero el entorno no aplica presupuestos: el agente ve los primeros k. Las ocho configuraciones
(sección y párrafo, k de 1 a 4) y los tres presupuestos están en [resultados/rag/INFORME.md](resultados/rag/INFORME.md);
el ranking con texto y la evidencia cubierta por consulta, en `resultados/rag/recuperaciones.jsonl`, y los hashes de
entradas y código, en `resultados/rag/manifiesto.json`.

**Decisión.** Se quedó sección/k=2: es la más cercana a la referencia con un contexto parecido (617 tokens). Sección/k=4
completa 57 de 60, pero duplica el contexto y baja la precisión a 0,271; párrafo/k=4 achica el contexto pero completa
menos. Ninguna de las dos se probó con el agente, así que no sabemos si cambiarían los casos resueltos.

**Límites.** No hay métricas formales en `b` y `c`: algunas esperadas de las consultas tienen números de `original`
(por ejemplo, d033 espera 67 años), y el script registra esas consultas en el manifiesto sin puntuarlas ni cambiarlas.
Que `b` y `c` carguen sus propios valores lo cubren las pruebas. Todo se eligió sobre las consultas de desarrollo, no
sobre el test secreto. Detalle en [resultados/rag/ANALISIS.md](resultados/rag/ANALISIS.md) y
[buscador/README.md](buscador/README.md).

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
transformers, el commit, las variables y cuánto tardó. La Parte 5 usa esos tiempos como medición en T4, no como de la A100.

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
la VRAM y el costo de estas corridas figuran en la Parte 5 como medidos en T4, no como de la A100. Comandos, reanudación y qué queda registrado:
[`entrenar/README.md`](entrenar/README.md). Todas las decisiones, con su motivo y su consecuencia:
[`entrenar/DECISIONES.md`](entrenar/DECISIONES.md).

**Corrida entregada: `sft-catedra-01`, paso 80.** Se entrenó con una **submuestra de 640 de las 2.176 conversaciones de
train (elegidas al azar, semilla 42), una época, 8 conversaciones por paso = 80 pasos**, y no con las 2 épocas sobre todo el
conjunto que se había planeado: en las 2×T4 se midieron ~72 tokens/s, el plan completo (~13 M de tokens) habría tardado ~50 h
contra sesiones de 12 h y una cuota de 30 h por semana. La corrida duró 7 h 55 min (~8,5 h de cuota) y la pérdida de validación
bajó de 0,031 (paso 20) a 0,0093 (40), 0,0053 (60) y **0,0042 (80, el elegido)**. En la matriz (Parte 4) da 27/25/21
contra 25/24/25 de la referencia de la cátedra. Lo que se pierde por usar una submuestra no está medido: no hay corrida con
todo el conjunto.

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
La tabla de trazabilidad dice de dónde sale cada parte. «solo entrenamiento» sí se jugó entera en una corrida
(`evaluacion.matriz --correr 'solo entrenamiento'`, lote 10, commit `15558ca`, entorno
`corridas/entornos/kaggle-20261119-014649.json`). Un primer intento con lote 15 dejó 33 de los 50 casos sin decisión: el
lote se quedó sin memoria en la 7.ª llamada y el reintento caso por caso no la liberaba. Se arregló en `agente/ciclo.py` y
esa corrida no se usa. Son corridas en Kaggle 2×T4, no en la A100 de la referencia de la cátedra.

<!-- tabla:matriz -->
| Condición | Normas original | Normas b | Normas c | Corrida |
| --- | --- | --- | --- | --- |
| base | 10/50 | 9/50 | 8/50 | `corridas/eval/matriz-base` |
| solo prompt | 8/50 | 8/50 | 6/50 | `corridas/eval/matriz-solo-prompt` |
| solo entrenamiento | 27/50 | 25/50 | 21/50 | `corridas/eval/matriz-solo-entrenamiento` |
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
| solo entrenamiento | original | 0.96 | 1.00 | 1.00 | 1.00 | 0.98 | 0.94 | 0.86 | 0.72 | 1.00 |
| solo entrenamiento | b | 0.94 | 1.00 | 1.00 | 1.00 | 0.98 | 0.94 | 0.84 | 0.72 | 1.00 |
| solo entrenamiento | c | 0.98 | 1.00 | 0.94 | 1.00 | 0.98 | 0.90 | 0.80 | 0.72 | 1.00 |
<!-- /tabla:controles -->

Regresiones frente a la base:

<!-- tabla:regresiones -->
| Condición | Normas | Resuelve la base y no esta | Resuelve esta y no la base |
| --- | --- | --- | --- |
| solo prompt | original | pev-010, pev-011, pev-017, pev-021, pev-024, pev-027, pev-030, pev-049, pev-050 | pev-012, pev-015, pev-028, pev-034, pev-037, pev-038, pev-042 |
| solo prompt | b | pev-011, pev-017, pev-021, pev-027, pev-030, pev-035, pev-049, pev-050 | pev-009, pev-015, pev-034, pev-037, pev-038, pev-041, pev-042 |
| solo prompt | c | pev-001, pev-012, pev-017, pev-021, pev-027, pev-049, pev-050 | pev-028, pev-034, pev-038, pev-041, pev-042 |
| solo entrenamiento | original | pev-011, pev-017 | pev-001, pev-002, pev-009, pev-012, pev-014, pev-020, pev-022, pev-028, pev-029, pev-034, pev-035, pev-036, pev-037, pev-038, pev-039, pev-040, pev-044, pev-045, pev-048 |
| solo entrenamiento | b | pev-017 | pev-002, pev-003, pev-012, pev-013, pev-014, pev-016, pev-019, pev-022, pev-024, pev-028, pev-034, pev-037, pev-038, pev-039, pev-040, pev-044, pev-045 |
| solo entrenamiento | c | pev-012, pev-017, pev-050 | pev-002, pev-003, pev-010, pev-013, pev-022, pev-024, pev-028, pev-029, pev-034, pev-035, pev-036, pev-037, pev-038, pev-039, pev-044, pev-045 |
<!-- /tabla:regresiones -->

**Lectura.** El entrenamiento es lo que mueve la matriz: 27/25/21 contra 10/9/8 de la base, con el mismo prompt. La
referencia de la cátedra con fine-tuning da 25/24/25. Quedamos arriba en original y en b, y abajo en c. Con 50 casos, una
diferencia de uno o dos es ruido. La caída de 27 a 21 entre original y c no aparece en la referencia, y puede venir de la
submuestra (640 de 2.176 conversaciones), pero no lo medimos. Lo que más sube es el box antes del registro (0,72 → 1,00 en
original), el registro (0,76 → 0,96) y la verificación (0,82 → 1,00). El aviso al voluntariado no se mueve: 0,72, igual que
la base, en las tres normas. La demo (Parte 1) ya mostraba que el modelo no da el aviso en ninguno de los casos que lo
piden. Regresiones frente a la base hay pocas, y pev-017 cae en las tres normas.

## Parte 5 · Recursos y producción

*A cargo de Pía (#2).*

**Límite principal: no medimos en la A100 de 40 GB.** Modal no habilita GPU sin tarjeta cargada (Parte 4), así que todo
se corrió en Kaggle con 2×T4 (15 GiB cada una, sin bf16 nativo). En esta parte se separan dos cosas: lo **medido** en
T4, con el archivo que lo respalda, y lo **estimado** para la A100, con sus supuestos. El único precio que se usa es el de
`mission.md`: una A100 de 40 GB cuesta unos **2,10 USD por hora** en Modal.

### Medido en Kaggle 2×T4

**Entrenamiento** (`sft-catedra-01`, `corridas/entrenamiento/sft-catedra-01/manifiesto.json` y
[entrenar/DECISIONES.md](entrenar/DECISIONES.md)): 7 h 55 min (28.518 s) para 80 pasos de 8 conversaciones (acumulación
de gradiente de 8), 72–74 tokens/s. Pico de VRAM de 12,4 GiB por GPU, con el modelo en bf16 repartido entre las dos y
contextos de hasta 4.192 tokens. Las dos T4 trabajan una después de la otra, así que la velocidad es la de una sola.

**Evaluación e inferencia.** `jugar_lote` abre todos los casos a la vez y, en cada turno, el modelo genera en tandas de
`lote` conversaciones (`agente/modelo.py`). El tiempo por caso es el tiempo total dividido por los casos.

| Corrida | Modelo | Lote | Carga | Tiempo total | Por caso | Llamadas | Búsquedas | Contexto (caracteres) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `prompt-antes` (original, 20 casos) | Gemma 4 E4B sin entrenar | 50 | 131,8 s | 898 s | 44,9 s | 4,8 | 1,2 | 18.159 |
| `matriz-solo-entrenamiento` (original) | checkpoint `292c8137` | 10 | 131,4 s | 4.136 s | 82,7 s | 6,7 | 3,22 | 45.964 |
| `matriz-solo-entrenamiento` (b) | checkpoint `292c8137` | 10 | 13,6 s | 4.207 s | 84,1 s | 6,7 | 3,24 | 46.299 |
| `matriz-solo-entrenamiento` (c) | checkpoint `292c8137` | 10 | 12,8 s | 4.202 s | 84,0 s | 6,8 | 3,26 | 46.523 |

Las cifras salen del `resumen.json` de cada carpeta en `corridas/eval/`. La carga de b y c es más corta porque el modelo
ya estaba en el disco de la sesión. El modelo entrenado tarda casi el doble por caso que el base porque trabaja más:
hace más llamadas, busca casi tres veces más en las normas y arrastra 2,5 veces más contexto. Con ese trabajo resuelve
27/25/21 casos en lugar de 10/9/8.

**VRAM en inferencia.** Cargar el checkpoint ocupa 8,71 + 6,37 = 15,1 GiB entre las dos GPU
(`corridas/entrenamiento/verificacion-292c8137984.json`). Con el modelo entrenado, **10 conversaciones a la vez entran y
15 no**: el primer intento con lote 15 se quedó sin memoria en la 7.ª llamada (Parte 4). El modelo base, con un tercio
del contexto, corrió 20 a la vez sin problemas (`prompt-antes`).

**Horas de GPU del desarrollo.** Las sesiones registradas en `corridas/entornos/` suman **25,4 h** de 2×T4: optimización
del prompt (11,9 h), entrenamiento (7,9 h), matriz con el modelo entrenado (3,5 h), evaluaciones del prompt (1,6 h) y
demo (0,4 h). Faltan los dos ensayos de entrenamiento fallidos, que sólo quedaron en W&B. **Costo en dinero: 0 USD**,
porque Kaggle es gratis (30 h de GPU por semana).

### Estimado para la A100 de 40 GB

Estas cifras **no son mediciones**. Suponen que la A100 tarda por caso, como mucho, lo mismo que las 2×T4. Es un
supuesto conservador: la A100 tiene bf16 nativo y el modelo entra en una sola GPU, pero no lo comprobamos.

| Concepto | Cálculo | Estimación |
|---|---|---:|
| Costo por caso (modelo entrenado) | 84 s × 2,10 USD/h | **≈ 0,049 USD** como máximo |
| Capacidad de una A100 | 3.600 s / 84 s por caso | **≥ 43 casos/h** (≈ 1.000 por día) |
| Casos a la vez en GPU | quedan ~24 GiB libres tras cargar 15,1 GiB, contra ~14 GiB en 2×T4, donde entraron 10 | **unos 15–17**, a verificar |
| Desarrollo, si se hubiera pagado | 25,4 h × 2,10 USD/h | **≤ 53 USD** |
| Mantenimiento, por actualización | reentrenar (~1 h en A100, estimación de [DECISIONES.md](entrenar/DECISIONES.md)) + matriz de 150 casos (≤ 3,5 h) | **≈ 10 USD** |

### Producción: simultaneidad, consumo y escalado

**Casos simultáneos.** Medido: 10 casos a la vez en 2×T4, con unos 43 casos por hora. En una A100 estimamos unos 15–17
a la vez. Pasado ese número, los casos esperan su turno: no se pierden, pero tardan más.

**Proyección de consumo.** No tenemos datos de demanda del hospital, así que usamos tres escenarios **hipotéticos** y el
costo máximo de 0,049 USD por caso (30,4 días por mes):

| Admisiones por día | Pagando por uso (GPU que se apaga sola) | A100 prendida todo el mes (730 h) |
|---:|---:|---:|
| 100 | ≈ 150 USD/mes | ≈ 1.530 USD/mes |
| 300 | ≈ 450 USD/mes | ≈ 1.530 USD/mes |
| 1.000 | ≈ 1.490 USD/mes | ≈ 1.530 USD/mes |

Cerca de 1.000 admisiones por día, las dos formas cuestan casi lo mismo y una A100 está cerca de su capacidad. Por debajo,
conviene pagar por uso. **Salvedad:** los 0,049 USD por caso salen de correr muchos casos juntos. Con poca demanda, cada
caso corre casi solo y ocupa la GPU todo el tiempo de su conversación, y ese tiempo no lo medimos. Con 100 admisiones por
día el costo real por caso va a ser mayor.

**Escalado.** Hasta ~1.000 casos por día, una A100 con lote de 15 aproximadamente. Más allá, una réplica más por cada
~1.000 casos diarios, con una cola delante que reparta los casos. Las réplicas no comparten estado: cada caso es
independiente, y cada una carga el modelo y las normas por su cuenta (unos 2 min de carga en T4).

### Trabajos futuros

- **Medir en una A100 de 40 GB** con `modal_app.py`, que ya está preparado: tiempo por caso con el lote más grande que
  entre, tiempo de un caso solo y VRAM durante la corrida, no sólo al cargar.
- **Servir con un motor de inferencia con lotes continuos y caché de prefijos** (por ejemplo vLLM): todos los casos
  comparten el prompt de sistema y suelen buscar las mismas secciones.
- **Achicar el contexto**, que es lo que limita los casos a la vez: probar los fragmentos por párrafo (Parte 2: 383
  tokens por búsqueda contra 617) y medir si se pierden casos resueltos.
- **Cuantizar el modelo** (8 o 4 bits) para que entren más casos por GPU, midiendo cuántos casos se pierden.
- **Entrenar con todo el conjunto** (2.176 conversaciones, 2 épocas): en A100 serían horas y no días, y podría mejorar el
  aviso al voluntariado, que no se mueve de 0,72.
- **Mejorar las búsquedas coloquiales** (recall 0,25 en la Parte 2) con un buscador híbrido o con reformulación de la
  consulta.

## Trazabilidad de las corridas

<!-- tabla:trazabilidad -->
| Corrida | Casos | Prompt (versión · sha256) | Modelo · revisión | Commit | Comando |
| --- | --- | --- | --- | --- | --- |
| `matriz-base` | todos | catedra · `f23f5921894f` | google/gemma-4-E4B-it · `4ecc2ba63bca` | `dfb9622` | `python -m evaluacion.componer --etiqueta matriz-base --partes corridas/prompt/busqueda-01/f23f5921894f corridas/eval/prompt-antes` (partes: `corridas/prompt/busqueda-01/f23f5921894f` @ `03743a8`, lote 15; `corridas/eval/prompt-antes` @ `7efb31e`, lote 50) |
| `matriz-solo-entrenamiento` | todos | catedra · `f23f5921894f` | genai-grupo-2/emergency-admission-agent · `292c81379842` | `15558ca` | `ADMISION_PROMPT=catedra ADMISION_MODELO_REPO=genai-grupo-2/emergency-admission-agent ADMISION_MODELO_REVISION=292c8137984283d426de735309d108459b5e51f9 python -m evaluacion.evaluar --etiqueta matriz-solo-entrenamiento --casos todos` |
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
