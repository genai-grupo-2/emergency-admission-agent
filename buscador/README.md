# Buscador BM25 — Pía, ítems 2 y 3

Se incorporaron únicamente `buscador/__init__.py` y `buscador/bm25.py` de la
rama `juan/agente-prompt`, commit `43c9e24e1427794cf90c159a08e91678998368c6`.
El BM25 inicial es trabajo de Juan. Se incorporó sin modificaciones en el
commit `6203ca0` (ítem 2); el ítem 3 agrega las mejoras descritas abajo.
El agente y `entrega.py` siguen en su rama; este cambio no los integra.

## Qué hace

- Usa `admision.normas.cargar_normas` para leer las 20 secciones y agregar los
  valores de `parametros.yaml` desde la carpeta recibida.
- Indexa una sección completa por fragmento por defecto, incluidas las de otras
  áreas. `fragmentacion="parrafo"` habilita fragmentos más pequeños para comparar.
- Normaliza mayúsculas y tildes y calcula BM25 sin dependencias adicionales.
- Devuelve objetos con `.id`, `.seccion` y `.texto`, ordenados por puntaje; desempata por orden
  de sección. Expone `k_entorno=2`, `k1=1.5` y `b=0.75` por defecto.

La interfaz coincide con la que usa `construir_buscador` en la rama de Juan:

```python
from pathlib import Path
from buscador.bm25 import BuscadorBM25

buscador = BuscadorBM25(Path("normas/original"))
for seccion in buscador.recuperar("dolor torácico electrocardiograma", 2):
    print(seccion.texto)
```

## Verificación realizada

```powershell
uv run --locked python -m unittest discover -s tests -p "test_buscador*.py" -v
```

Las pruebas verifican el contrato en original/b/c, inclusión de distractores,
normalización de tildes, límites básicos de k, error sin secciones y lectura
de un parámetro cambiado en una carpeta temporal independiente del repositorio.
No requieren modelo, GPU ni credenciales.

## Mejoras del ítem 3

- Consultas vacías, con solo puntuación o sin coincidencias devuelven `[]`.
  Se excluyen los fragmentos de puntaje cero; la cantidad devuelta puede ser
  menor que k. El entorno ya interpreta una lista vacía como búsqueda sin resultado.
- `k` debe ser entero no negativo, `k_entorno` entero positivo, `k1` positivo
  finito y `b` finito entre 0 y 1; los booleanos no se aceptan como números.
  Consultas que no sean texto y configuraciones inválidas fallan explícitamente.
- El modo párrafo conserva el encabezado y el texto íntegro del párrafo,
  junto con todos los valores citados en su sección. Mantiene los parámetros
  de referencias cruzadas y la procedencia, sin truncar evidencia ni fijar números.
  Puede requerir más resultados para recuperar excepciones y precedencias que
  estén en otros párrafos; por eso sigue siendo opcional hasta medir calidad.
- Se calculan los puntajes una sola vez por fragmento y consulta.
- El paquete `buscador` se incluye en la instalación del proyecto.

Inspección sin modelo ni credenciales:

```powershell
uv run --locked python -m buscador --normas normas/b --consulta "dolor torácico electrocardiograma" --k 2
uv run --locked python -m buscador --normas normas/c --consulta "accidente de trabajo ART" --fragmentacion parrafo --k 3
```

Se pueden variar `k_entorno`, `k1`, `b` y `fragmentacion` al construir la clase.
La llamada existente de Juan sigue funcionando con secciones completas y k=2.
Las pruebas adicionales comprueban argumentos, ausencia de coincidencias,
procedencia y conservación de párrafos/valores en las tres variantes.

## Pendientes para la integración

- Coordinar con Juan la integración final y la configuración elegida a partir
  de las mediciones; no cambiar el valor por defecto antes de esa comparación.

No se fijaron dependencias de inferencia ni se modificó `admision/`.

## Evaluación realizada — ítem 4

```powershell
uv run --locked python -m buscador.evaluar --salida resultados/rag
uv run --locked python -m admision.evaluar_rag --entrega buscador/entrega_rag.py --normas normas/original --consultas rag/consultas_dev.jsonl
```

El primer comando compara ocho configuraciones (sección/párrafo con k=1–4),
usa las funciones del evaluador oficial y comprueba que la base sección/k=2
coincida exactamente con el segundo comando. Genera resumen, ranking con texto,
evidencia cubierta por fragmento, hashes de fuentes y tablas del informe.
`entrega_rag.py` es un adaptador exclusivo de evaluación, no la entrega del agente.

Resultados y análisis: [informe generado](../resultados/rag/INFORME.md) y
[análisis para el grupo](../resultados/rag/ANALISIS.md).
El ranking guarda hasta 20 fragmentos, que es el límite del evaluador con
presupuestos de 256/512/1024 tokens estimados; no representa conversaciones del agente.

La evidencia de algunas consultas numéricas solo coincide con `original`
(por ejemplo, d033 espera 67 años). El script detecta esa incompatibilidad y
registra las consultas afectadas de b/c sin puntuar ni cambiar sus esperadas.
La carga dinámica de b/c sigue cubierta por las pruebas del buscador.
