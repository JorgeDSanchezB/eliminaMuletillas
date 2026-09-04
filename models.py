"""Modelos de datos del proyecto EliminaMuletillas."""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path

FILLER_JSON_PATH = Path(__file__).parent / "filler_words.json"

DEFAULT_FILLERS: list[str] = [
    "eh", "este", "o sea", "como que", "bueno",
    "entonces", "digamos", "vale", "en plan", "sabes",
]


@dataclass
class Project:
    """Metadatos de un proyecto de audio. Los valores provienen SIEMPRE
    del header real del archivo (nunca se asumen)."""

    id: int | None
    original_path: Path
    duration: float          # segundos
    sample_rate: int         # Hz, leído del header
    channels: int            # leído del header
    bit_depth: int           # sample_width * 8
    export_path: Path | None = None


@dataclass
class WordTimestamp:
    """Una palabra transcrita por Whisper con su posición temporal."""

    text: str
    start: float             # segundos
    end: float               # segundos
    confidence: float
    is_filler: bool = False
    will_remove: bool = True


class FillerConfig:
    """Singleton que carga/guarda la lista de muletillas en filler_words.json.

    El usuario (el "DM") puede añadir o eliminar frases sin tocar el código:
    basta con usar add()/remove(), que persisten en el JSON al instante.
    """

    _instance: "FillerConfig | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "FillerConfig":
        with cls._lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance.phrases: list[str] = []
                instance._load()
                cls._instance = instance
        return cls._instance

    def _load(self) -> None:
        if FILLER_JSON_PATH.exists():
            try:
                data = json.loads(FILLER_JSON_PATH.read_text(encoding="utf-8"))
                self.phrases = [str(p) for p in data.get("fillers", DEFAULT_FILLERS)]
                return
            except (json.JSONDecodeError, OSError):
                pass  # JSON corrupto: se regenera con los defaults
        self.phrases = list(DEFAULT_FILLERS)
        self.save()

    def save(self) -> None:
        FILLER_JSON_PATH.write_text(
            json.dumps({"fillers": self.phrases}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, phrase: str) -> bool:
        clean = phrase.strip().lower()
        if not clean or clean in self.phrases:
            return False
        self.phrases.append(clean)
        self.save()
        return True

    def remove(self, phrase: str) -> bool:
        if phrase in self.phrases:
            self.phrases.remove(phrase)
            self.save()
            return True
        return False

    def reload(self) -> None:
        self._load()
