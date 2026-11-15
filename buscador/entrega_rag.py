"""Adaptador exclusivo para evaluar el RAG con el comando oficial del kit.

No es la entrega del agente y no construye ni carga un modelo.
"""

from buscador.bm25 import BuscadorBM25


def construir_buscador(ruta_normas):
    return BuscadorBM25(ruta_normas)


def construir_agente():
    # El cargador del kit exige este nombre incluso para evaluar solo RAG.
    raise RuntimeError("Adaptador exclusivo de RAG: usar la entrega real para jugar casos")
