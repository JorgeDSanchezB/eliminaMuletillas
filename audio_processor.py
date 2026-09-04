"""Capas de Adquisición, Análisis, Edición y Exportación de audio.

Reglas del proyecto que este módulo garantiza:
- Cero hardcoding: sample_rate / canales / bit_depth se leen del header real.
- No se corta "en seco": todo corte lleva crossfade de 25 ms por defecto.
- Los cortes se hacen por índices de frames sobre segmentos, nunca
  reconstruyendo el archivo entero manualmente en RAM.
"""
from __future__ import annotations

import importlib
import math
import types
import wave
from functools import lru_cache
from pathlib import Path
from typing import Callable

import numpy as np
import whisper
from pydub import AudioSegment
from tqdm import tqdm as _tqdm

from models import WordTimestamp

# OJO: `import whisper.transcribe as x` devolvería la FUNCIÓN whisper.transcribe
# (el __init__ del paquete la sombrea), no el módulo. Por eso se usa importlib.
_whisper_transcribe = importlib.import_module("whisper.transcribe")

ProgressCallback = Callable[[float], None]  # recibe 0.0 <= pct <= 1.0

DEFAULT_CROSSFADE_MS = 25


# ---------------------------------------------------------------------------
# Capa de Adquisición
# ---------------------------------------------------------------------------

def read_header(file_path: Path) -> dict[str, int | float]:
    """Lee sample_rate, canales y bit_depth del header sin decodificar
    todo el audio cuando el formato lo permite (WAV usa el módulo `wave`)."""
    suffix = file_path.suffix.lower()
    if suffix == ".wav":
        with wave.open(str(file_path), "rb") as wav:
            return {
                "duration": wav.getnframes() / wav.getframerate(),
                "sample_rate": wav.getframerate(),
                "channels": wav.getnchannels(),
                "bit_depth": wav.getsampwidth() * 8,
            }
    # Formatos comprimidos (MP3/M4A/OGG): pydub decodifica para leer el header.
    segment = AudioSegment.from_file(str(file_path))
    return {
        "duration": len(segment) / 1000.0,
        "sample_rate": segment.frame_rate,
        "channels": segment.channels,
        "bit_depth": segment.sample_width * 8,
    }


def load_audio(file_path: Path) -> AudioSegment:
    """Carga el audio respetando los parámetros del header real.
    MP3/M4A/OGG se convierten a WAV en memoria (pydub usa ffmpeg)."""
    return AudioSegment.from_file(str(file_path))


# ---------------------------------------------------------------------------
# Capa de Análisis (Whisper con timestamps por palabra)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=None)
def load_model(model_size: str = "small"):
    """Carga el modelo Whisper (cacheado entre sesiones)."""
    return whisper.load_model(model_size)


class _ProgressTqdm(_tqdm):
    """Envoltorio de tqdm para reportar el progreso interno de Whisper.

    Nota: el bucle de whisper hace `continue` sin actualizar la barra en los
    tramos sin voz (fast-forward), por eso close() reporta el 100% final.
    """
    _hook: ProgressCallback | None = None

    def update(self, n: int = 1) -> bool | None:
        if self.total and _ProgressTqdm._hook is not None:
            _ProgressTqdm._hook(min(self.n / self.total, 1.0))
        return super().update(n)

    def close(self) -> None:
        if _ProgressTqdm._hook is not None:
            _ProgressTqdm._hook(1.0)
            _ProgressTqdm._hook = None
        return super().close()


# Módulo sustituto: whisper.transcribe hace `tqdm.tqdm(...)`, así que el
# reemplazo del módulo debe exponer la clase como atributo `.tqdm`.
_fake_tqdm_module = types.ModuleType("tqdm")
_fake_tqdm_module.tqdm = _ProgressTqdm


def transcribe_with_timestamps(
    audio_path: Path,
    progress_callback: ProgressCallback | None = None,
    model_size: str = "small",
    language: str = "es",
) -> list[WordTimestamp]:
    """Transcribe el audio y devuelve palabras con timestamps.

    Tolerancia a fallos: los segmentos sin palabras detectadas (ruido,
    silencio) se marcan como "[No transcrito]" con will_remove=False,
    de modo que NUNCA se eliminan automáticamente.
    """
    model = load_model(model_size)

    _ProgressTqdm._hook = progress_callback
    original_tqdm = _whisper_transcribe.tqdm
    _whisper_transcribe.tqdm = _fake_tqdm_module
    try:
        result = model.transcribe(
            str(audio_path),
            language=language,
            word_timestamps=True,
            verbose=False,  # habilita la barra de progreso interna
        )
    finally:
        _whisper_transcribe.tqdm = original_tqdm
        _ProgressTqdm._hook = None

    words: list[WordTimestamp] = []
    for segment in result.get("segments", []):
        segment_words = segment.get("words") or []
        if not segment_words:
            words.append(
                WordTimestamp(
                    text="[No transcrito]",
                    start=float(segment.get("start", 0.0)),
                    end=float(segment.get("end", 0.0)),
                    confidence=0.0,
                    is_filler=False,
                    will_remove=False,
                )
            )
            continue
        for w in segment_words:
            words.append(
                WordTimestamp(
                    text=str(w.get("word", "")).strip(),
                    start=float(w.get("start", 0.0)),
                    end=float(w.get("end", 0.0)),
                    confidence=float(w.get("probability", 0.0)),
                )
            )
    return words


# ---------------------------------------------------------------------------
# Capa de Edición (cortes suaves con crossfade)
# ---------------------------------------------------------------------------

def merge_spans(words_to_remove: list[WordTimestamp]) -> list[list[int]]:
    """Convierte las palabras a eliminar en rangos [start_ms, end_ms],
    fusionando los solapados o adyacentes."""
    spans: list[list[int]] = []
    for w in sorted(words_to_remove, key=lambda w: w.start):
        start_ms, end_ms = int(w.start * 1000), int(w.end * 1000)
        if spans and start_ms <= spans[-1][1]:
            spans[-1][1] = max(spans[-1][1], end_ms)
        else:
            spans.append([start_ms, end_ms])
    return spans


def apply_filters(
    audio_segment: AudioSegment,
    words_to_remove: list[WordTimestamp],
    crossfade_ms: int = DEFAULT_CROSSFADE_MS,
    progress_callback: ProgressCallback | None = None,
) -> AudioSegment:
    """Elimina los rangos de palabras indicados aplicando un crossfade
    (fade out + fade in) de `crossfade_ms` en cada unión, para evitar clicks.

    El trabajo se hace por índices de frames (slicing de pydub), sin
    reconstruir el audio entero a mano. Si no hay nada que eliminar,
    devuelve el segmento original sin copiar.
    """
    spans = merge_spans(words_to_remove)
    if not spans:
        return audio_segment

    def join(left: AudioSegment, right: AudioSegment) -> AudioSegment:
        # pydub lanza ValueError si el crossfade supera la duración de
        # cualquiera de los dos segmentos (chunks cortos o vacíos).
        cf = min(crossfade_ms, len(left), len(right))
        return left.append(right, crossfade=cf)

    result: AudioSegment | None = None
    cursor_ms = 0
    for i, (start_ms, end_ms) in enumerate(spans):
        chunk = audio_segment[cursor_ms:start_ms]
        if len(chunk) > 0:
            result = chunk if result is None else join(result, chunk)
        cursor_ms = end_ms
        if progress_callback:
            progress_callback((i + 1) / len(spans))

    tail = audio_segment[cursor_ms:]
    if len(tail) > 0:
        result = tail if result is None else join(result, tail)

    if result is None:  # se eliminó todo el audio
        return audio_segment[:0]
    return result


# ---------------------------------------------------------------------------
# Capa de Exportación
# ---------------------------------------------------------------------------

def export_audio(
    audio_segment: AudioSegment,
    output_path: Path,
    format: str = "wav",
) -> Path:
    """Exporta el audio procesado preservando los parámetros originales."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    audio_segment.export(str(output_path), format=format)
    return output_path


# ---------------------------------------------------------------------------
# Previsualización (decimación para la forma de onda)
# ---------------------------------------------------------------------------

def generate_waveform_data(
    audio_segment: AudioSegment,
    max_points: int = 1000,
) -> list[float]:
    """Submuestrea la señal a ~`max_points` picos normalizados (0..1),
    uno por pixel aproximado, para dibujar la forma de onda sin cargar
    la señal completa en el navegador."""
    samples = np.array(audio_segment.get_array_of_samples(), dtype=np.float32)
    channels = audio_segment.channels
    if channels > 1:
        usable = (len(samples) // channels) * channels
        samples = samples[:usable].reshape(-1, channels).mean(axis=1)
    bucket = max(1, math.ceil(len(samples) / max_points))
    trimmed = samples[: (len(samples) // bucket) * bucket]
    if trimmed.size == 0:
        return [0.0]
    peaks = np.abs(trimmed.reshape(-1, bucket)).max(axis=1)
    full_scale = float(2 ** (audio_segment.sample_width * 8 - 1))
    return (peaks / full_scale).tolist()
