# EliminaMuletillas 🎙️

Editor y automatizador de audio para **Windows** que detecta y elimina **muletillas en castellano** ("eh", "este", "o sea", "bueno", …) en grabaciones narrativas (partidas de D&D, audiolibros, podcasts), con **transcripción sincronizada** para auditar cada detección antes de exportar.

> Funciona 100 % local: tu audio nunca sale del equipo. No abre el navegador: se ejecuta en su propia ventana de escritorio.

## Características

- **Transcripción local** con Whisper (`word_timestamps=True`) y barra de progreso con tiempo estimado.
- **Lista de muletillas editable** desde la UI o editando `filler_words.json` — sin tocar código y sin re-transcribir.
- **Forma de onda interactiva** con marcadores: rojo = se elimina, verde = se conserva, gris = sin transcribir.
- **Karaoke sincronizado**: la transcripción se desplaza y resalta la palabra que suena en ese segundo.
- **Auditoría visual**: desmarca cualquier detección para conservarla, sin re-procesar el audio.
- **Cortes suaves**: crossfade de 25 ms por defecto (sin chasquidos); el original nunca se modifica.
- **Soporta sesiones largas** (hasta 2 GB): cortes por índices de frames, onda decimada a ~1000 puntos.
- **Ventana nativa** (WebView2) sin navegador; cae al navegador solo si falta el runtime.

## Requisitos

| Requisito | Detalle |
|---|---|
| Sistema | Windows 10/11 de 64 bits |
| Python | 3.11 (dev) — el portable lleva su runtime embebido |
| ffmpeg | En PATH (incluido en `bin\` del portable) |
| Internet | Solo para la **primera** descarga del modelo Whisper (~460 MB) |

## Uso (versión portable)

1. Descomprime `EliminaMuletillas_Portable_Windows.zip`.
2. Doble clic en `EliminaMuletillas.exe`.
3. Sube un audio (MP3, WAV, M4A, OGG) → **Empezar el análisis** → revisa las detecciones → **Generar audio limpio**.

Instrucciones para el usuario final: `EliminaMuletillas_Portable\LEEME.txt`.

## Desarrollo

```cmd
:: Instalar dependencias
.venv\Scripts\python.exe -m pip install -r requirements.txt

:: Modo navegador (Streamlit puro)
.venv\Scripts\python.exe -m streamlit run app.py

:: Modo ventana nativa (recomendado)
.venv\Scripts\python.exe launcher.py
```

No hay lint ni suite de tests configurados; la verificación es manual con `demo_speech.wav`.

## Documentación

| Documento | Contenido |
|---|---|
| `AGENTS.md` / `CLAUDE.md` | Guía operativa para agentes de IA que trabajen en el repo |
| `docs/architecture.md` | Arquitectura en capas, módulos y flujo de datos |
| `docs/current-state.md` | Estado actual, qué funciona y qué hay que saber |
| `docs/decisions/` | Registro de Decisiones de Arquitectura (ADR) |

## Estructura

```
proyecto/
├── AGENTS.md / CLAUDE.md / README.md
├── app.py                  # UI Streamlit (única capa de presentación)
├── audio_processor.py      # Adquisición + Análisis + Edición + Exportación
├── detection.py            # Marcado de muletillas (en memoria)
├── models.py               # Dataclasses + FillerConfig (filler_words.json)
├── database.py             # SQLite (projects.db)
├── filler_words.json       # Lista de muletillas editable
├── launcher.py             # Ventana nativa (WebView2)
├── docs/
├── exports/                # Audio procesado (el original no se toca)
└── EliminaMuletillas_Portable/   # Build portable (exe + runtime + bin)
```
