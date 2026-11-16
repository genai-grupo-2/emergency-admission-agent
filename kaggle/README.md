# Correr en Kaggle (2×T4, sin tarjeta)

Modal no habilita ninguna GPU sin una tarjeta cargada. Kaggle da 2×T4 de 16 GB gratis (con el teléfono verificado),
y con eso se corren la optimización del prompt y las evaluaciones del modelo sin entrenar. El notebook
[`correr.ipynb`](correr.ipynb) clona la rama, instala las mismas versiones que `modal_app.py` y llama a
[`correr_kaggle.py`](../correr_kaggle.py).

## Una sola vez

1. Cuenta de Kaggle con el teléfono verificado (*Settings* → *Phone verification*). Sin eso no hay GPU ni internet.
2. *Create* → *New Notebook* → *File* → *Import Notebook* → subir `kaggle/correr.ipynb`.
3. *Settings* del notebook: Accelerator **GPU T4 x2** e Internet **on**.
4. *Add-ons* → *Secrets* → un secreto `HF_TOKEN` con un token de lectura de Hugging Face, con la licencia de Gemma
   aceptada. Tildarlo para este notebook.

## Cada corrida

1. En la celda de parámetros, poner el `COMANDO` (los mismos que van después de `--comando` en `modal_app.py`).
2. Las cortas, con *Run All*. Las largas (la búsqueda, la matriz), con *Save Version* → *Save & Run All*: siguen
   corriendo con el navegador cerrado, hasta 12 horas por sesión.
3. Bajar `corridas-kaggle-<fecha>.zip` del panel *Output*, descomprimirlo en la raíz del repo y commitear la carpeta
   de la corrida junto con su `corridas/entornos/kaggle-<fecha>.json`.

Si da `CUDA out of memory`, bajar `LOTE` (por ejemplo a 16) y volver a correr con otro `--nombre` o `--etiqueta`.

## Qué cambia respecto de la A100

- Los pesos se reparten entre las dos T4 (`ADMISION_DEVICE_MAP=auto`) porque Gemma 4 E4B en bf16 no entra en una.
- La T4 no tiene bf16 nativo: es más lenta y la generación en lote puede mover algún caso respecto de la A100.
- Por eso cada corrida deja en `corridas/entornos/` las GPU, el driver, las versiones de torch y transformers, el
  commit, las variables y cuánto tardó. Los tiempos no sirven para la Parte 5, que pide la A100 de 40 GB.
