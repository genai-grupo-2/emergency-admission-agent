"""El modelo como función de lote: recibe una lista de conversaciones y devuelve una respuesta por conversación.

`torch` y `transformers` se importan recién al construir el modelo, así el ciclo del agente, los tests y el optimizador
se pueden importar sin GPU. Decodificación greedy (sin muestreo) para que la evaluación sea reproducible; en GPU,
generar en lote puede mover algún caso (ver mission.md, Auditabilidad)."""

import os


class ModeloHF:
    def __init__(self, repo: str, revision: str, dtype: str = "bfloat16", max_new_tokens: int = 384, lote: int = 50):
        import torch
        import transformers

        self.repo, self.revision, self.max_new_tokens, self.lote = repo, revision, max_new_tokens, lote
        token = os.environ.get("HF_TOKEN") or None
        self.tokenizer = transformers.AutoTokenizer.from_pretrained(repo, revision=revision, token=token)
        self.tokenizer.padding_side = "left"
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        argumentos = dict(revision=revision, token=token, dtype=getattr(torch, dtype), device_map="cuda")
        try:  # Gemma 4 se publica como modelo multimodal; para texto alcanza con la clase causal si existe.
            self.modelo = transformers.AutoModelForCausalLM.from_pretrained(repo, **argumentos)
        except ValueError:
            self.modelo = transformers.AutoModelForImageTextToText.from_pretrained(repo, **argumentos)
        self.modelo.eval()
        self._torch = torch

    def _plantilla(self, mensajes: list[dict]) -> str:
        return self.tokenizer.apply_chat_template(mensajes, tokenize=False, add_generation_prompt=True)

    def __call__(self, conversaciones: list[list[dict]]) -> list[str]:
        respuestas = []
        for i in range(0, len(conversaciones), self.lote):
            textos = [self._plantilla(c) for c in conversaciones[i:i + self.lote]]
            entrada = self.tokenizer(textos, return_tensors="pt", padding=True, add_special_tokens=False)
            entrada = entrada.to(self.modelo.device)
            with self._torch.inference_mode():
                salida = self.modelo.generate(**entrada, max_new_tokens=self.max_new_tokens, do_sample=False,
                                              pad_token_id=self.tokenizer.pad_token_id)
            nuevos = salida[:, entrada["input_ids"].shape[1]:]
            respuestas.extend(self.tokenizer.batch_decode(nuevos, skip_special_tokens=True))
        return respuestas

    def contar_tokens(self, mensajes: list[dict]) -> int:
        """Tokens de una conversación con la plantilla de chat del modelo aplicada."""
        return len(self.tokenizer(self._plantilla(mensajes), add_special_tokens=False)["input_ids"])


def construir_modelo(config_modelo: dict):
    backend = config_modelo.get("backend", "hf")
    if backend == "hf":
        return ModeloHF(config_modelo["repo"], config_modelo["revision"], config_modelo.get("dtype", "bfloat16"),
                        int(config_modelo.get("max_new_tokens", 384)), int(config_modelo.get("lote", 50)))
    if backend == "falso":
        from agente.falso import ModeloFalso
        return ModeloFalso()
    raise ValueError(f"backend de modelo desconocido: {backend!r}")
