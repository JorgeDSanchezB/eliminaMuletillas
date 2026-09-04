"""Capa de Detección: marca muletillas sobre WordTimestamps ya transcritos.

Clave del diseño: esta capa trabaja SOLO sobre los objetos WordTimestamp
en memoria. Añadir/quitar muletillas del JSON re-ejecuta mark_fillers()
en milisegundos; Whisper nunca se vuelve a llamar.
"""
from __future__ import annotations

import re
from unidecode import unidecode

from models import FillerConfig, WordTimestamp

_PUNCT = ".,;:¡!?¿\"'«»“”‘’…()[]"


def normalize(text: str) -> str:
    """Minúsculas, sin acentos y sin puntuación: 'Eh,' == 'eh'."""
    return unidecode(text.lower().strip(_PUNCT).strip())


def mark_fillers(words: list[WordTimestamp], config: FillerConfig) -> None:
    """Marca is_filler=True y will_remove=True en las palabras que
    coinciden con la lista ACTIVA del config (in-place).

    Soporta frases de varias palabras ("o sea", "como que") mediante
    ventana deslizante sobre la secuencia de palabras transcritas.
    """
    active = {normalize(p) for p in config.phrases if normalize(p)}
    normalized = [normalize(w.text) for w in words]

    # Reset: al cambiar la lista activa, el marcado se recalcula por completo.
    for w in words:
        w.is_filler = False
        w.will_remove = False

    # Coincidencias de una sola palabra.
    for i, w in enumerate(words):
        if normalized[i] in active:
            w.is_filler = True

    # Coincidencias de frases (2+ palabras).
    for phrase in active:
        n = len(phrase.split())
        if n < 2:
            continue
        pattern = re.compile(r"\s+".join(re.escape(tok) for tok in phrase.split()))
        joined = " ".join(normalized)
        for m in pattern.finditer(joined):
            word_index = len(joined[: m.start()].split())
            for j in range(word_index, word_index + n):
                if j < len(words):
                    words[j].is_filler = True

    # Las muletillas detectadas se marcan para eliminar por defecto.
    for w in words:
        if w.is_filler:
            w.will_remove = True
