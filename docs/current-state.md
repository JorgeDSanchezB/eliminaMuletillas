# Estado actual — EliminaMuletillas

_Fecha de la última revisión: 2026-09-04_

## Qué está implementado y verificado ✅

- **Flujo completo de 3 pasos** en la UI: subir audio → revisar (onda + karaoke + detecciones) → exportar.
- **Transcripción Whisper** con `word_timestamps=True`, progreso con ETA (`st.progress` + `eta_text`) y modelos `tiny`/`small`/`medium` seleccionables.
- **Detección de muletillas re-ejecutable sin Whisper**: `mark_fillers` corre en milisegundos al añadir/eliminar frases (verificado por tiempos de respuesta < 1 s).
- **Lista de muletillas editable** desde la sidebar y vía `filler_words.json`; se persiste al instante.
- **Forma de onda interactiva** (Plotly, decimada a 1000 puntos) con marcadores por estado y seek al hacer clic.
- **Karaoke sincronizado** mediante slider de tiempo; muletillas tachadas en rojo, conservadas en verde, `[No transcrito]` en gris.
- **Auditoría por detección** (`st.data_editor` con checkbox "quitar") sin re-procesar el audio.
- **Exportación** con crossfade de 25 ms configurable ("Suavizar los cortes"), selector de carpeta nativo (tkinter), ubicaciones rápidas y registro en SQLite.
- **Ventana nativa sin navegador**: `launcher.py` con pywebview/WebView2, arranque headless en puerto libre (8501–8560), fallback al navegador, errores en `launcher.log`. **Verificado de punta a punta**: servidor saludable (`/_stcore/health → 200`) y ventana abierta con título "EliminaMuletillas".
- **Build portable** generado y verificado: `EliminaMuletillas_Portable\EliminaMuletillas.exe` + `EliminaMuletillas_Portable_Windows.zip` (≈470 MB) con `app/`, `runtime/`, `bin/` y `LEEME.txt` completos.

## Limitaciones y puntos a tener en cuenta ⚠️

- **Primer arranque con un modelo nuevo** descarga ~460 MB de internet (modelo `small` por defecto). Sin conexión no se puede transcribir.
- **Whisper puede fallar** en tramos con ruido/silencio: se marcan `[No transcrito]` y nunca se eliminan automáticamente (diseño intencional).
- **Dependencia de ffmpeg** para MP3/M4A/OGG (pydub). En desarrollo hay que tenerlo en `PATH`; en el portable vive en `bin\`.
- **WebView2 Runtime** necesario para la ventana nativa; si falta, el programa abre el navegador como plan B (no es un error del programa).
- **Streamlit widget keys**: las claves duplicadas causan `StreamlitDuplicateElementKey` (fallo recurrente ya corregido en `quick_loc`); cualquier widget nuevo necesita clave única. No asignar claves de widgets vía `st.session_state`.
- **`whisper.transcribe` está sombreado por una función**: el hook de `tqdm` en `audio_processor.py` es frágil por diseño; cambios ahí requieren retestar la barra de progreso.
- **El audio cargado vive en memoria** (`ss.audio`, `AudioSegment`): un único archivo a la vez por sesión; la edición usa slicing por índices para no reconstruir todo a mano.

## No implementado / pendiente (opcional)

- No hay suite de tests automatizada (solo verificación manual con `demo_speech.wav`).
- No hay lint/formateador configurado.
- No hay instalador clásico (solo ZIP portable).
- El proyecto no usa `src/` ni `tests/` como carpetas de código: los módulos viven planos en la raíz para mantener el empaquetado portable simple (`launcher.py` espera `app.py` junto a `runtime/`).

## Verificación manual rápida

```cmd
:: 1) Arrancar en desarrollo
.venv\Scripts\python.exe -m streamlit run app.py

:: 2) Subir demo_speech.wav, analizar, revisar, exportar
:: 3) Comprobar que exports/ contiene *_limpio.wav y el original sigue intacto
:: 4) Para el modo ventana: .venv\Scripts\python.exe launcher.py
```
