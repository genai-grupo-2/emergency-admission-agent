# Demo de Cande — pendiente del modelo final

La preparación de datos está disponible en esta rama. La demo todavía no se ejecutó: requiere el checkpoint final publicado por Juli y la versión de `entrega.py` integrada por Juan/Pía. No hay resultados de modelo ni nueve controles aprobados para reportar aún.

## Qué vamos a mostrar

1. **Un caso con circuito tiempo-dependiente**, sobre las normas `b` o `c`. Mostrar el triage, la búsqueda de la sección adecuada y el plazo obtenido de esa versión de las normas. Un ingreso en ambulancia permite mostrar también la reducción del plazo.
2. **Un caso cuya decisión usa una costumbre**, sobre la misma versión: por ejemplo, una persona de al menos 75 años sin acompañante, o una doble credencial de obra social/prepaga sin accidente laboral. Mostrar que la costumbre se aprendió del historial y que las reglas escritas siguen prevaleciendo.

Los casos concretos se elegirán y conservarán con su ID cuando se ejecute la entrega final; no se eligen fingiendo que ya los resolvió. Las expectativas y respuestas usadas para puntuar no se pasan al agente ni se agregan al conjunto de entrenamiento.

## Ensayo con la entrega final

Con el modelo final configurado en `entrega.py` y el acceso de Hugging Face preparado, el comando del kit para la variante `b` es:

```powershell
uv run --locked python -X utf8 -m admision.correr practica --entrega entrega.py --casos practica/casos.jsonl --esperadas practica/esperadas-b.jsonl --normas normas/b --salida corridas/demo-b
```

Para la variante `c`, reemplazar las rutas por `practica/esperadas-c.jsonl`, `normas/c` y `corridas/demo-c`. La fase `practica` del kit separa jugar de puntuar; ejecutar este comando sólo cuando exista la entrega y el grupo acuerde el ensayo en la A100 de 40 GB. Este documento no ejecuta el comando ni crea una corrida de GPU.

## Qué guardar antes de grabar

- Commit exacto de la entrega, revisión del modelo de Hugging Face, prompt, versión de normas y comando.
- IDs de los dos casos elegidos y conversaciones completas en `trazas.jsonl`.
- Resultados reales de los ocho campos y la verificación de afiliación, los nueve controles por caso.
- Tiempos, búsquedas y contexto de la corrida, separando lo medido de cualquier estimación.
- Explicación breve de por qué corresponde el circuito del primer caso y qué evidencia respalda la costumbre del segundo.

Si un caso falla un control, se muestra el fallo o se corrige y se repite con evidencia; no se informa como resuelto. Con esos archivos se termina la sección de demo del informe y se prepara la parte de Cande para el Loom grupal.
