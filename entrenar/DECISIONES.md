# Decisiones del entrenamiento (issue #4)

Registro de lo que se decidió, por qué y qué consecuencia tiene para los resultados. Las cifras salen de
`corridas/entrenamiento/sft-catedra-01/manifiesto.json` salvo que se diga otra cosa.

## 1. Prompt de entrenamiento: el de la cátedra
Juan primero congeló `prompts/optimizado.txt` y después corrigió: en validación rinde peor que el de la cátedra
(2/20, 1/20 y 1/20 contra 7/20, 5/20 y 5/20; ver Parte 3 del informe). Se entrena con `prompts/catedra.txt`, el mismo que
tienen las conversaciones de Cande. `entrenar/datos.py` comprueba que el mensaje de sistema de cada conversación es
exactamente ese prompt. **Consecuencia:** la fila «ambos» de la matriz (checkpoint entrenado con el prompt optimizado) no
existe. Juan dijo que se resuelve aparte y no frena este entrenamiento.

## 2. Dónde se entrena: Kaggle 2×T4, no la A100 de 40 GB
Modal no habilita ninguna GPU sin tarjeta, y el grupo no la tiene cargada. Se usó la infraestructura que armó Juan
(`kaggle/correr.ipynb`, `correr_kaggle.py`), con una cuenta con teléfono verificado (30 horas de GPU por semana, sesiones de
hasta 12 h). **Consecuencia:** los tiempos, la VRAM y el costo medidos acá **no** sirven para la Parte 5, que pide A100.
bf16 en T4 es emulado: más lento y puede mover algún caso. Hay que decirlo en el informe.

## 3. Método: LoRA, pesos base en bf16 repartidos entre las dos GPU
LoRA r=16, alpha=32, dropout 0,05, sólo en las proyecciones del modelo de lenguaje (la expresión está en la configuración).
Sin cuantizar: el modelo en bf16 repartido con `device_map="auto"` ocupa unos 12 GiB por GPU (pico medido 12,4 GiB de 15) con
contextos de hasta 4.192 tokens, así que no hizo falta `nf4`. La pérdida se calcula sólo sobre las respuestas del
asistente (11,6 % de los tokens: 221.222 de 1.898.838 en train). Como las dos T4 trabajan una a la vez, la velocidad es
la de una sola.

## 4. Tamaño de la corrida: submuestra y una época
- **Plan original:** 2.176 conversaciones, 2 épocas, 272 pasos de 16 conversaciones, unos 13 M de tokens.
- **Medición:** en el ensayo y en la corrida real, 72–74 tokens/s y unos 336 s por paso de 8 conversaciones. El plan original
  habría tardado ~50 h, contra 12 h por sesión y 30 h de cuota semanal, con el 20/11 como plazo y la matriz de Juan sin correr.
- **Corrida real:** 640 conversaciones de train y 40 de validación, elegidas al azar con la semilla 42 (los índices quedan en
  el manifiesto), 1 época, 8 conversaciones por paso = 80 pasos, calentamiento de 5 pasos, lr 2e-4 con coseno,
  validación y checkpoint cada 20 pasos. Duró 7 h 55 min (28.518 s). Se usaron ~8,5 de las 30 horas semanales.
- **Qué se pierde:** 70 % de las conversaciones y la segunda pasada. La pérdida de validación llegó a 0,0042 y seguía
  bajando en el último paso, o sea que el formato de las herramientas se aprendió, pero no se sabe cuánta exactitud se deja
  frente a una corrida completa. Lo dirá la matriz.
- **Si hubiera más tiempo o cuota:** una segunda corrida con otras 640 conversaciones (otro nombre, otra publicación), o una
  A100 donde todo entra en una hora aproximadamente. No se hizo.

## 5. Selección del checkpoint: menor pérdida de validación
Validación (0,0310 en el paso 20; 0,0093 en el 40; 0,0053 en el 60; 0,0042 en el 80). Se publicó el paso 80. Nunca
intervienen el test secreto ni los 50 casos de práctica. La validación es de 40 conversaciones (de 224), también al azar.

## 6. Qué se publica: pesos fusionados
`entrega.py` carga el modelo con `ADMISION_MODELO_REPO` y `ADMISION_MODELO_REVISION` en una sola carga, así que se
publican los pesos completos fusionados en bf16 (más `adaptador/` y `ENTRENAMIENTO.json` con la procedencia), en el repo
privado `genai-grupo-2/emergency-admission-agent`, revisión `292c8137984283d426de735309d108459b5e51f9`. Fusionar redondea
a bf16 (en pruebas con un modelo diminuto, diferencia máxima de logits 0,027), por eso lo evaluado es el modelo fusionado.
Los adaptadores de cada paso están en `adaptadores/sft-catedra-01/paso-000NN/` del mismo repo (usados para reanudar).

## 7. Corridas que no salieron (todas quedan en W&B)
- **Ensayo 1 y 2** (`sft-catedra-01-ensayo`, con el mismo nombre): fallaron con `RuntimeError: indices should be either on
  cpu or on the same device as the indexed tensor (cuda:1)`. Al repartir el modelo entre dos GPU, el cálculo de logits
  sólo de las posiciones con pérdida (`logits_to_keep`) indexaba un tensor de `cuda:1` con un índice en `cuda:0`: los hooks
  de accelerate mueven los tensores de entrada a la primera GPU. El primer arreglo (índice en CPU) no sirvió; el segundo
  (índice como lista de enteros, con respaldo a logits completos) sí. Con commit `97efbde` no hizo falta el respaldo.
- **Ensayo 3** (OK, run `gw58nvt6`): 4 pasos, comprobó memoria y flujo. Pérdida de validación 0,298 → 0,208.
- El plan de 2 épocas sobre todo el conjunto se descartó antes de lanzarlo (sección 4).
Los manifiestos de los ensayos fallidos estaban en la sesión de Kaggle y no se bajaron; lo que queda es el registro en W&B y
este texto. Las corridas de la entrega son sólo `sft-catedra-01`.

## 8. Cosas pendientes o a vigilar
- **Particiones de Cande:** confirmadas como finales (PR #10); `datos/manifiesto.json` dice «final» desde el 18/11/2026.
- **Repositorio público:** `mission.md` pide GitHub privado con acceso para la cátedra; se decidió dejarlo público. En él
  no hay credenciales ni pesos (los checkpoints están en `.gitignore`); Hugging Face y W&B sí son privados.
- **Verificación de carga limpia:** hecha en 2×T4 (una sola carga, JSON válido; `corridas/entrenamiento/verificacion-292c8137984.json`).
  Falta en la A100 de 40 GB de la consigna, que el grupo no tiene.
- **Parte 5 en A100:** requiere una medición aparte (Modal con tarjeta o la cátedra); estas corridas no la reemplazan.
