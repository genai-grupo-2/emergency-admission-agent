# Entrenamiento (issue #4)

SFT con LoRA de Gemma 4 E4B sobre las conversaciones de `datos/conversaciones/`, con el prompt de la cátedra
(`prompts/catedra.txt`; el optimizado no se usa, ver `INFORME.md` Parte 3). Se corre en Kaggle 2×T4 con la misma
infraestructura que Juan armó para las evaluaciones (`kaggle/`, `correr_kaggle.py`). Modal no habilita GPU sin tarjeta.

## Qué se entrena y cómo

| | |
|---|---|
| Modelo base | `google/gemma-4-E4B-it` @ `4ecc2ba63bca…` (el mismo que `configuracion.json`) |
| Método | LoRA r=16, alpha=32, sólo en las proyecciones del modelo de lenguaje; pesos base en bf16 repartidos entre las 2 GPU |
| Datos | `datos/conversaciones/train.jsonl` (2.176) y `validacion.jsonl` (224); su sha256 queda en el manifiesto |
| Pérdida | sólo sobre las respuestas del asistente (herramienta + argumentos + cierre del turno) |
| Pasos | 16 conversaciones por paso del optimizador, 2 épocas = 272 pasos; lr 2e-4 con calentamiento y coseno; semilla 42 |
| Selección | menor pérdida en **validación**. Nunca el test secreto ni los casos de práctica |
| Salida | adaptador por checkpoint; se publican los pesos fusionados en bf16 (los que carga `entrega.py`) |

Antes de gastar GPU, `entrenar/datos.py` comprueba que el mensaje de sistema de cada conversación es exactamente el prompt de
la configuración, que train y validación no comparten ids, grupos ni huellas, y que ninguna conversación reproduce un caso de
práctica. Los ids de paciente (`P-xxxx`) que coinciden con los de la práctica en 11 conversaciones son casualidad: son otros
pacientes (otra edad y motivo).

## Pasos

```bash
# 0) Sin GPU, en cualquier máquina: valida datos y prompt
python -m entrenar.entrenar --config entrenar/configs/sft-catedra.json --solo-datos

# 1) En Kaggle (notebook kaggle/entrenar.ipynb, ver kaggle/README.md): primero el ensayo, después la corrida real
python correr_kaggle.py --comando "entrenar.entrenar --config entrenar/configs/sft-catedra.json --ensayo --checkpoints /kaggle/working/checkpoints/sft-catedra-01-ensayo"
python correr_kaggle.py --comando "entrenar.entrenar --config entrenar/configs/sft-catedra.json --checkpoints /kaggle/working/checkpoints/sft-catedra-01"

# 2) Si la sesión se corta (el límite de Kaggle es de unas 12 h; max_horas=10.5 guarda un checkpoint antes y sale ordenado)
python correr_kaggle.py --comando "entrenar.entrenar --config entrenar/configs/sft-catedra.json --reanudar --checkpoints /kaggle/working/checkpoints/sft-catedra-01"

# 3) Publicar el checkpoint con menor pérdida de validación (la revisión queda en el manifiesto y se le pasa a Juan, Pía y Cande)
python -m entrenar.publicar --nombre sft-catedra-01 --paso <N> --repo <usuario-o-org>/<repo> --checkpoints /kaggle/working/checkpoints/sft-catedra-01

# 4) Desde un entorno limpio, sin reentrenar
python -m entrenar.verificar_carga --repo <usuario-o-org>/<repo> --revision <hash>
ADMISION_MODELO_REPO=<repo> ADMISION_MODELO_REVISION=<hash> python -m evaluacion.evaluar --etiqueta solo-entrenamiento --prompt catedra
```

Para reanudar en una sesión nueva hay que tener el manifiesto de la corrida (`corridas/entrenamiento/<nombre>/`, commiteado
después de la sesión anterior) y poner `subir_checkpoints_a` en la configuración: cada checkpoint se copia a ese repo privado
de Hugging Face y `--reanudar` baja el último. El orden de las conversaciones sale de la semilla y del número de paso, así
que retomar da los mismos lotes que seguir de largo (lo único que no es idéntico bit a bit es el dropout de LoRA).

## Accesos del grupo

- Hugging Face (privado): `genai-grupo-2/emergency-admission-agent` (`subir_checkpoints_a` en la configuración).
- W&B: entidad `gen-ai-grupo-2`, proyecto `emergency-admission-agent`, en el servidor del grupo
  `https://forge.coreweave.com/wandb/gen-ai-grupo-2/emergency-admission-agent`, **no** en wandb.ai: el notebook
  fija `WANDB_BASE_URL=https://forge.coreweave.com/wandb` y la clave se saca de ese mismo servidor.

## Qué queda registrado

- `corridas/entrenamiento/<nombre>/manifiesto.json`: datos (archivo y sha256), prompt (sha256), configuración completa,
  semilla, commit, versiones, GPU, parámetros entrenables, plan de pasos, cada checkpoint con sus pérdidas y su revisión
  en Hugging Face, la corrida de W&B y VRAM pico. **También las corridas que fallan o se pausan**, con el error.
- W&B (proyecto `emergency-admission-agent`): pérdida de entrenamiento y validación, lr, norma del gradiente, tokens/s y VRAM.
  `--sin-wandb` sólo existe para el ensayo local.
- Hugging Face (repo privado): pesos fusionados + `adaptador/` + `ENTRENAMIENTO.json` con la procedencia.

## Límites que hay que decir en el informe

- Kaggle 2×T4 no es la A100 de 40 GB que pide `mission.md`. Los tiempos, la VRAM y el costo medidos acá **no** sirven para la
  Parte 5; hace falta una medición en A100 para eso. bf16 en T4 es emulado: es más lento y puede mover algún caso.
- Las dependencias de entrenamiento (`peft==0.21.3`) se instalan en el notebook, igual que torch y transformers en el de
  Juan, y no están en `pyproject.toml`/`uv.lock` (cambiarlo rompería el `uv sync --locked` de los demás notebooks).
- **Qué se probó y qué no.** Probado en CPU con un Gemma 4 diminuto de pesos al azar (la clase `Gemma4ForConditionalGeneration`
  y el tokenizador reales, con `torch==2.14.1`, `transformers==5.20.2`, `peft==0.21.3`): LoRA se engancha a los módulos del
  modelo de lenguaje con la expresión de `lora.modulos`, la pérdida con `logits_to_keep` y los `token_type_ids` en cero
  funciona, la pausa por `max_horas` y `--reanudar` continúan con el mismo calendario, el manifiesto de una corrida fallida
  queda escrito, y `entrenar.publicar` (con un cliente de Hugging Face falso) arma una carpeta que `agente/modelo.py`
  recarga. **No se probó con el modelo de 4.000 millones de parámetros**: no se sabe si entra en 2×T4 con 4.192 tokens de
  contexto (el máximo del conjunto). El ensayo con `--ensayo` en Kaggle lo comprueba; si da `CUDA out of memory`, usar
  `"cuantizacion": "nf4"` (necesita `bitsandbytes`). Tampoco se subió nada a Hugging Face ni a W&B.
- Arrancar tarda unos 7 minutos antes de la primera GPU: tokenizar las 2.400 conversaciones con la plantilla de chat
  (dos tokenizaciones por turno del asistente, para fijar la máscara). Es CPU y se repite en cada sesión.
- La plantilla de chat de Gemma 4 es prefijo-estable en las 2.400 conversaciones (se comprobó con el tokenizador real): los
  tokens supervisados son exactamente el JSON de cada respuesta más `<turn|>` y el salto de línea (11,7 % de los tokens).
- La fila «ambos» de la matriz necesita un segundo checkpoint entrenado con el prompt optimizado. Juan dijo que se define
  aparte y que no frena este entrenamiento; las conversaciones de Cande no cambian de prompt sin regenerarlas.
