"""SFT con LoRA de Gemma 4 E4B sobre las conversaciones de `datos/conversaciones/` (issue #4).

    python -m entrenar.entrenar --config entrenar/configs/sft-catedra.json --ensayo   # unos pocos pasos: memoria y flujo
    python -m entrenar.entrenar --config entrenar/configs/sft-catedra.json            # corrida completa
    python -m entrenar.entrenar --config entrenar/configs/sft-catedra.json --reanudar # sigue desde el último checkpoint

Qué hace, en orden:
1. valida los datos contra el prompt de la configuración (`entrenar/datos.py`) antes de cargar el modelo;
2. carga el modelo base (misma revisión fija que usa el agente) y le agrega LoRA sólo en el modelo de lenguaje;
3. entrena con pérdida sólo sobre las respuestas del asistente, una conversación por paso de micro-lote y
   `acumulacion` conversaciones por paso del optimizador; el orden de cada época sale de la semilla, así reanudar
   retoma exactamente por donde iba;
4. evalúa la pérdida en la partición de validación (nunca el test secreto ni los casos de práctica) y guarda un
   checkpoint cada `guardar_cada` pasos (adaptador + estado del optimizador), opcionalmente también en Hugging Face;
5. registra todo en W&B y en `corridas/entrenamiento/<nombre>/manifiesto.json`, también si la corrida falla.

Para la memoria: la pérdida se calcula sólo en las posiciones del asistente (`logits_to_keep`), porque el vocabulario
de Gemma es de unos 262.000 tokens y los logits de una conversación entera no entran en una T4.

`torch`, `transformers` y `peft` se importan recién acá; el resto del paquete se prueba sin GPU."""

import argparse
import inspect
import json
import math
import os
import random
import re
import sys
import time
from pathlib import Path

from agente.prompts import cargar_prompt, huella
from entrenar import config as configuracion
from entrenar import datos as datos_
from entrenar.manifiesto import Manifiesto, ahora, contexto_git, versiones

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_CORRIDAS = RAIZ / "corridas" / "entrenamiento"


def ruta_checkpoints(nombre: str, indicada: str | None) -> Path:
    """Los checkpoints pesan: van fuera de `corridas/` (que se commitea y se zipea) y fuera de Git."""
    return Path(indicada) if indicada else RAIZ / "checkpoints" / nombre


def orden_de_la_epoca(n: int, semilla: int, epoca: int) -> list[int]:
    orden = list(range(n))
    random.Random(semilla * 1000 + epoca).shuffle(orden)
    return orden


def pasos_por_epoca(n_ejemplos: int, acumulacion: int) -> int:
    return max(1, n_ejemplos // acumulacion)


def apartar_anterior(carpeta: Path) -> Path | None:
    """Un ensayo se puede repetir (típicamente después de arreglar algo): el anterior, fallido o no, se conserva con otro
    nombre en vez de abortar o pisarse. Las corridas reales nunca pasan por acá."""
    if not carpeta.exists():
        return None
    destino = carpeta.with_name(f"{carpeta.name}.anterior-{time.strftime('%Y%m%d-%H%M%S')}")
    os.replace(carpeta, destino)
    return destino


def lote_del_paso(orden_por_epoca: dict, n: int, semilla: int, acumulacion: int, paso: int) -> list[int]:
    """Índices de las conversaciones del paso `paso` (0 = el primero); determinista, así reanudar es exacto."""
    por_epoca = pasos_por_epoca(n, acumulacion)
    epoca, dentro = divmod(paso, por_epoca)
    if epoca not in orden_por_epoca:
        orden_por_epoca[epoca] = orden_de_la_epoca(n, semilla, epoca)
    return orden_por_epoca[epoca][dentro * acumulacion:(dentro + 1) * acumulacion]


def factor_de_lr(paso: int, total: int, warmup: int) -> float:
    """Calentamiento lineal y después coseno hasta 10 % del máximo. `paso` cuenta pasos del optimizador ya dados."""
    if paso < warmup:
        return (paso + 1) / max(1, warmup)
    progreso = (paso - warmup) / max(1, total - warmup)
    return 0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * min(1.0, progreso)))


def ultimo_checkpoint(carpeta: Path) -> Path | None:
    candidatos = [p for p in carpeta.glob("paso-*") if p.is_dir() and (p / "estado.pt").exists()] if carpeta.exists() else []
    return max(candidatos, key=lambda p: int(p.name.split("-")[1])) if candidatos else None


def traer_ultimo_de_hf(repo: str, nombre: str, carpeta: Path) -> Path | None:
    """Baja el último checkpoint subido por `subir_a_hf` (para reanudar en una sesión nueva de Kaggle, donde
    /kaggle/working empieza vacío). Devuelve la carpeta local o None si no hay ninguno."""
    from huggingface_hub import HfApi, snapshot_download

    token = os.environ.get("HF_TOKEN")
    prefijo = f"adaptadores/{nombre}/"
    pasos = set()
    for archivo in HfApi(token=token).list_repo_files(repo):
        coincide = re.match(rf"{re.escape(prefijo)}(paso-\d+)/", archivo)
        if coincide:
            pasos.add(coincide.group(1))
    if not pasos:
        return None
    ultimo = max(pasos, key=lambda p: int(p.split("-")[1]))
    descarga = Path(snapshot_download(repo, token=token, allow_patterns=[f"{prefijo}{ultimo}/*"],
                                      local_dir=str(carpeta / "_hf")))
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / ultimo
    if destino.exists():
        import shutil
        shutil.rmtree(destino)
    os.replace(descarga / prefijo / ultimo, destino)
    return destino


class Entrenamiento:
    def __init__(self, config: dict, manifiesto: Manifiesto, carpeta_checkpoints: Path, usar_wandb: bool):
        import torch
        import transformers

        self.torch, self.transformers = torch, transformers
        self.config, self.manifiesto, self.carpeta = config, manifiesto, carpeta_checkpoints
        self.usar_wandb, self.wandb = usar_wandb, None
        self.inicio = time.monotonic()
        self.logits_to_keep_ok = True

    # ---------------------------------------------------------------- modelo
    def cargar_modelo(self):
        from peft import LoraConfig, get_peft_model

        torch, transformers = self.torch, self.transformers
        m = self.config["modelo"]
        token = os.environ.get("HF_TOKEN") or None
        self.tokenizador = transformers.AutoTokenizer.from_pretrained(m["repo"], revision=m["revision"], token=token)
        argumentos = dict(revision=m["revision"], token=token, dtype=getattr(torch, m["dtype"]),
                          device_map=m["device_map"])
        if m["cuantizacion"] == "nf4":  # alternativa si bf16 no entra; necesita bitsandbytes
            argumentos["quantization_config"] = transformers.BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=getattr(torch, m["dtype"]))
        try:  # igual que agente/modelo.py: Gemma 4 se publica como multimodal
            base = transformers.AutoModelForCausalLM.from_pretrained(m["repo"], **argumentos)
        except ValueError:
            base = transformers.AutoModelForImageTextToText.from_pretrained(m["repo"], **argumentos)
        base.config.use_cache = False
        if m["cuantizacion"] == "nf4":
            from peft import prepare_model_for_kbit_training
            base = prepare_model_for_kbit_training(base, use_gradient_checkpointing=True)
        else:
            base.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        lora = self.config["lora"]
        self.modelo = get_peft_model(base, LoraConfig(
            r=int(lora["r"]), lora_alpha=int(lora["alpha"]), lora_dropout=float(lora["dropout"]),
            target_modules=lora["modulos"], bias="none", task_type="CAUSAL_LM"))
        entrenables = [n for n, p in self.modelo.named_parameters() if p.requires_grad]
        if not entrenables:
            raise RuntimeError(f"la expresión lora.modulos no coincidió con ningún módulo: {lora['modulos']!r}")
        total = sum(p.numel() for p in self.modelo.parameters())
        propios = sum(p.numel() for p in self.modelo.parameters() if p.requires_grad)
        self.manifiesto.actualizar(parametros={"total": total, "entrenables": propios,
                                               "modulos_con_lora": len({n.rsplit(".lora_", 1)[0] for n in entrenables})})
        base_forward = self.modelo.get_base_model().forward
        parametros = inspect.signature(base_forward).parameters
        self.extras_ceros = [n for n in ("token_type_ids", "mm_token_type_ids") if n in parametros]
        self.dispositivo = self.modelo.get_input_embeddings().weight.device

    # ---------------------------------------------------------------- pérdida
    def perdida_suma(self, ejemplo) -> tuple:
        """Suma de la entropía cruzada sobre los tokens del asistente, y cuántos son."""
        torch = self.torch
        n = len(ejemplo.ids)
        objetivos = [t for t in range(1, n) if ejemplo.mascara[t]]
        # En CPU: con device_map="auto" las últimas capas (y lm_head) están en otra GPU que los embeddings, y un índice
        # en cuda:0 no puede indexar un tensor de cuda:1. Un índice en CPU lo acepta cualquier dispositivo.
        posiciones = torch.tensor([t - 1 for t in objetivos])
        entrada = torch.tensor([ejemplo.ids], device=self.dispositivo)
        kwargs = {"input_ids": entrada, "attention_mask": torch.ones_like(entrada), "use_cache": False}
        for nombre in self.extras_ceros:  # Gemma exige estos campos al entrenar aunque no haya imágenes
            kwargs[nombre] = torch.zeros_like(entrada)
        if self.logits_to_keep_ok:
            kwargs["logits_to_keep"] = posiciones
        try:
            logits = self.modelo(**kwargs).logits[0]
        except TypeError as error:
            if "logits_to_keep" not in str(error):
                raise
            self.logits_to_keep_ok = False
            print("el modelo no acepta logits_to_keep: se calculan los logits completos (más memoria)", flush=True)
            kwargs.pop("logits_to_keep")
            logits = self.modelo(**kwargs).logits[0]
        if logits.shape[0] == n:  # el modelo devolvió todas las posiciones
            logits = logits[posiciones.to(logits.device)]
        objetivo = entrada[0, torch.tensor(objetivos, device=self.dispositivo)].to(logits.device)
        suma = torch.nn.functional.cross_entropy(logits.float(), objetivo, reduction="sum")
        return suma, len(objetivos)

    def evaluar(self, ejemplos) -> dict:
        torch = self.torch
        self.modelo.eval()
        suma, tokens = 0.0, 0
        with torch.no_grad():
            for e in ejemplos:
                s, n = self.perdida_suma(e)
                suma += float(s)
                tokens += n
        self.modelo.train()
        return {"perdida": suma / max(1, tokens), "tokens": tokens, "conversaciones": len(ejemplos)}

    # ---------------------------------------------------------------- checkpoints
    def guardar_checkpoint(self, paso: int, optimizador, metricas: dict) -> Path:
        torch = self.torch
        destino = self.carpeta / f"paso-{paso:05d}"
        temporal = self.carpeta / f"paso-{paso:05d}.tmp"
        temporal.mkdir(parents=True, exist_ok=True)
        self.modelo.save_pretrained(temporal)
        torch.save({"paso": paso, "optimizador": optimizador.state_dict()}, temporal / "estado.pt")
        if destino.exists():
            import shutil
            shutil.rmtree(destino)
        os.replace(temporal, destino)
        # El estado del optimizador pesa varias veces el adaptador: sólo se conserva el del último checkpoint.
        for viejo in self.carpeta.glob("paso-*"):
            if viejo != destino and (viejo / "estado.pt").exists():
                (viejo / "estado.pt").unlink()
        self.manifiesto.agregar_checkpoint(paso=paso, ruta=str(destino), **metricas)
        if self.config.get("subir_checkpoints_a"):
            self.subir_a_hf(destino, paso)
        return destino

    def subir_a_hf(self, carpeta: Path, paso: int):
        """Copia del checkpoint en el repo privado del grupo para poder reanudar si la sesión de Kaggle se corta.
        Si falla no se aborta el entrenamiento: queda anotado en el manifiesto."""
        try:
            from huggingface_hub import HfApi
            api = HfApi(token=os.environ.get("HF_TOKEN"))
            repo = self.config["subir_checkpoints_a"]
            api.create_repo(repo, private=True, exist_ok=True)
            info = api.upload_folder(repo_id=repo, folder_path=str(carpeta), repo_type="model",
                                     path_in_repo=f"adaptadores/{self.config['nombre']}/paso-{paso:05d}",
                                     commit_message=f"adaptador de {self.config['nombre']} en el paso {paso}")
            self.manifiesto.actualizar_checkpoint(paso, hf_adaptador={"repo": repo, "revision": info.oid})
        except Exception as error:  # noqa: BLE001 - registrar y seguir
            self.manifiesto.actualizar_checkpoint(paso, hf_adaptador_error=f"{type(error).__name__}: {error}"[:500])

    def reanudar(self, optimizador) -> int:
        from safetensors.torch import load_file
        from peft import set_peft_model_state_dict

        ultimo = ultimo_checkpoint(self.carpeta)
        if ultimo is None:
            raise FileNotFoundError(f"no hay checkpoints para reanudar en {self.carpeta} (con estado del optimizador)")
        pesos = load_file(str(ultimo / "adapter_model.safetensors"))
        set_peft_model_state_dict(self.modelo, pesos)
        estado = self.torch.load(ultimo / "estado.pt", map_location="cpu")
        optimizador.load_state_dict(estado["optimizador"])
        print(f"reanudando desde {ultimo.name}", flush=True)
        return int(estado["paso"])

    # ---------------------------------------------------------------- vram
    def vram_pico_gib(self) -> list[float]:
        torch = self.torch
        if not torch.cuda.is_available():
            return []
        return [round(torch.cuda.max_memory_allocated(i) / 2**30, 2) for i in range(torch.cuda.device_count())]

    def registrar(self, metricas: dict, paso: int):
        if self.wandb:
            self.wandb.log(metricas, step=paso)
        print(f"paso {paso}: " + " ".join(f"{k}={v:.4g}" if isinstance(v, float) else f"{k}={v}"
                                          for k, v in metricas.items()), flush=True)

    # ---------------------------------------------------------------- bucle
    def correr(self, train, validacion, reanudar: bool) -> str:
        torch = self.torch
        c = self.config
        o = c["optimizador"]
        acumulacion = int(o["acumulacion"])
        por_epoca = pasos_por_epoca(len(train), acumulacion)
        total_pasos = por_epoca * int(c["epocas"])
        if "ensayo" in c:
            total_pasos = min(total_pasos, c["ensayo"]["max_pasos"])
        parametros = [p for p in self.modelo.parameters() if p.requires_grad]
        optimizador = torch.optim.AdamW(parametros, lr=float(o["lr"]), weight_decay=float(o["weight_decay"]),
                                        betas=(0.9, 0.999))
        paso = self.reanudar(optimizador) if reanudar else 0
        self.manifiesto.actualizar(plan={"pasos_por_epoca": por_epoca, "pasos_totales": total_pasos,
                                         "conversaciones_por_paso": acumulacion})
        self.modelo.train()
        if self.usar_wandb:
            self.iniciar_wandb(total_pasos)
        orden, tokens_vistos, t0 = {}, 0, time.monotonic()
        mejor = min((cp["perdida_validacion"] for cp in self.manifiesto.datos["checkpoints"]
                     if "perdida_validacion" in cp), default=None)
        limite = float(c["max_horas"]) * 3600
        ultima_val = None
        while paso < total_pasos:
            indices = lote_del_paso(orden, len(train), int(c["semilla"]), acumulacion, paso)
            ejemplos = [train[i] for i in indices]
            n_tokens = sum(e.n_supervisados for e in ejemplos)
            for g in optimizador.param_groups:
                g["lr"] = float(o["lr"]) * factor_de_lr(paso, total_pasos, int(o["warmup_pasos"]))
            suma_total = 0.0
            for e in ejemplos:
                suma, _ = self.perdida_suma(e)
                (suma / n_tokens).backward()
                suma_total += float(suma.detach())
                tokens_vistos += len(e.ids)
            norma = torch.nn.utils.clip_grad_norm_(parametros, float(o["max_norma_grad"]))
            optimizador.step()
            optimizador.zero_grad(set_to_none=True)
            paso += 1
            metricas = {"perdida_entrenamiento": suma_total / n_tokens, "norma_gradiente": float(norma),
                        "lr": optimizador.param_groups[0]["lr"], "epoca": paso / por_epoca,
                        "tokens_por_s": tokens_vistos / max(1e-9, time.monotonic() - t0)}
            if not math.isfinite(metricas["perdida_entrenamiento"]):
                raise FloatingPointError(f"la pérdida de entrenamiento no es finita en el paso {paso}")
            if torch.cuda.is_available():
                metricas["vram_pico_gib"] = max(self.vram_pico_gib())
            self.registrar(metricas, paso)
            fin = paso >= total_pasos
            pausar = (time.monotonic() - self.inicio) > limite
            if paso % int(c["evaluar_cada"]) == 0 or fin or pausar:
                ultima_val = self.evaluar(validacion)
                self.registrar({"perdida_validacion": ultima_val["perdida"]}, paso)
            if paso % int(c["guardar_cada"]) == 0 or fin or pausar:
                info = {"perdida_entrenamiento": metricas["perdida_entrenamiento"]}
                if ultima_val is not None:
                    info["perdida_validacion"] = ultima_val["perdida"]
                    if mejor is None or ultima_val["perdida"] < mejor:
                        mejor = ultima_val["perdida"]
                        self.manifiesto.actualizar(mejor_checkpoint={"paso": paso,
                                                                     "perdida_validacion": mejor,
                                                                     "criterio": "menor pérdida de validación"})
                self.guardar_checkpoint(paso, optimizador, info)
            if pausar and not fin:
                print("se alcanzó max_horas: checkpoint guardado, se puede reanudar con --reanudar", flush=True)
                self.manifiesto.actualizar(paso_alcanzado=paso)
                return "pausada"
        self.manifiesto.actualizar(paso_alcanzado=paso)
        return "completada"

    def iniciar_wandb(self, total_pasos: int):
        import wandb

        w = self.config["wandb"]
        previo = self.manifiesto.datos.get("wandb", {}).get("run_id")
        self.wandb = wandb.init(project=w["proyecto"], entity=w.get("entidad") or None, name=self.config["nombre"],
                                id=previo, resume="allow", config=self.config,
                                tags=["sft", "lora"] + (["ensayo"] if "ensayo" in self.config else []))
        self.wandb.define_metric("perdida_validacion", summary="min")
        self.manifiesto.actualizar(wandb={"entidad": self.wandb.entity, "proyecto": self.wandb.project,
                                          "run_id": self.wandb.id, "url": self.wandb.url,
                                          "pasos_totales": total_pasos})


def preparar_datos(config: dict):
    prompt = cargar_prompt(config["prompt"]["version"])
    rutas = {k: RAIZ / config["datos"][k] for k in ("train", "validacion")}
    filas = {k: datos_.leer_conversaciones(r) for k, r in rutas.items()}
    casos = [json.loads(linea) for linea in
             (RAIZ / "practica" / "casos.jsonl").read_text(encoding="utf-8").splitlines() if linea.strip()]
    resumen = datos_.validar(filas["train"], filas["validacion"], prompt, casos)
    if "ensayo" in config:
        filas["train"] = filas["train"][:config["ensayo"]["max_train"]]
        filas["validacion"] = filas["validacion"][:config["ensayo"]["max_validacion"]]
    descripcion = {
        "prompt": {"version": config["prompt"]["version"], "sha256": huella(prompt)},
        "train": {"archivo": config["datos"]["train"], "sha256": datos_.sha256_archivo(rutas["train"])},
        "validacion": {"archivo": config["datos"]["validacion"],
                       "sha256": datos_.sha256_archivo(rutas["validacion"])},
        "validacion_de_datos": resumen,
        "manifiesto_de_datos": {"archivo": "datos/manifiesto.json",
                                "sha256": datos_.sha256_archivo(RAIZ / "datos" / "manifiesto.json")},
    }
    return filas, descripcion


def principal(argv=None) -> int:
    p = argparse.ArgumentParser(description="SFT con LoRA sobre las conversaciones del grupo.")
    p.add_argument("--config", required=True)
    p.add_argument("--ensayo", action="store_true", help="corrida corta para comprobar memoria y flujo (no se reporta)")
    p.add_argument("--reanudar", action="store_true", help="seguir desde el último checkpoint de la misma corrida")
    p.add_argument("--checkpoints", help="carpeta de checkpoints (por defecto ./checkpoints/<nombre>)")
    p.add_argument("--sin-wandb", action="store_true", help="sólo para ensayos locales: no registra en W&B")
    p.add_argument("--solo-datos", action="store_true", help="valida y tokeniza los datos y termina (no usa GPU)")
    args = p.parse_args(argv)

    config = configuracion.cargar(args.config)
    if args.ensayo:
        config = configuracion.para_ensayo(config)
    if args.sin_wandb and "ensayo" not in config:
        p.error("--sin-wandb sólo se permite con --ensayo: toda corrida real tiene que quedar en W&B")
    nombre = config["nombre"]
    carpeta_corrida = CARPETA_CORRIDAS / nombre
    ruta_manifiesto = carpeta_corrida / "manifiesto.json"
    carpeta_ckpt = ruta_checkpoints(nombre, args.checkpoints)
    if "ensayo" in config and ruta_manifiesto.exists() and not args.reanudar and not args.solo_datos:
        print("había un ensayo anterior; se conserva en", apartar_anterior(carpeta_corrida), flush=True)
    if ruta_manifiesto.exists() and not args.reanudar and not args.solo_datos:
        p.error(f"ya existe {ruta_manifiesto}: las corridas no se pisan; usar otro nombre o --reanudar")
    if args.reanudar and not ruta_manifiesto.exists():
        p.error(f"no hay manifiesto en {ruta_manifiesto} para reanudar")

    filas, descripcion = preparar_datos(config)
    print("datos válidos:", descripcion["validacion_de_datos"], flush=True)
    if args.solo_datos:
        return 0
    if args.reanudar and ultimo_checkpoint(carpeta_ckpt) is None and config.get("subir_checkpoints_a"):
        traido = traer_ultimo_de_hf(config["subir_checkpoints_a"], nombre, carpeta_ckpt)
        print("checkpoint traído de Hugging Face:", traido, flush=True)

    inicial = {"nombre": nombre, "estado": "en_curso", "inicio": ahora(), "comando": "python -m entrenar.entrenar "
               + " ".join(sys.argv[1:]), "config": config, "semilla": config["semilla"], "datos": descripcion,
               "git": contexto_git(), "versiones": versiones(), "checkpoints_en": str(carpeta_ckpt)}
    if args.reanudar:
        manifiesto = Manifiesto.retomar(ruta_manifiesto)
        manifiesto.datos["sesiones"].append({"inicio": ahora(), "git": contexto_git(), "versiones": versiones()})
        manifiesto.actualizar(estado="en_curso")
    else:
        manifiesto = Manifiesto(ruta_manifiesto, inicial)
    entrenamiento = None
    try:
        entrenamiento = Entrenamiento(config, manifiesto, carpeta_ckpt, usar_wandb=not args.sin_wandb)
        random.seed(config["semilla"])
        entrenamiento.torch.manual_seed(config["semilla"])
        entrenamiento.cargar_modelo()
        train, est_train = datos_.construir_ejemplos(entrenamiento.tokenizador, filas["train"],
                                                     int(config["datos"]["max_tokens"]))
        val, est_val = datos_.construir_ejemplos(entrenamiento.tokenizador, filas["validacion"],
                                                 int(config["datos"]["max_tokens"]))
        manifiesto.actualizar(tokens={"train": est_train, "validacion": est_val})
        if not train or not val:
            raise RuntimeError("no quedaron conversaciones para entrenar o validar (¿max_tokens muy bajo?)")
        estado = entrenamiento.correr(train, val, args.reanudar)
        manifiesto.terminar(estado, vram_pico_gib=entrenamiento.vram_pico_gib(),
                            segundos=round(time.monotonic() - entrenamiento.inicio))
        if entrenamiento.wandb:
            entrenamiento.wandb.finish()
        return 0
    except BaseException as error:  # noqa: BLE001 - la corrida fallida también se documenta
        manifiesto.fallar(error)
        if entrenamiento is not None and entrenamiento.wandb:
            entrenamiento.wandb.finish(exit_code=1)
        raise


if __name__ == "__main__":
    sys.exit(principal())
