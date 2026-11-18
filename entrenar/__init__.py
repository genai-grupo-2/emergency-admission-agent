"""Entrenamiento del agente (issue #4): SFT con LoRA sobre las conversaciones de `datos/conversaciones/`.

    python -m entrenar.entrenar --config entrenar/configs/sft-catedra.json --ensayo     # ensayo corto
    python -m entrenar.entrenar --config entrenar/configs/sft-catedra.json              # corrida completa
    python -m entrenar.publicar --nombre sft-catedra-01 --paso 272 --repo <usuario/repo> # fusiona y sube a HF

Los módulos que no necesitan GPU (`config`, `datos`, `manifiesto`) no importan torch: se prueban sin GPU."""
