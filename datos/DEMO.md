# Demo de Cande

La demo se corrió el 18/11/2026 con el checkpoint `sft-catedra-01` (`genai-grupo-2/emergency-admission-agent` @
`292c8137984283d426de735309d108459b5e51f9`), el mismo que fija `configuracion.json` en `main`. Resultados y casos
elegidos: «Resultado» más abajo.

## Qué vamos a mostrar

1. **Un caso con circuito tiempo-dependiente**, sobre las normas `b` o `c`: el triage, la búsqueda de la sección y el
   plazo que sale de esa versión de las normas. Si llegó en ambulancia, también la reducción del plazo.
2. **Un caso que se decide por una costumbre**, sobre la misma versión: una persona de al menos 75 años sin
   acompañante, o una doble credencial de obra social y prepaga sin accidente laboral.

## Candidatos

```powershell
uv run --locked python -X utf8 -m datos.candidatos_demo
```

Genera `datos/candidatos_demo.json` mirando sólo `practica/casos.jsonl`. No lee las respuestas esperadas ni corridas
de ningún modelo, y esos casos no están en el entrenamiento. De los 50 casos:

- **35 activan un circuito.** Ocho llegan en ambulancia: `pev-007`, `pev-008`, `pev-011`, `pev-013`, `pev-016`,
  `pev-021`, `pev-026` y `pev-028`.
- **17 tocan una costumbre.** En seis no hay circuito, así que la costumbre es lo que distingue el caso: `pev-015`,
  `pev-025`, `pev-041`, `pev-042` y `pev-043` (voluntariado) y `pev-050` (doble credencial).

Cuál de ellos se muestra se decide con la corrida del modelo final, no antes.

## Por qué `b` o `c`

Los plazos cambian entre versiones, así que una respuesta memorizada de las normas originales falla:

| Parámetro | original | b | c |
| --- | --- | --- | --- |
| P-TDE-1 · ECG (min) | 10 | 15 | 20 |
| P-TDE-2 · Código ACV (min) | 10 | 20 | 15 |
| P-TDE-3 · sepsis probable o con shock (min) | 15 | 30 | 20 |
| P-TDE-4 · sepsis posible sin shock (min) | 60 | 45 | 90 |
| P-TDE-5 · reducción por ambulancia (min) | 5 | 3 | 6 |

Un dolor torácico en ambulancia da 5 minutos con las originales, 12 con `b` y 14 con `c`. Las costumbres no dependen
de ningún parámetro: el umbral de 75 años sale del historial (`costumbres.md`).

## Ensayo con la entrega final

Con el modelo final configurado y el acceso de Hugging Face preparado:

```powershell
uv run --locked python -X utf8 -m admision.correr practica --entrega entrega.py --casos practica/casos.jsonl --esperadas practica/esperadas-b.jsonl --normas normas/b --salida corridas/demo-b
```

Para `c`, reemplazar por `practica/esperadas-c.jsonl`, `normas/c` y `corridas/demo-c`. Ejecutarlo sólo cuando exista
la entrega y el grupo acuerde el ensayo en la GPU.

### Ensayo corto con el checkpoint publicado (sin esperar el merge)

Para no repetir la matriz, la demo juega sólo 14 casos: los tiempo-dependientes que llegan en ambulancia y los de
costumbre sin circuito. Salen de `candidatos_demo.json` y no se mira ninguna respuesta esperada:

```powershell
uv run --locked python -X utf8 -m datos.casos_demo
```

Escribe `datos/demo/casos.jsonl` con `pev-007`, `pev-008`, `pev-011`, `pev-013`, `pev-015`, `pev-016`, `pev-021`,
`pev-025`, `pev-026`, `pev-028`, `pev-041`, `pev-042`, `pev-043` y `pev-050`. El circuito completo ya se probó con el
modelo falso (`ADMISION_BACKEND=falso`).

En Kaggle (2×T4, ver [kaggle/README.md](../kaggle/README.md)), con `kaggle/correr.ipynb` y estos parámetros:

```python
RAMA = "cande/demo-y-diagrama"
COMMIT = ""  # vacío: la punta de la rama
COMANDO = ("admision.correr practica --entrega entrega.py --casos datos/demo/casos.jsonl "
           "--esperadas practica/esperadas-b.jsonl --normas normas/b --salida corridas/demo/b-sft-catedra-01")
LOTE = ""
import os
os.environ["ADMISION_MODELO_REPO"] = "genai-grupo-2/emergency-admission-agent"
os.environ["ADMISION_MODELO_REVISION"] = "292c8137984283d426de735309d108459b5e51f9"
os.environ["ADMISION_DEVICE_MAP"] = "auto"
```

El secreto `HF_TOKEN` tiene que tener acceso al repo privado del grupo. Cargar el modelo tarda unos 2 minutos. Al
terminar, bajar el zip de *Output*, descomprimirlo en la raíz y commitear `corridas/demo/` y su
`corridas/entornos/kaggle-<fecha>.json`. Es una corrida en T4 con el checkpoint `sft-catedra-01` (submuestra de 640
conversaciones). Si después cambia la entrega final, se repite con esa revisión.

## Resultado

Corrida `corridas/demo/b-sft-catedra-01/`, normas `b`, Kaggle 2×T4, commit `dfa9e78`, sin cambios sin commitear
(`corridas/entornos/kaggle-20261118-192810.json`). Cargar el modelo tardó 131 s y jugar los 14 casos, 1.266 s
(90 s por caso, en un solo lote). Son tiempos de T4, no sirven para la Parte 5.

**6 de 14 casos aprueban los 9 controles.** Por control: registro, documento, box, circuito, cobertura y verificación
1,00; plazo 0,93; entidad a notificar 0,86; aviso al voluntariado 0,57. No quedó ningún caso sin ficha.

| Caso | Tipo | Resultado | Qué falló (esperado / obtenido) |
| --- | --- | --- | --- |
| `pev-007` | Código ACV, ambulancia | 8/9 | entidad a notificar: ninguna / Obra Social Bermejo |
| `pev-008` | Código Sepsis, ambulancia, voluntariado | 7/9 | entidad: ninguna / Obra Social Fluvial; aviso al voluntariado: sí / no |
| `pev-011` | ECG, ambulancia | **9/9** | — |
| `pev-013` | Código Sepsis, ambulancia | **9/9** | — |
| `pev-015` | Voluntariado | 8/9 | aviso al voluntariado: sí / no |
| `pev-016` | ECG, ambulancia | **9/9** | — |
| `pev-021` | ECG, ambulancia | **9/9** | — |
| `pev-025` | Voluntariado | 8/9 | aviso al voluntariado: sí / no |
| `pev-026` | ECG, ambulancia | 8/9 | plazo: 12 / 15 (no restó la reducción por ambulancia) |
| `pev-028` | Código Sepsis, ambulancia | **9/9** | — |
| `pev-041` | Voluntariado | 8/9 | aviso al voluntariado: sí / no |
| `pev-042` | Voluntariado | 8/9 | aviso al voluntariado: sí / no |
| `pev-043` | Voluntariado | 8/9 | aviso al voluntariado: sí / no |
| `pev-050` | Doble credencial | **9/9** | — |

**Lo que muestra.** Los circuitos tiempo-dependientes salen bien: 5 de 8 completos, y el circuito es correcto en
los 8. El modelo busca la sección del circuito y la de ambulancia y calcula el plazo con los valores de `b`. La
costumbre de la doble credencial (verificar la prepaga) se aplicó. **La del voluntariado no se aplicó en ninguno de
los 6 casos que la requieren**: el modelo nunca marcó el aviso. Es el hallazgo principal de esta corrida y hay que
contarlo, no esconderlo.

### Casos elegidos

1. **Tiempo-dependiente: `pev-011`.** Dolor torácico, 74 años, llega en ambulancia y sin credencial. Busca
   `NOR-TDE-01` (ECG) y `NOR-TDE-04` (ambulancia) y registra **12 minutos**: 15 de `b` menos 3 por ambulancia. Con
   las normas originales serían 5. Pregunta la cobertura, revisa la terminación reservada (`NOR-COB-04`) y verifica
   Obra Social Fluvial (activa). 9/9.
2. **Costumbre: `pev-050`.** Palpitaciones, presenta Obra Social Fluvial y Prepaga Sierra, sin accidente laboral.
   Las normas no dicen cuál verificar. Siguiendo la costumbre del historial, verifica la **prepaga**, que está
   inactiva, y registra sin cobertura. 9/9.
3. **Si hay tiempo, un fallo: `pev-015`.** 82 años y sin acompañante: correspondía avisar al voluntariado y no lo
   hizo. Muestra el límite del modelo con la costumbre que menos aprendió.

Las conversaciones completas están en `corridas/demo/b-sft-catedra-01/trazas.jsonl` y los controles en
`resultados.jsonl`.

## Qué guardar antes de grabar

- Commit de la entrega, revisión del modelo en Hugging Face, prompt, versión de normas y comando.
- IDs de los dos casos elegidos y sus conversaciones completas en `trazas.jsonl`.
- Los ocho campos de la ficha, la verificación de afiliación y los nueve controles de cada caso.
- Tiempos, búsquedas y contexto de la corrida, separando lo medido de lo estimado.

Si un caso falla un control, se muestra el fallo o se corrige y se repite con evidencia; no se informa como resuelto.

## Guion de la parte de datos en el Loom

El orden del video está en [`LOOM.md`](../LOOM.md): ahí la demo (sección 2) va antes que el historial (sección 3). Acá queda el detalle.

Unos cuatro minutos, con el repositorio abierto:

1. **Historial** (`historial_clasificado.csv`). Norma escrita primero y costumbre después: 1.600 correctas, 240 errores
   y 160 ruidos. Mostrar `H-0010` en `datos/clasificacion_detalle.jsonl`: 10 minutos de ECG cuando por ambulancia
   correspondían 5.
2. **Costumbres** (`costumbres.md`). Voluntariado desde los 75 años sin acompañante (1.609 de 1.760, contra 1.599 con
   76 años) y prepaga ante doble credencial (163 de 172). Decir el límite: se infirieron del mismo historial.
3. **Conversaciones** (`datos/manifiesto.json`). 2.400 conversaciones con el prompt de la cátedra, 2.176 y 224 sin
   pacientes compartidos; `python -m datos.verificar` las reproduce.
4. **Demo (~1,5 min).** Abrir los archivos legibles de `datos/demo/` (los genera `python -m datos.ver_demo` desde la
   corrida, sin volver a correr el modelo). Cada uno tiene la tabla de controles, un recorrido de un renglón por
   llamada a herramienta y abajo la conversación completa; en el video alcanza con la tabla y el recorrido. Decir
   primero el contexto: checkpoint `sft-catedra-01`, normas `b`, 14 casos elegidos, 6 aprueban los 9 controles.
   - [`pev-011.md`](demo/pev-011.md): dolor torácico en ambulancia. Señalar las dos búsquedas (`NOR-TDE-01` y
     `NOR-TDE-04`) y el plazo de 12 minutos: 15 de `b` menos 3 por ambulancia. Con las originales serían 5, así que
     no lo memorizó. Después la cobertura: pregunta, verifica Obra Social Fluvial y la notifica. 9/9.
   - [`pev-050.md`](demo/pev-050.md): presenta obra social y prepaga. Las normas no dicen cuál verificar; la costumbre
     del historial (163 de 172) dice la prepaga, y eso hace. Está inactiva, así que queda sin cobertura. 9/9.
   - [`pev-015.md`](demo/pev-015.md), si hay tiempo: 82 años y sin acompañante. Correspondía avisar al voluntariado y
     no lo hizo. Le pasó en los 6 casos con esa costumbre; sólo 53 de las 640 conversaciones de entrenamiento la
     tenían.
5. **Cierre (~15 s).** Lo que aprendió (circuitos, plazos de cada versión, doble credencial) y lo que no (el
   voluntariado), con el dato de cuántos ejemplos había.
