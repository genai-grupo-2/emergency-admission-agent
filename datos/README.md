# Datos del historial — issue #1 de Cande

Este directorio contiene el trabajo de datos del grupo. El primer paso es comprobar que las fuentes estén completas y que sus registros se puedan relacionar correctamente. La clasificación de decisiones según las normas viene después.

## Repetir la inspección

Desde la raíz del repositorio, con el entorno preparado según [SETUP.md](../SETUP.md):

```powershell
uv run --locked python -X utf8 -m datos.inspeccionar
```

También se puede usar directamente el Python del entorno ya instalado:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m datos.inspeccionar
```

El comando genera [diagnostico.json](diagnostico.json). Devuelve código 0 cuando pasa la revisión de integridad, y 1 si encuentra errores. El archivo contiene el detalle necesario para investigar cada problema. `registro` es la posición del registro de datos, empezando en 1; en el CSV no incluye la cabecera.

Para revisar otra copia del kit o elegir dónde guardar el diagnóstico:

```powershell
uv run --locked python -X utf8 -m datos.inspeccionar --raiz C:\ruta\al\kit --salida datos/diagnostico.json
```

Las rutas relativas de salida se interpretan desde `--raiz`. El comando impide usar uno de los tres archivos de entrada como salida.

## Qué revisa

- El CSV tiene sus 28 columnas, 2.000 admisiones y los IDs `H-0001` a `H-2000`, sin duplicados.
- Hay 2.000 trazas del historial y 800 trazas de referencia, con sus campos y tipos esperados.
- Los campos obligatorios están presentes. Cuenta por separado los vacíos permitidos: por ejemplo, no tener documento no equivale a tener una fila incompleta.
- Las herramientas son conocidas, sus argumentos tienen el formato esperado y los pasos están numerados de manera consecutiva.
- Cada traza empieza leyendo el triage y termina con una sola llamada a `registrar_decision`, dentro del límite de 40 llamadas.
- Los ocho campos de esa llamada coinciden con la ficha guardada.
- El CSV y las trazas del historial tienen los mismos IDs en el mismo orden, las mismas fechas y operadores, y las mismas fichas. Al comparar, convierte `sí/no` en booleanos, vacíos opcionales en `null` y plazos en números.
- Informa filas y trazas repetidas por contenido, además de identificadores de paciente repetidos. El identificador de paciente no reemplaza al ID de admisión.

Cada fuente incluye su tamaño y SHA-256: una huella que permite comprobar exactamente qué archivo se usó. El diagnóstico es determinista: los mismos archivos y la misma versión del script producen el mismo resultado, sin fechas de ejecución ni rutas de la computadora dentro del JSON.

## Qué significa que pase

Un resultado `ok` significa que los archivos cumplen estas comprobaciones de integridad. **No significa que las admisiones sean correctas según las normas.** Los errores de los operadores forman parte del historial que tenemos que clasificar; este paso conserva todas las filas.

El script usa únicamente `historial/historial.csv`, `historial/trazas.jsonl` y `entrenamiento/trazas.jsonl`. El historial y la referencia se revisan por separado, porque los valores de las normas cambian entre las trazas de referencia. Las fuentes de trazas provienen del [commit 876d889 de la cátedra](https://github.com/austral-ing-ai/talksmith-ing/commit/876d8894c1cd339ffb968f12754a21f460ffb393).

## Verificar el inspector

```powershell
uv run --locked python -X utf8 -m unittest discover -s tests -p "test_inspeccion_datos.py" -v
```

Las pruebas introducen problemas deliberados: IDs duplicados, trazas reordenadas, JSON roto, columnas faltantes, fichas distintas, tipos inválidos y llamadas posteriores al cierre. También comprueban que los vacíos opcionales y los pacientes repetidos no se confundan con archivos corruptos.

## Regenerar la clasificación y la evidencia

```powershell
uv run --locked python -X utf8 -m datos.clasificar
```

El comando comprueba primero la integridad y después genera:

- `historial_clasificado.csv`: exactamente `id,tipo`, con 2.000 filas en el orden original.
- `costumbres.md`: las dos costumbres inferidas, con evidencia y contraejemplos.
- `datos/clasificacion_detalle.jsonl`: por cada admisión, las normas violadas o los desvíos de costumbres que explican su etiqueta.
- `datos/evidencia_costumbres.json`: todos los IDs de apoyo y contraejemplos, y los umbrales de edad comparados.
- `datos/resumen_clasificacion.json`: cantidades y huellas de fuentes, código y entregables.

Las fuentes actuales producen 1.600 `correcta`, 240 `error` y 160 `ruido`. Son etiquetas derivadas de las reglas y la evidencia, no una exactitud medida contra etiquetas oficiales.

### Cómo se decide

Primero se comprueban las normas escritas de registro, ubicación antes del registro, circuito y plazo, cobertura, notificación y consulta/verificación. Los números se leen de `normas/original/parametros.yaml`. Se respetan las excepciones de documento extranjero urgente, mayores, ART, terminación reservada y llegada en ambulancia. Los demás documentos se conservan en las huellas de fuentes; no se inventan tiempos o eventos que el historial no registra.

Si hay una violación escrita, el tipo es `error`. En las filas sin esas violaciones se estudian dos patrones: preferencia de prepaga ante doble credencial y aviso al voluntariado según edad y acompañante. Se exige al menos 80% de apoyo y 20 ejemplos en cada grupo. El umbral que mejor explica el voluntariado es 75 años; si dos umbrales empatan, el proceso se detiene para revisión.

Una fila sin violaciones escritas que se aparta de esos patrones es `ruido`. Todas las restantes son `correcta`. Las costumbres se infieren del historial completo y sus porcentajes no son un benchmark independiente. Se revisan sólo admisiones estáticas: ante circuitos simultáneos, categorías desconocidas o evidencia insuficiente el proceso se detiene, en lugar de asignar una etiqueta dudosa.

Ejemplo: `H-0010` registró 10 minutos para un ECG cuando, por llegar en ambulancia, correspondían 5 según NOR-TDE-01 y NOR-TDE-04. Su detalle registra ambas normas, el campo y los valores esperado y observado.

## Coordinación pendiente

El formato final de conversaciones, las particiones y el prompt deben revisarse con Juan y Juli antes de entrenar. La demo con los nueve controles depende del modelo final de Juli. Este trabajo de datos no cierra por sí solo el issue completo.

## Regenerar todos los datos de entrenamiento

```powershell
uv run --locked python -X utf8 -m datos.preparar
uv run --locked python -X utf8 -m datos.verificar
```

El primer comando repite inspección y clasificación, convierte las 1.600 trazas clasificadas como correctas y las 800 de referencia, y genera:

- `datos/conversaciones/train.jsonl` y `validacion.jsonl`: conversaciones y metadatos de procedencia. Cada registro contiene `messages`, una lista de objetos `role,content`. Juli puede tomar esa columna para su cargador.
- `datos/prompts/sistema-usado.txt`: texto exacto del mensaje de sistema usado.
- `datos/manifiesto.json`: fuentes, código, prompt, selección, exclusiones, semilla, IDs de cada partición y huellas de los resultados.

Cada conversación empieza con el sistema y el pedido del usuario. Después alterna una llamada JSON del asistente y el resultado de la herramienta como mensaje del usuario. Termina en la llamada a `registrar_decision`, sin agregar su resultado. Los valores normativos de cada traza se conservan tal como vienen; las 800 de referencia no se reinterpretan usando los parámetros originales del historial.

La semilla por defecto es 42 y la fracción objetivo de validación es 10%. Se agrupan los identificadores de paciente repetidos y las conversaciones que sólo cambian ID/nombre, incluso si el vínculo es transitivo. Cada grupo queda entero en una partición. No se confunden documentos ni números normativos al calcular esa huella. La fracción real puede variar por el tamaño de los grupos: las fuentes actuales producen 2.176 conversaciones de entrenamiento y 224 de validación, sin identidades de paciente ni huellas compartidas entre ambas. No hay copias adicionales por huella en estas fuentes.

El campo `id` de cada conversación tiene prefijo de fuente, por ejemplo `historial:H-0001` o `entrenamiento:E-001`. `traza_sha256` identifica la representación JSON canónica de la traza original. El registro incluye su paciente, origen y grupo; esos metadatos no se agregan a los mensajes enviados al modelo. La clasificación excluye 240 errores y 160 ruidos del historial, sin inventar respuestas corregidas. No se generaron ejemplos sintéticos para entrenamiento.

El segundo comando comprueba las huellas de fuentes, código y entregables, la selección completa de conversaciones, cada mensaje contra su traza y la reproducción de las particiones. Se detiene si se altera una fuente, una etiqueta, un mensaje, el prompt o el reparto. Las pruebas de conversión también comprueban de forma explícita el protocolo y la conservación de argumentos y resultados.

Para cambiar la semilla, la proporción o incorporar las instrucciones que entregue Juan:

```powershell
uv run --locked python -X utf8 -m datos.preparar --semilla 42 --fraccion-validacion 0.1 --prompt ruta/al/prompt-acordado.txt
uv run --locked python -X utf8 -m datos.verificar
```

El archivo de prompt debe estar en UTF-8. Si no se pasa `--prompt`, se usa `mensaje_de_sistema()` del ejemplo de la cátedra, como borrador. Cambiarlo regenera las conversaciones y sus huellas. No guardar el prompt acordado en `datos/prompts/sistema-usado.txt` antes de regenerar: ese archivo es una salida del proceso; conservar una entrada aparte para el prompt de Juan.

El manifiesto sigue marcado como provisional hasta que el grupo revise las instrucciones y particiones. El entrenamiento debe comenzar después de optimizar el prompt. La plantilla de chat, la tokenización y el ajuste de longitud se verifican con el modelo que elija Juli; los tamaños informados aquí son caracteres, no tokens.

### Huellas y Windows/Linux

El diagnóstico de inspección conserva SHA-256 y tamaños de los bytes de entrada. En el resumen de clasificación y el manifiesto, `fuentes_sha256_lf` y `codigo_sha256_lf` normalizan sólo los saltos CRLF a LF antes de calcular SHA-256: así un checkout en Windows o Linux no parece un cambio de contenido. Los hashes de entregables, conversaciones y prompt se calculan sobre sus bytes exactos. `.gitattributes` conserva los saltos LF de nuestros entregables y preserva los bytes del prompt. No cambia el código del kit.

## Estado del issue

- [x] Inspección reproducible, esquemas, IDs, vacíos y correspondencia CSV/trazas.
- [x] Reglas escritas con precedencias y pruebas de límites.
- [x] Costumbres documentadas con evidencia y contraejemplos.
- [x] Clasificación de las 2.000 filas y justificación de etiquetas.
- [x] Conversión de las trazas seleccionadas y las 800 de referencia.
- [x] Particiones provisionales, semilla, manifiesto y verificación de reproducción.
- [ ] Confirmar formato y particiones con Juan/Juli e incorporar el prompt optimizado.
- [ ] Juli comprueba que se pueden entrenar con la plantilla y el modelo elegidos.
- [ ] Ejecutar y documentar los dos casos de demo con el checkpoint final.
- [ ] Integrar nuestra sección de datos en el informe grupal y grabar la parte propia del Loom.

La sección para integrar en el informe está en [INFORME_DATOS.md](INFORME_DATOS.md). La guía de demo y sus dependencias está en [DEMO.md](DEMO.md).
