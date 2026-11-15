"""Comprueba el entorno local sin autenticar servicios ni ejecutar trabajos GPU."""

import importlib
import importlib.metadata
from pathlib import Path
import platform
import sys
import tomllib


def main() -> int:
    raiz = Path(__file__).resolve().parents[1]
    proyecto = tomllib.loads((raiz / "pyproject.toml").read_text(encoding="utf-8"))
    python_esperado = (raiz / ".python-version").read_text().strip()
    fallos = []
    actual = platform.python_version()
    print(f"Python: {actual} (esperado: {python_esperado})")
    if actual != python_esperado:
        fallos.append("La version de Python no coincide con .python-version")

    dependencias = proyecto["project"]["dependencies"] + proyecto["dependency-groups"]["dev"]
    for requisito in dependencias:
        if "==" not in requisito:
            fallos.append(f"Dependencia sin version exacta: {requisito}")
            continue
        nombre, esperada = requisito.split("==", 1)
        try:
            instalada = importlib.metadata.version(nombre)
        except importlib.metadata.PackageNotFoundError:
            instalada = "no instalada"
        print(f"{nombre}: {instalada} (esperado: {esperada})")
        if instalada != esperada:
            fallos.append(f"Version incorrecta de {nombre}")

    # Importar el kit completo detecta errores de instalacion sin iniciar servicios.
    for archivo in sorted((raiz / "admision").glob("*.py")):
        modulo = "admision" if archivo.stem == "__init__" else f"admision.{archivo.stem}"
        try:
            importlib.import_module(modulo)
        except Exception as error:
            fallos.append(f"No se pudo importar {modulo}: {type(error).__name__}")
    if fallos:
        for fallo in fallos:
            print(f"ERROR: {fallo}")
        return 1
    print("Entorno local: OK. Accesos remotos, modelo y GPU requieren comprobacion aparte.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
