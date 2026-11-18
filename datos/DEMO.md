# Demo de Cande — pendiente del modelo final

La demo todavía no se ejecutó. Se puede ensayar con el checkpoint ya publicado de Juli (#4), pisando el modelo con
variables de entorno (ver «Ensayo corto» más abajo). La versión final usa el que quede fijado en `configuracion.json`. No hay
resultados de modelo entrenado ni nueve controles aprobados para reportar. Lo que sí está listo es la selección de
candidatos, los comandos y el guion.

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

## Qué guardar antes de grabar

- Commit de la entrega, revisión del modelo en Hugging Face, prompt, versión de normas y comando.
- IDs de los dos casos elegidos y sus conversaciones completas en `trazas.jsonl`.
- Los ocho campos de la ficha, la verificación de afiliación y los nueve controles de cada caso.
- Tiempos, búsquedas y contexto de la corrida, separando lo medido de lo estimado.

Si un caso falla un control, se muestra el fallo o se corrige y se repite con evidencia; no se informa como resuelto.

## Guion de la parte de datos en el Loom

Unos tres minutos, con el repositorio abierto:

1. **Historial** (`historial_clasificado.csv`). Norma escrita primero y costumbre después: 1.600 correctas, 240 errores
   y 160 ruidos. Mostrar `H-0010` en `datos/clasificacion_detalle.jsonl`: 10 minutos de ECG cuando por ambulancia
   correspondían 5.
2. **Costumbres** (`costumbres.md`). Voluntariado desde los 75 años sin acompañante (1.609 de 1.760, contra 1.599 con
   76 años) y prepaga ante doble credencial (163 de 172). Decir el límite: se infirieron del mismo historial.
3. **Conversaciones** (`datos/manifiesto.json`). 2.400 conversaciones con el prompt de la cátedra, 2.176 y 224 sin
   pacientes compartidos; `python -m datos.verificar` las reproduce.
4. **Demo.** Los dos casos elegidos, con herramientas, búsquedas, ficha y los nueve controles.
