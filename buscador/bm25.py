"""Buscador PROVISORIO: BM25 con una sección entera de las normas por fragmento, como la referencia de la cátedra.

Está para que `entrega.py` funcione mientras llega el buscador de Pía (issue #2); cuando esté, `entrega.py` pasa a usar
el suyo y este archivo se borra. Las secciones y sus valores se leen siempre de la carpeta que recibe."""

import math
import re
import unicodedata
from collections import Counter
from pathlib import Path

from admision.normas import cargar_normas


def _tokens(texto: str) -> list[str]:
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.findall(r"[a-z0-9]+", t)


class BuscadorBM25:
    def __init__(self, ruta_normas: Path, k_entorno: int = 2, k1: float = 1.5, b: float = 0.75):
        self.secciones = cargar_normas(Path(ruta_normas))
        if not self.secciones:
            raise FileNotFoundError(f"no hay secciones NOR-*.md en {ruta_normas}")
        self.k_entorno, self.k1, self.b = k_entorno, k1, b
        self._docs = [Counter(_tokens(s.texto)) for s in self.secciones]
        self._largos = [sum(d.values()) for d in self._docs]
        self._medio = sum(self._largos) / len(self._largos)
        df = Counter(t for d in self._docs for t in d)
        n = len(self._docs)
        self._idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def _puntaje(self, consulta: list[str], i: int) -> float:
        d, largo, total = self._docs[i], self._largos[i], 0.0
        for t in consulta:
            f = d.get(t, 0)
            if f:
                total += self._idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * largo / self._medio))
        return total

    def recuperar(self, consulta: str, k: int):
        q = _tokens(consulta)
        orden = sorted(range(len(self.secciones)), key=lambda i: (-self._puntaje(q, i), i))
        return [self.secciones[i] for i in orden[:k]]
