# Sección de datos para el informe grupal

Responsable: Cande. Issue [#1](https://github.com/genai-grupo-2/emergency-admission-agent/issues/1).

Esta sección está preparada para que Juan la integre en `INFORME.md`. Los comandos y formatos se explican en [README.md](README.md). El prompt y las particiones siguen pendientes de acuerdo con Juan y Juli; la demo depende del checkpoint final.

## Fuentes y controles de integridad

Se usaron las 2.000 admisiones de `historial/historial.csv`, sus 2.000 trazas y las 800 trazas de referencia de `entrenamiento/trazas.jsonl`. Se conservaron las fuentes originales y el código de `admision/`. La preparación no carga las respuestas de los casos de práctica ni del test secreto.

La inspección verifica esquemas, tipos, IDs, columnas, vacíos permitidos, herramientas, orden de pasos y ficha final. Los 2.000 IDs del historial son únicos y coinciden en orden, fecha y operador entre CSV y trazas. Los ocho campos de cada ficha coinciden después de normalizar booleanos, números y valores nulos. No se encontraron filas ni trazas duplicadas por contenido bajo las comparaciones implementadas.

Se observaron identificadores de paciente repetidos: 191 grupos en el historial, con 210 apariciones adicionales, y 34 en las trazas de referencia, con 37 apariciones adicionales. No equivalen a admisiones duplicadas. La correspondencia se hace por ID de admisión y las particiones mantienen juntos los identificadores repetidos como precaución.

## Clasificación del historial

Las reglas escritas se implementaron como comprobaciones offline independientes del agente. Los valores se leen de `normas/original/parametros.yaml`. Se contemplaron las precedencias de documento extranjero urgente, edad para box antes del registro, ART, afiliación con terminación reservada y reducción de plazos por ambulancia. Cada incumplimiento registra código de norma, campo, valor esperado y valor observado.

Un error escrito prevalece sobre cualquier desvío de costumbre. Sólo entre las filas sin violaciones escritas se estudian costumbres. El resultado derivado fue **1.600 correctas, 240 errores y 160 ruidos**. `historial_clasificado.csv` tiene exactamente las columnas `id,tipo` y los 2.000 IDs únicos en el orden original. La justificación por fila está en `datos/clasificacion_detalle.jsonl`.

Ejemplo: `H-0010` consignó 10 minutos para ECG, cuando la combinación de NOR-TDE-01 y NOR-TDE-04 exige 5 por llegada en ambulancia. No se inventaron tiempos de atención ni eventos posteriores que el CSV no describe. Si hay circuitos simultáneos o datos no reconocidos, el proceso se detiene para revisión.

## Costumbres y evidencia

Se exploraron dos hipótesis en las 1.760 filas sin violaciones escritas:

- Avisar al voluntariado si el paciente tiene al menos 75 años y no tiene acompañante. El umbral se obtuvo comparando todas las edades observadas y la siguiente. Coincide en 1.609 de 1.760 filas; nunca avisar coincidiría en 1.461. En el grupo que debe recibir aviso coinciden 167 de 186; en el resto, 1.442 de 1.574. El umbral alternativo de 76 coincide en 1.599.
- Preferir la prepaga ante doble credencial de obra social y prepaga, fuera de accidentes laborales: 163 de 172 filas. Se observa la entidad verificada y no sólo la cobertura final, porque una afiliación inactiva o reservada cambia esa cobertura. La ART sigue teniendo prioridad por norma.

Se exige como criterio de apoyo al menos 20 ejemplos y 80% de coincidencia en cada grupo. `costumbres.md` contiene explicación y ejemplos; `datos/evidencia_costumbres.json` conserva todos los IDs de apoyo y contraejemplos. Las etiquetas son inferidas y no disponemos de etiquetas oficiales para medir su exactitud. Estos porcentajes no son una evaluación independiente: las hipótesis se eligieron explorando el mismo historial.

## Conversaciones y selección

Se seleccionaron las 1.600 trazas históricas clasificadas como correctas y las 800 trazas de referencia: **2.400 conversaciones**. Se excluyeron 240 errores y 160 ruidos; no se sustituyeron por respuestas inventadas y no se incorporaron datos sintéticos de entrenamiento. Los ejemplos artificiales de pruebas se usan sólo para probar el código.

El protocolo conserva sistema, pedido inicial, llamadas JSON del asistente y resultados como mensajes del usuario. La última intervención es `registrar_decision`, sin observación posterior. Se preservan argumentos, resultados, orden de herramientas y normas con sus valores específicos de cada traza. El prompt provisional es el del ejemplo de la cátedra y se puede reemplazar desde un archivo UTF-8 con `--prompt`.

Cada registro conserva ID de origen, archivo/fuente, paciente, huella de la traza y grupo. Los metadatos quedan fuera de `messages`. El manifiesto identifica selección, exclusiones, fuentes, código, prompt y salidas. Las conversaciones actuales tienen entre 7.474 y 15.186 caracteres de contenido; todavía no se midieron tokens con el modelo elegido.

## Particiones reproducibles

Se usó semilla 42 y objetivo de 10% para validación. Se construyen grupos por identificador de paciente y huella de conversación, incluyendo vínculos transitivos. La huella elimina diferencias de ID/nombre y conserva documentos y números normativos. Un SHA-256 de la semilla y el grupo asigna el grupo completo a una partición.

El resultado actual es **2.176 para entrenamiento** (1.448 del historial y 728 de referencia) y **224 para validación** (152 del historial y 72 de referencia). No hay IDs, pacientes, huellas ni grupos compartidos entre particiones; tampoco copias adicionales por huella entre estas fuentes. La fracción real difiere levemente del objetivo porque los grupos no se dividen.

La validación es interna para el trabajo de entrenamiento, no el test secreto ni un benchmark independiente del método de curado. Las proporciones y el esquema deben acordarse con Juan y Juli antes de comenzar. Juli verificará la plantilla de chat, tokenización, longitudes y compatibilidad con su cargador y modelo.

## Reproducción y comprobaciones

Desde la raíz del repositorio:

```powershell
uv run --locked python -X utf8 -m datos.preparar
uv run --locked python -X utf8 -m datos.verificar
uv run --locked python -X utf8 -m unittest discover -s tests -p "test_*_datos.py" -v
```

El verificador contrasta huellas de fuentes y código, selección y mensajes con las trazas originales y reparto con la semilla/grupos registrados. Las huellas de fuentes y código normalizan CRLF a LF para permitir Windows y Linux. Las de conversaciones y prompt identifican bytes exactos; `.gitattributes` evita alteraciones de esos entregables durante el checkout.

Las pruebas cubren corrupción de fuentes, campos opcionales, órdenes, precedencias normativas, casos límite, inferencias ambiguas, formato de chat, ausencia de respuesta posterior al cierre, agrupación transitiva, reparto estable y huellas entre sistemas. No se ejecutó entrenamiento, no se midió desempeño de un modelo y no se consumió GPU para preparar estos datos.

## Trabajo que depende del grupo

Falta incorporar el prompt que Juan optimice, confirmar formato y particiones con Juan/Juli, y verificar carga/tokenización con el modelo de Juli. Con el checkpoint final y `entrega.py`, se ejecutarán dos casos de demo sobre normas `b` o `c`, mostrando herramientas, búsquedas, ficha y los nueve controles. Los resultados de esa demo y la intervención en Loom se agregarán cuando se realicen; no se presentan como completados.
