# Integración del buscador y el agente — Pía, ítem 5

## Código incorporado

Se tomaron de `juan/agente-prompt`, commit
`43c9e24e1427794cf90c159a08e91678998368c6`, los archivos de ejecución
`agente/`, `entrega.py`, `configuracion.json`, `prompts/catedra.txt` y las
pruebas `tests/test_agente_ciclo.py`. El agente y esas pruebas son trabajo
de Juan. No se incorporaron sus módulos de optimización, evaluación ni Modal:
siguen en su rama y conservan a Juan como responsable de esas tareas.

Pía conectó el buscador evaluado en `entrega.py`, agregó su configuración
explícita y las pruebas conjuntas `tests/test_entrega_buscador.py`.
No se modificó el entorno del kit `admision/`.

## Interfaz y configuración

`construir_buscador(ruta_normas)` pasa la carpeta y la configuración al
`BuscadorBM25` de Pía. El agente usa `buscar_normativa` del entorno, que llama
a `recuperar(consulta, k_entorno)` y entrega el texto de los fragmentos al modelo.

La configuración provisional conserva secciones completas y k=2:

```json
"buscador": {
  "k_entorno": 2,
  "fragmentacion": "seccion",
  "k1": 1.5,
  "b": 0.75
}
```

Para comparar otra configuración, copiar `configuracion.json`, cambiar el
bloque y señalar el archivo con `ADMISION_CONFIG`. Las alternativas medidas
están en `resultados/rag/ANALISIS.md`; el desempeño del agente todavía debe
decidir si conviene cambiar el valor por defecto.

`construir_agente()` carga el modelo una vez y devuelve el agente por lotes de
Juan. Los módulos se pueden importar sin torch; la carga del backend real
sí requiere las dependencias de inferencia y acceso al modelo.

Las variables activas se llaman `ADMISION_MODELO_REPO` y
`ADMISION_MODELO_REVISION`; reemplazan la propuesta anterior `MODEL_ID` y
`MODEL_REVISION`. `.env.example` refleja los nombres que consume el código.
El archivo `.env` no se carga automáticamente.

## Verificación sin GPU

Desde la raíz del repositorio, con el entorno instalado:

```powershell
uv run --locked python -m unittest discover -s tests -p "test_entrega_buscador.py" -v
uv run --locked python -m unittest discover -s tests -p "test_agente_ciclo.py" -v
```

La prueba conjunta usa el modelo simulado de Juan de manera explícita y
recorre las cinco herramientas con el buscador y el entorno reales:
leer_triage, preguntar, verificar_afiliacion, buscar_normativa y registrar_decision.
Lo hace sobre dos casos en cada variante original/b/c, sin usar sus fichas
esperadas. Comprueba una carga de modelo por construcción del agente, orden
de casos, mensajes de entrada/salida y observaciones completas, ficha registrada
y persistencia exacta en trazas.jsonl. También comprueba que las opciones del
RAG lleguen desde configuración al constructor.

Las fichas de ese modelo son guionadas y **no son resultados de calidad**;
no se publican porcentajes de acierto con ellas. La evaluación de 50 casos
con modelo real corresponde al ítem 6 y todavía no se realizó.

## Pendiente para correr con el modelo real

- Acordar modelo y revisión final, permisos y credenciales con el grupo.
- La configuración de modelo incluida se heredó de Juan; no constituye una
  elección confirmada del grupo ni una descarga/verificación de ese checkpoint.
- Fijar las versiones de inferencia con Juan/Juli y usarlas también en Modal.
- Correr en A100 de 40 GB con el backend real y guardar trazas/tiempos/resultados.

El backend `falso` solo se selecciona explícitamente para pruebas; el código
no sustituye silenciosamente un modelo real por el simulado si falla la carga.
Esta documentación es el traspaso técnico para Juan; no se envió un mensaje
al compañero ni se integró su rama entera.
