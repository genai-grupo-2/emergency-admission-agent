"""La entrega del grupo, según el contrato del kit (README, «El contrato de la entrega»).

    construir_buscador(ruta_normas) -> buscador con recuperar(consulta, k) y k_entorno
    construir_agente()              -> agente con jugar_lote(entornos); carga el modelo una sola vez

Qué modelo, qué prompt y qué buscador se usan sale de `configuracion.json` (ver `agente/config.py` para pisarlo con
variables de entorno al evaluar otras condiciones). Nada de acá lee casos ni fichas esperadas."""

from pathlib import Path

from agente.config import cargar_config
from agente.modelo import construir_modelo
from agente.prompts import cargar_prompt


def construir_buscador(ruta_normas):
    from buscador.bm25 import BuscadorBM25  # provisorio hasta el buscador de Pía (#2)

    config = cargar_config()
    return BuscadorBM25(Path(ruta_normas), k_entorno=int(config["buscador"]["k_entorno"]))


def construir_agente():
    from admision.ejemplo import AgenteJSON

    config = cargar_config()
    from admision.ejemplo import mensaje_de_sistema

    if cargar_prompt(config["prompt"]["version"]) != mensaje_de_sistema():
        raise NotImplementedError("el agente de ejemplo sólo acepta el prompt de la cátedra")
    return AgenteJSON(construir_modelo(config["modelo"]))
