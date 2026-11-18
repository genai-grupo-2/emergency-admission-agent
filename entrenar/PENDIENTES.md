# Traspaso y pendientes del entrenamiento (issue #4)

Estado al 18/11/2026. Sirve para que cualquier persona del grupo, o un agente que abra el repo, sepa qué está hecho, qué
falta y quién lo tiene. Contexto completo: [`DECISIONES.md`](DECISIONES.md) y [`README.md`](README.md). Si algo de acá queda
viejo, actualizar este archivo en el mismo commit que lo cambia.

## Hecho
- Código de entrenamiento, manifiestos, publicación y verificación (`entrenar/`, `kaggle/entrenar.ipynb`,
  `kaggle/publicar.ipynb`, `kaggle/verificar.ipynb`), con pruebas en `tests/test_entrenar_*.py`.
- Corrida `sft-catedra-01` en Kaggle 2×T4: 640 conversaciones, 1 época, 80 pasos, 7 h 55 min. W&B run `1y5xd2de`.
  Manifiesto en `corridas/entrenamiento/sft-catedra-01/`.
- Checkpoint elegido por la pérdida de validación: **paso 80** (0,0042). Publicado, privado y fusionado en bf16.
- Verificación de carga desde una sesión limpia (una sola carga, JSON válido de `leer_triage`):
  `corridas/entrenamiento/verificacion-292c8137984.json`.

## Para usar el modelo (Juan, Pía, Cande)
```
ADMISION_MODELO_REPO=genai-grupo-2/emergency-admission-agent
ADMISION_MODELO_REVISION=292c8137984283d426de735309d108459b5e51f9
```
- Repo de Hugging Face **privado**; hace falta `HF_TOKEN` con acceso al grupo. W&B: entidad `gen-ai-grupo-2`, proyecto
  `emergency-admission-agent`, run `1y5xd2de`.
- En 2×T4 hay que repartir el modelo: `ADMISION_DEVICE_MAP=auto`. Cargarlo cuesta unos 2 minutos y ~15 GiB entre las dos GPU.
- Fila «solo entrenamiento» de la matriz:
  `ADMISION_MODELO_REPO=... ADMISION_MODELO_REVISION=... python -m evaluacion.evaluar --etiqueta solo-entrenamiento --prompt catedra`.
- Dos advertencias que tienen que figurar donde se usen los números: entrenó con una **submuestra** (640 de 2.176, una época,
  por la cuota de Kaggle) y en **T4, no en la A100 de 40 GB** de la consigna.

## Pendientes
| # | Qué | Quién | Notas |
|---|---|---|---|
| 1 | Avisar al grupo con el repo, la revisión y el run de W&B (texto arriba) | Juli | Juan, Pía y Cande dependen de esto. Hecho cuando respondan. |
| 2 | Matriz: correr la fila «solo entrenamiento» con esta revisión y regenerar `INFORME.md` con `python -m evaluacion.tablas` | Juan | **En curso.** La revisión ya está en `evaluacion/matriz.json`; se corre en Kaggle con `evaluacion.matriz --correr 'solo entrenamiento'` (rama `juan/cierre-matriz`), que escribe `corridas/eval/matriz-solo-entrenamiento`. |
| 3 | Revisar `entrega.py` y `configuracion.json` con la revisión publicada y corregir incompatibilidades | Juli + Juan | **Hecho** (rama `juan/cierre-matriz`): `configuracion.json` apunta a esta revisión; `entrega.py` no necesitó cambios (la verificación de carga ya usa `construir_agente()`). Las condiciones de la matriz fijan su modelo, así que base y solo prompt siguen usando Gemma sin entrenar. |
| 4 | Fila «ambos» (checkpoint con el prompt optimizado) | Juan | **Hecho:** queda «no hecho» en la matriz (`no_hecho` en `evaluacion/matriz.json`) y en la Parte 4, con el motivo. |
| 5 | Confirmar que las particiones de datos son las finales (`datos/manifiesto.json` dice «provisional») | Cande | Si cambian, el entrenamiento habría que repetirlo. |
| 6 | Parte 5: medir VRAM, tiempo y costo en **A100 de 40 GB** | Pía | Las medidas de Kaggle T4 no sirven. Si no hay A100, decir la limitación en el informe. |
| 7 | Llevar `juli/entrenamiento` a `main` (PR con revisión de Juan) | Juli + Juan | **Hecho:** PR #10 revisado (28 pruebas sin GPU, sin credenciales, no toca `admision/`), aprobado y mergeado. |
| 8 | Sección del Loom (15–20 min en total, ~3–4 min de Juli) | Juli | Guion en `DECISIONES.md`: prompt, Kaggle/T4, submuestra, selección por validación, fallas. |
| 9 | Cerrar el issue #4 con el resumen (revisión, W&B, límites) | Juli | Después de 1 y 3. |

## Acceso de la cátedra (entrega: viernes 20/11/2026)
`mission.md` pide que la cátedra pueda abrir todo lo que cita el informe. Estado:
- [x] Grupo (cuatro integrantes) agregado a Hugging Face, W&B y Kaggle.
- [ ] **Cátedra (Paulo Veiga y Marco) con acceso de lectura** al repo privado de Hugging Face
  `genai-grupo-2/emergency-admission-agent` y a la entidad/proyecto de W&B `gen-ai-grupo-2/emergency-admission-agent`.
- [ ] Abrir los enlaces del informe con una cuenta que no sea del grupo (o pedir que alguien de la cátedra confirme).
- [ ] Correo a Paulo Veiga y Marco antes del viernes 20/11, con todo el grupo en copia: enlaces finales de GitHub, HF, W&B y Loom.
- [ ] El repositorio de GitHub está **público** por decisión del grupo; `mission.md` dice «privado, con acceso para la cátedra».
  Si la cátedra lo objeta, pasarlo a privado e invitarlos.
- Sin credenciales en Git: ningún token ni clave en el repo. Las claves de Kaggle (`HF_TOKEN`, `WANDB_API_KEY`) están sólo
  en *Secrets* de cada cuenta. Las claves de W&B expiran el 17/12/2026.

## Qué no se hizo y hay que decirlo
- No se entrenó sobre todo el conjunto ni 2 épocas (cuota de GPU); no se midió cuánto afecta.
- No hay checkpoint con el prompt optimizado.
- Nada se midió en A100; la verificación de carga fue en 2×T4.
- Los manifiestos de los dos ensayos fallidos no se bajaron de Kaggle; sólo están en W&B y en `DECISIONES.md`.
