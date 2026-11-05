# Revisión de la base BM25 — Pía, ítem 2

Se incorporaron únicamente `buscador/__init__.py` y `buscador/bm25.py` de la
rama `juan/agente-prompt`, commit `43c9e24e1427794cf90c159a08e91678998368c6`.
El BM25 es trabajo de Juan y se conserva sin modificaciones como punto de
partida. El agente y `entrega.py` siguen en su rama; este cambio no los integra.

## Qué hace

- Usa `admision.normas.cargar_normas` para leer las 20 secciones y agregar los
  valores de `parametros.yaml` desde la carpeta recibida.
- Indexa una sección completa por fragmento, incluidas las de otras áreas.
- Normaliza mayúsculas y tildes y calcula BM25 sin dependencias adicionales.
- Devuelve objetos con `.texto`, ordenados por puntaje; desempata por orden
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
uv run --locked python -m unittest discover -s tests -p test_buscador_base.py -v
```

Las pruebas verifican el contrato en original/b/c, inclusión de distractores,
normalización de tildes, límites básicos de k, error sin secciones y lectura
de un parámetro cambiado en una carpeta temporal independiente del repositorio.
No requieren modelo, GPU ni credenciales.

## Pendientes para los ítems 3 y 4

- Definir el comportamiento de consulta vacía o sin coincidencias: la base
  devuelve las primeras secciones por empate, aunque su puntaje sea cero.
- Validar los argumentos: `k` negativo actualmente usa el recorte de Python
  y devuelve resultados; `k1`, `b` y `k_entorno` no tienen validación explícita.
- Comparar segmentación, normalización y cantidad de resultados según la
  evidencia recuperada y el contexto consumido, conservando los valores normativos.
- Ejecutar la evaluación formal de las 60 consultas y documentar métricas
  frente a la referencia. Las pruebas de compatibilidad no miden esa calidad.
- Coordinar con Juan la integración final y agregar el paquete del buscador
  al empaquetado si la entrega se distribuye como paquete instalado. Por ahora
  se importa desde el repositorio, como en su entrega provisional.

No se fijaron dependencias de inferencia ni se modificó `admision/`.
