# CLAUDE.md

Guía para agentes de IA que trabajan en este repositorio. Para el detalle completo (arquitectura, decisiones y estado) consulta `AGENTS.md` y la carpeta `docs/`.

## Comandos

```cmd
:: Arrancar la app en desarrollo (navegador)
.venv\Scripts\python.exe -m streamlit run app.py

:: Modo ventana nativa (WebView2, sin navegador)
.venv\Scripts\python.exe launcher.py
```

No hay lint, formatter ni tests configurados. Verificación manual con `demo_speech.wav`.

## Reglas críticas (no negociables)

1. **Cero hardcoding de audio**: `sample_rate`/`channels`/`bit_depth` se leen del header real (`read_header`), nunca se asumen. MP3/M4A/OGG → WAV en memoria vía pydub (ffmpeg).
2. **Muletillas editables sin código**: `filler_words.json` (`{"fillers": [...]}`); `models.DEFAULT_FILLERS` es solo el seed inicial. Cambiar la lista re-ejecuta `mark_fillers` (milisegundos), **nunca** re-transcribe con Whisper.
3. **Sin audio completo en RAM**: cortes por índices de frames, onda decimada (~1000 picos). Debe soportar sesiones de 2 GB / 6 h.
4. **Cortes suaves**: crossfade de 25 ms (`DEFAULT_CROSSFADE_MS`); el archivo original nunca se modifica.
5. **Tolerancia a fallos**: tramos sin transcribir → `[No transcrito]` con `will_remove=False`, nunca se eliminan solos.
6. **UI**: solo modo claro (mandato del usuario); todo el texto en español; claves de widgets Streamlit únicas; no asignar claves de widgets vía `st.session_state` (`StreamlitValueAssignmentNotAllowedError`).
7. **Empaquetado**: no borrar/renombrar `runtime\` ni `bin\`; no tocar `python311._pth`; el exe no debe abrir el navegador (`--server.headless true`).
8. **GIT — REGLA OBLIGATORIA**: NUNCA ejecutes `git add`, `git commit` ni `git push` (tampoco force-push, borrado de ramas ni nada que publique o mute el historial) sin la autorización explícita del usuario. El usuario debe aprobar el alcance exacto de cada operación. `.gitignore` excluye `.venv/`, `EliminaMuletillas_Portable/`, `*.zip`, `build/`, `uploads/`, `exports/`, `projects.db` y demás artefactos de ejecución — no los añadas con `git add -f`.

## Trampas conocidas

- **Hook de tqdm de Whisper** (`audio_processor.py`): `whisper.transcribe` es una función que sombrea al módulo; se carga con `importlib.import_module("whisper.transcribe")` y se intercambia su `tqdm` por `_ProgressTqdm`. No "simplificar" sin retestar el progreso.
- **Widget keys de Streamlit**: la colisión de claves (p. ej. `quick_loc`) es un fallo recurrente; cada widget requiere una clave única.

## Arquitectura en 10 segundos

`app.py` (UI Streamlit, 3 pasos) → `audio_processor.py` (adquisición/Whisper/edición/exportación) → `detection.py` (marcado en memoria) ← `models.py` (FillerConfig → `filler_words.json`) → `database.py` (SQLite `projects.db`). `launcher.py` arranca Streamlit headless y lo muestra en una ventana WebView2.

Detalles: `docs/architecture.md` · `docs/current-state.md` · `docs/decisions/`.
