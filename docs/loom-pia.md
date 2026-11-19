# Guion de la parte de Pía en el Loom

Unos cuatro minutos, con el repositorio abierto. Cubre el buscador (sección 4 de `mission.md`, junto con Juan, que
cuenta el prompt) y recursos y producción (sección 6, cierra el video). Los números salen de la Parte 2 y la Parte 5
de [INFORME.md](../INFORME.md).

## Buscador (~1,5 min)

1. **Qué es** (`buscador/bm25.py`). BM25 propio, sin dependencias, fuera de `admision/`. Lee las normas y los valores
   de la carpeta que recibe; ningún número está en el código. Una sección por fragmento y las 2 mejores (k=2).
2. **Cómo rinde, antes del agente** ([resultados/rag/INFORME.md](../resultados/rag/INFORME.md)). Mostrar la tabla:
   recall 0,817, 48 de 60 consultas completas y 617 tokens por búsqueda, contra 0,875, 51 y 580 de la referencia de la
   cátedra. Decir dónde falla: las consultas coloquiales (recall 0,25), cuando no se usan las palabras de la norma.
3. **Por qué k=2.** Con k=4 completa 57 de 60, pero duplica el contexto (1.269 tokens) y baja la precisión a 0,271.
   Ninguna alternativa se probó con el agente.

## Recursos y producción (~2,5 min)

1. **El límite primero.** No medimos en la A100: Modal pide tarjeta. Todo es Kaggle 2×T4, y lo de la A100 es una
   estimación con el precio de `mission.md` (2,10 USD/h).
2. **Medido** (tabla de la Parte 5). Entrenamiento: 7 h 55 min y 12,4 GiB por GPU. Inferencia con el modelo entrenado:
   84 s por caso, 10 casos a la vez (15 no entran en memoria), el modelo ocupa 15,1 GiB. Tarda casi el doble que el
   base porque busca casi tres veces más y resuelve 27 casos en lugar de 10. El desarrollo usó 25,4 h de GPU y costó 0 USD.
3. **Estimado para la A100.** Como máximo 0,049 USD por caso, al menos 43 casos por hora y unos 15–17 casos a la vez.
4. **Producción.** Mostrar la tabla de escenarios: con 100 admisiones por día conviene pagar por uso (~150 USD/mes);
   cerca de 1.000 por día cuesta lo mismo una A100 prendida todo el mes (~1.530 USD) y conviene agregar réplicas con una
   cola. Decir la salvedad: con poca demanda cada caso corre casi solo y cuesta más.
5. **Cierre: trabajos futuros (~30 s).** Medir en A100, servir con lotes continuos y caché de prefijos, achicar el
   contexto (párrafos) o cuantizar para que entren más casos, entrenar con todo el conjunto y mejorar las búsquedas
   coloquiales.
