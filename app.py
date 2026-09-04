"""EliminaMuletillas — Editor de audio con detección de muletillas.

Flujo lineal y ordenado:
  1. Subir audio → 2. Escuchar y revisar (onda + karaoke + detecciones)
     → 3. Guardar el resultado.
"""
from __future__ import annotations

import html
import time
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import database
from audio_processor import (
    DEFAULT_CROSSFADE_MS,
    apply_filters,
    export_audio,
    generate_waveform_data,
    load_audio,
    read_header,
    transcribe_with_timestamps,
)
from detection import mark_fillers
from models import DEFAULT_FILLERS, FillerConfig, Project, WordTimestamp

st.set_page_config(
    page_title="EliminaMuletillas",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DEFAULT_EXPORT_DIR = Path(__file__).parent / "exports"

# ---------------------------------------------------------------------------
# Estado de sesión
# ---------------------------------------------------------------------------
ss = st.session_state
ss.setdefault("config", FillerConfig())
ss.setdefault("project", None)        # Project | None
ss.setdefault("audio", None)          # AudioSegment
ss.setdefault("words", None)          # list[WordTimestamp]
ss.setdefault("wave_data", None)      # list[float]
ss.setdefault("current_time", 0.0)
ss.setdefault("last_export", None)    # ruta del último audio exportado


def eta_text(pct: float, started_at: float) -> str:
    """Texto de progreso con tiempo estimado de finalización."""
    pct = max(pct, 0.001)
    elapsed = time.time() - started_at
    eta = elapsed / pct * (1 - pct)
    return (
        f"{pct * 100:.0f}% completado · transcurrido {elapsed / 60:.1f} min · "
        f"quedan ~{eta / 60:.1f} min"
    )


def _browse_folder() -> str | None:
    """Abre el explorador nativo de Windows para elegir una carpeta."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.update()
        chosen = filedialog.askdirectory(
            parent=root, title="Elige la carpeta de exportación"
        )
        root.destroy()
        return chosen or None
    except Exception:
        return None


def inject_theme() -> None:
    """Tema claro estilo estudio editorial: tipografía, colores y tarjetas."""
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,600;0,9..144,700;1,9..144,400;1,9..144,600&family=Karla:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap');

:root {
  --paper: #FAF5EC;
  --card: #FFFDF8;
  --ink: #2E2722;
  --muted: #8A7F72;
  --line: #E8DFD0;
  --accent: #D9603A;
  --accent-dark: #B84A2A;
  --red: #C0452F;
  --sage: #4E7C6B;
}

.stApp {
  background:
    radial-gradient(1200px 500px at 85% -10%, rgba(217,96,58,0.08), transparent 60%),
    radial-gradient(900px 420px at -10% 15%, rgba(78,124,107,0.07), transparent 55%),
    var(--paper);
  font-family: 'Karla', system-ui, sans-serif;
  color: var(--ink);
}
[data-testid="stMainBlockContainer"] {
  max-width: 860px;
  padding-top: 2.6rem;
  padding-bottom: 4rem;
}
[data-testid="stHeader"] { background: transparent; }

h1, h2, h3, h4 { font-family: 'Fraunces', Georgia, serif; color: var(--ink); }
p, label, .stMarkdown, [data-testid="stWidgetLabel"] { font-family: 'Karla', system-ui, sans-serif; }

/* ---- Hero compacto ---- */
.hero { padding: 0.2rem 0 0.4rem; }
.hero-kicker {
  font-size: 0.68rem; letter-spacing: 0.26em; text-transform: uppercase;
  color: var(--accent-dark); font-weight: 700; margin-bottom: 0.15rem;
}
.hero-title { font-size: 2.55rem; line-height: 1.1; margin: 0; font-weight: 700; }
.hero-title span { font-style: italic; font-weight: 600; color: var(--accent); }
.hero-sub { color: var(--muted); font-size: 0.98rem; max-width: 640px; margin-top: 0.35rem; }
.hero-status {
  float: right; margin-top: -2.2rem; color: var(--accent-dark);
  font-size: 0.72rem; font-weight: 700; letter-spacing: 0.16em;
  text-transform: uppercase;
}

/* ---- Títulos de sección ---- */
.section-title {
  display: flex; align-items: center; gap: 0.55rem;
  font-family: 'Fraunces', Georgia, serif; font-size: 1.3rem; font-weight: 600;
  color: var(--ink); margin: 0.3rem 0 0.6rem;
}
.section-title .badge {
  font-family: 'Karla', sans-serif; font-size: 0.62rem; font-weight: 700;
  letter-spacing: 0.16em; text-transform: uppercase; color: var(--accent-dark);
  background: rgba(217,96,58,0.12); border-radius: 999px; padding: 0.18rem 0.55rem;
}

/* ---- Sidebar ---- */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #F6EFE3, #F1E8D8);
  border-right: 1px solid var(--line);
}
[data-testid="stSidebar"] .sb-label {
  font-size: 0.66rem; letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--accent-dark); font-weight: 700; margin: 0.7rem 0 0.2rem;
}
[data-testid="stSidebar"] .stCheckbox { margin-bottom: 0.1rem; }

/* ---- Tarjetas ---- */
[data-testid="stVerticalBlockBorderWrapper"] {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 18px;
  box-shadow: 0 6px 24px rgba(46,39,34,0.06);
  padding: 0.9rem 1rem;
}
[data-testid="stExpander"] {
  background: var(--card); border: 1px solid var(--line);
  border-radius: 14px; box-shadow: 0 4px 16px rgba(46,39,34,0.05);
}

/* ---- Botones ---- */
[data-testid="stBaseButton-primary"] {
  background: var(--accent); border: none; border-radius: 12px;
  font-weight: 700; font-size: 0.95rem; color: #fff;
  box-shadow: 0 4px 14px rgba(217,96,58,0.35);
  transition: transform 0.12s ease, box-shadow 0.12s ease;
}
[data-testid="stBaseButton-primary"]:hover {
  background: var(--accent-dark); transform: translateY(-1px);
  box-shadow: 0 6px 18px rgba(217,96,58,0.45);
}
[data-testid="stBaseButton-secondary"] {
  background: transparent; border: 1.5px solid var(--line);
  border-radius: 12px; color: var(--ink); font-weight: 600;
  transition: border-color 0.12s ease, color 0.12s ease;
}
[data-testid="stBaseButton-secondary"]:hover {
  border-color: var(--accent); color: var(--accent-dark);
}

/* ---- Inputs ---- */
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input {
  background: #fff; border: 1.5px solid var(--line); border-radius: 12px;
  color: var(--ink);
}
[data-testid="stFileUploaderDropzone"] {
  background: #fff; border: 2px dashed var(--line); border-radius: 16px;
  transition: border-color 0.15s ease, background 0.15s ease;
}
[data-testid="stFileUploaderDropzoneInstructions"] {
  color: var(--muted);
}
[data-testid="stFileUploaderDropzone"]:hover { border-color: var(--accent); background: #FFF7F0; }
[data-testid="stSelectbox"] [data-baseweb="select"] > div {
  background: #fff; border: 1.5px solid var(--line); border-radius: 12px;
}

/* ---- Slider y progreso ---- */
[data-testid="stSlider"] [role="slider"] { background: var(--accent); }
.stProgress > div > div > div { background: linear-gradient(90deg, var(--accent), #E8833A); border-radius: 8px; }

/* ---- Alerts ---- */
[data-testid="stAlert"] { border-radius: 14px; border: 1px solid var(--line); }

/* ---- Audio ---- */
audio { border-radius: 14px; width: 100%; border: 1px solid var(--line); }

/* ---- Transcripción karaoke (claro) ---- */
.transcript {
  max-height: 380px; overflow-y: auto; line-height: 2.25;
  font-size: 1.02rem; padding: 1rem 1.1rem; border-radius: 14px;
  background: #fff; border: 1px solid var(--line); color: var(--ink);
}
.transcript .f { text-decoration: line-through; color: var(--red); background: #FBE9E4; border-radius: 4px; padding: 1px 4px; }
.transcript .f.ignored { text-decoration: none; color: var(--sage); background: #EAF2EE; font-style: italic; }
.transcript .active { background: var(--accent); color: #fff !important; border-radius: 5px; padding: 1px 5px; box-shadow: 0 2px 8px rgba(217,96,58,0.45); }
.transcript .nt { color: var(--muted); background: #F3EDE2; border-radius: 4px; padding: 1px 4px; font-style: italic; }

/* ---- Chips "muletillas cercanas" ---- */
.chip {
  display: inline-flex; align-items: center; gap: 0.4rem;
  border-radius: 999px; padding: 0.28rem 0.75rem; margin: 0.15rem 0.3rem 0.15rem 0;
  font-size: 0.85rem; font-weight: 600; border: 1px solid var(--line); background: #fff;
}
.chip .t { color: var(--muted); font-variant-numeric: tabular-nums; font-weight: 500; }
.chip.remove { color: var(--red); border-color: #F0D3CB; background: #FDF3F0; }
.chip.keep { color: var(--sage); border-color: #D5E3DC; background: #F1F7F4; }

/* ---- Leyenda ---- */
.legend { display: flex; flex-wrap: wrap; gap: 0.9rem; font-size: 0.8rem; color: var(--muted); margin-top: 0.3rem; }
.legend .dot { display: inline-block; width: 11px; height: 11px; border-radius: 3px; margin-right: 0.3rem; }
.legend .d-red { background: var(--red); }
.legend .d-sage { background: var(--sage); }
.legend .d-gray { background: #C9BFAE; }

/* ---- Celdas de la tabla ---- */
[data-testid="stDataFrame"] { border-radius: 12px; border: 1px solid var(--line); overflow: hidden; }

/* ---- Captions ---- */
[data-testid="stCaptionContainer"] { color: var(--muted); }
</style>
""",
        unsafe_allow_html=True,
    )


def section(title: str, badge: str = "") -> None:
    badge_html = f'<span class="badge">{badge}</span>' if badge else ""
    st.markdown(
        f'<div class="section-title">{badge_html}{title}</div>',
        unsafe_allow_html=True,
    )


inject_theme()

# ---------------------------------------------------------------------------
# SIDEBAR — solo muletillas y calidad (limpia y sin ruido)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<p class="sb-label">Configuración</p>',
                unsafe_allow_html=True)
    st.caption("Personaliza las frases que quieres detectar.")

    with st.expander(
        f"🗣️ Frases activas · {len(ss.config.phrases)}",
        expanded=False,
    ):
        st.caption("Desmarca una frase para dejar de buscarla.")
        changed = False
        for phrase in sorted(ss.config.phrases):
            keep = st.checkbox(phrase, value=True, key=f"cb_{phrase}")
            if not keep:
                ss.config.remove(phrase)
                changed = True
        if changed:
            if ss.words is not None:
                mark_fillers(ss.words, ss.config)
            st.rerun()

        new_filler = st.text_input(
            "Añadir una frase nueva",
            placeholder="ej: la verdad es que",
            key="new_filler_input",
        )
        c_add, c_reset = st.columns([1, 1])
        if c_add.button(
            "➕ Añadir", use_container_width=True, disabled=not new_filler
        ):
            if ss.config.add(new_filler):
                if ss.words is not None:
                    mark_fillers(ss.words, ss.config)
                st.rerun()
            else:
                st.warning("Ya existe en la lista o está vacía.")
        if c_reset.button("♻️ Restaurar", use_container_width=True):
            for phrase in list(ss.config.phrases):
                ss.config.remove(phrase)
            for phrase in DEFAULT_FILLERS:
                ss.config.add(phrase)
            if ss.words is not None:
                mark_fillers(ss.words, ss.config)
            st.rerun()

    with st.expander("⚙️ Calidad del análisis", expanded=False):
        model_labels = {
            "Rápido": "tiny",
            "Equilibrado (recomendado)": "small",
            "Más preciso": "medium",
        }
        model_size = model_labels[
            st.selectbox("Calidad del análisis", list(model_labels), index=1)
        ]

# Carpeta de destino por defecto (se puede cambiar en el Paso 3 de la app).
export_dir_str = str(DEFAULT_EXPORT_DIR)

# ---------------------------------------------------------------------------
# Cabecera
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="hero">
      <div class="hero-kicker">Estudio de audio · Castellano</div>
      <h1 class="hero-title">Elimina <span>muletillas</span></h1>
      <div class="hero-status">● 100% local</div>
      <p class="hero-sub">
        Transcribe tu grabación, revisa cada «eh» u «o sea» y exporta una
        versión limpia, sin cortes bruscos.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# PASO 1 — Subir audio (solo cuando aún no hay análisis)
# ---------------------------------------------------------------------------
if ss.words is None:
    section("Sube tu grabación", "Paso 1")
    uploaded = st.file_uploader(
        "Elige un archivo de audio (MP3, WAV, M4A u OGG — hasta 2 GB)",
        type=["mp3", "wav", "m4a", "ogg", "flac"],
        label_visibility="collapsed",
    )

    if uploaded is not None:
        with st.spinner("Leyendo el audio..."):
            tmp_path = Path("uploads") / uploaded.name
            tmp_path.parent.mkdir(exist_ok=True)
            tmp_path.write_bytes(uploaded.getbuffer())

            header = read_header(tmp_path)
            mins = header["duration"] / 60
            dur_txt = (f"{mins:.1f} minutos" if mins >= 1
                       else f"{header['duration']:.1f} segundos")
            st.info(f"🎵 Audio cargado: **{dur_txt}** — listo para analizar.")

        if st.button("🚀 Empezar el análisis", type="primary",
                     use_container_width=True):
            progress = st.progress(0.0, text="Preparando...")
            started_at = time.time()

            def on_progress(pct: float) -> None:
                progress.progress(pct, text=f"Transcribiendo · {eta_text(pct, started_at)}")

            audio = load_audio(tmp_path)
            words = transcribe_with_timestamps(
                tmp_path, on_progress, model_size=model_size
            )
            mark_fillers(words, ss.config)

            ss.project = Project(
                id=None,
                original_path=tmp_path,
                duration=header["duration"],
                sample_rate=header["sample_rate"],
                channels=header["channels"],
                bit_depth=header["bit_depth"],
            )
            ss.audio = audio
            ss.words = words
            ss.wave_data = generate_waveform_data(audio, max_points=1000)
            progress.progress(1.0, text="Análisis completado.")
            st.rerun()

# ---------------------------------------------------------------------------
# PASOS 2 y 3 — Escuchar/revisar y guardar
# ---------------------------------------------------------------------------
if ss.words is not None:
    words: list[WordTimestamp] = ss.words
    fillers = [w for w in words if w.is_filler]

    # -- 2a · Forma de onda + reproductor (ancho completo) -------------------
    section("Escucha la grabación", "Paso 2")
    with st.container(border=True):
        marked = [w for w in fillers if w.will_remove]
        kept = [w for w in fillers if not w.will_remove]
        untranscribed = [w for w in words if w.text == "[No transcrito]"]

        fig = go.Figure()
        duration = ss.project.duration
        xs = [i / max(1, len(ss.wave_data) - 1) * duration
              for i in range(len(ss.wave_data))]
        fig.add_trace(
            go.Scatter(
                x=xs, y=ss.wave_data, mode="lines", fill="tozeroy",
                line={"color": "#D9603A", "width": 1.4},
                fillcolor="rgba(217,96,58,0.16)", name="amplitud",
                hoverinfo="skip",
            )
        )
        for w in marked:
            fig.add_vrect(
                x0=w.start, x1=w.end, fillcolor="rgba(192,69,47,0.30)",
                line_width=0, annotation_text="✂", annotation_font_size=9,
            )
        for w in kept:
            fig.add_vrect(
                x0=w.start, x1=w.end, fillcolor="rgba(78,124,107,0.22)",
                line_width=0,
            )
        for w in untranscribed:
            fig.add_vrect(
                x0=w.start, x1=w.end, fillcolor="rgba(138,127,114,0.18)",
                line_width=0, annotation_text="?", annotation_font_size=9,
            )
        fig.add_vline(x=ss.current_time, line_color="#B84A2A", line_width=2)
        fig.update_layout(
            height=230,
            margin={"l": 0, "r": 0, "t": 10, "b": 0},
            xaxis_title="segundos", yaxis_title="",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font={"family": "Karla", "color": "#8A7F72"},
            xaxis={"gridcolor": "#F0E8DC", "zerolinecolor": "#E8DFD0"},
            yaxis={"gridcolor": "#F5EEE2", "visible": False},
            showlegend=False,
        )
        event = st.plotly_chart(
            fig, use_container_width=True, key="waveform_chart",
            on_select="rerun", selection_mode="points",
        )
        points = event.selection.get("points", []) if event else []
        if points and points[0].get("x") is not None:
            ss.current_time = float(points[0]["x"])
            st.rerun()

        st.markdown(
            '<div class="legend">'
            '<span><span class="dot d-red"></span>se elimina</span>'
            '<span><span class="dot d-sage"></span>se conserva</span>'
            '<span><span class="dot d-gray"></span>sin transcribir</span>'
            "</div>",
            unsafe_allow_html=True,
        )
        st.audio(str(ss.project.original_path),
                 start_time=int(ss.current_time * 1000))

    # -- 2b · Transcripción karaoke + detecciones ----------------------------
    col_text, col_cfg = st.columns([1.6, 1])

    with col_text:
        section("Transcripción en vivo")
        with st.container(border=True):
            ss.current_time = st.slider(
                "Tiempo (s)", 0.0, max(ss.project.duration, 0.1),
                ss.current_time, step=0.1,
            )

            parts: list[str] = []
            for w in words:
                escaped = html.escape(w.text)
                if w.text == "[No transcrito]":
                    parts.append(
                        f'<span class="nt" title="{w.start:.1f}s">{escaped}</span> '
                    )
                elif w.is_filler:
                    if w.start <= ss.current_time <= w.end:
                        parts.append(f'<span class="f active">{escaped}</span> ')
                    else:
                        cls = "f removed" if w.will_remove else "f ignored"
                        parts.append(f'<span class="{cls}">{escaped}</span> ')
                elif w.start <= ss.current_time <= w.end:
                    parts.append(f'<span class="active">{escaped}</span> ')
                else:
                    parts.append(f"<span>{escaped}</span> ")
            st.markdown(
                f'<div class="transcript">{"".join(parts)}</div>',
                unsafe_allow_html=True,
            )

            st.markdown("**⏱️ Muletillas cercanas**")
            nearby = sorted(fillers, key=lambda w: abs(w.start - ss.current_time))[:20]
            chips = []
            for w in sorted(nearby, key=lambda w: w.start):
                cls = "chip remove" if w.will_remove else "chip keep"
                icon = "✂️" if w.will_remove else "👍"
                chips.append(
                    f'<span class="{cls}"><span class="t">{w.start:6.2f}s</span>'
                    f'{icon} {html.escape(w.text)}</span>'
                )
            st.markdown("".join(chips) if chips else "_Sin muletillas cerca._",
                        unsafe_allow_html=True)

    with col_cfg:
        section("Detecciones", f"{len(fillers)}")
        with st.container(border=True):
            if fillers:
                st.caption("Desmarca «quitar» para conservar una muletilla concreta.")
                df = pd.DataFrame(
                    {
                        "quitar": [w.will_remove for w in fillers],
                        "muletilla": [w.text for w in fillers],
                        "inicio (s)": [round(w.start, 2) for w in fillers],
                        "confianza": [round(w.confidence, 2) for w in fillers],
                        "_idx": [words.index(w) for w in fillers],
                    }
                )
                edited = st.data_editor(
                    df,
                    column_order=["quitar", "muletilla", "inicio (s)", "confianza"],
                    column_config={
                        "quitar": st.column_config.CheckboxColumn("quitar", default=True),
                        "confianza": st.column_config.ProgressColumn(
                            "confianza", min_value=0.0, max_value=1.0
                        ),
                    },
                    hide_index=True,
                    height=380,
                    key="filler_editor",
                )
                for _, row in edited.iterrows():
                    words[int(row["_idx"])].will_remove = bool(row["quitar"])
            else:
                st.success("No se detectaron muletillas con tu lista actual. 🎉")

    # -- 3 · Guardar ----------------------------------------------------------
    section("Guarda el resultado", "Paso 3")
    with st.container(border=True):
        c_loc, c_path = st.columns([1, 2])
        with c_loc:
            st.markdown("**¿Dónde guardarlo?**")
            home = Path.home()
            quick_options = {
                "(sin cambio)": None,
                "Proyecto (exports)": str(DEFAULT_EXPORT_DIR),
                "Escritorio": str(home / "Desktop"),
                "Documentos": str(home / "Documents"),
                "Música": str(home / "Music"),
                "Descargas": str(home / "Downloads"),
            }
            quick = st.selectbox("Ubicaciones rápidas", list(quick_options),
                                 key="quick_loc", label_visibility="collapsed")
            if quick_options[quick] and ss.get("_applied_quick") != quick:
                ss["export_dir_input"] = quick_options[quick]
                ss["_applied_quick"] = quick
                st.rerun()
            if st.button("🖥️ Explorar carpetas...", use_container_width=True,
                         help="Abre el explorador de Windows para elegir la carpeta"):
                chosen = _browse_folder()
                if chosen:
                    ss["export_dir_input"] = chosen
                    st.rerun()
                else:
                    st.warning("No se pudo abrir el explorador; escribe la ruta manualmente.")
        with c_path:
            st.markdown("**O escribe la ruta**")
            export_dir_str = st.text_input(
                "Carpeta de destino",
                value=str(DEFAULT_EXPORT_DIR),
                key="export_dir_input",
                label_visibility="collapsed",
            )
            suavizar = st.checkbox(
                "Suavizar los cortes (evita chasquidos)",
                value=True,
                help="Une los trozos con una micro-transición de 25 ms para que "
                     "no se oigan 'clicks'. Recomendado siempre activo.",
            )
            crossfade = DEFAULT_CROSSFADE_MS if suavizar else 0

        export_dir = Path(export_dir_str.strip() or str(DEFAULT_EXPORT_DIR))
        st.caption(f"📂 Se guardará como `{export_dir / (ss.project.original_path.stem + '_limpio.wav')}`")

        if st.button("💾 Generar audio limpio", type="primary",
                     use_container_width=True):
            to_remove = [w for w in words if w.is_filler and w.will_remove]
            if not to_remove:
                st.warning("No hay muletillas marcadas para eliminar.")
            else:
                try:
                    progress = st.progress(0.0, text="Cortando...")
                    started_at = time.time()

                    def on_cut(pct: float) -> None:
                        progress.progress(
                            pct, text=f"Cortando · {eta_text(pct, started_at)}"
                        )

                    clean = apply_filters(
                        ss.audio, to_remove, crossfade_ms=int(crossfade),
                        progress_callback=on_cut,
                    )
                    out = export_audio(
                        clean,
                        export_dir / f"{ss.project.original_path.stem}_limpio.wav",
                    )
                    progress.progress(1.0, text="Guardado completado.")
                    if ss.project.id is None:
                        ss.project.id = database.save_project(
                            ss.project.original_path, ss.project.duration,
                            ss.project.sample_rate, ss.project.channels,
                            ss.project.bit_depth,
                        )
                        database.set_export_path(ss.project.id, out)
                    ss.last_export = str(out)
                    st.success(f"✅ Audio limpio guardado en:\n\n`{out.resolve()}`")
                except (OSError, PermissionError) as exc:
                    st.error(
                        f"No se pudo guardar en `{export_dir}`: {exc}. "
                        "Prueba con otra carpeta."
                    )

        if ss.last_export and Path(ss.last_export).exists():
            out_path = Path(ss.last_export)
            st.download_button(
                "⬇️ Descargar audio limpio",
                data=out_path.read_bytes(),
                file_name=out_path.name,
                mime="audio/wav",
                use_container_width=True,
            )
            st.caption(f"Último archivo: `{out_path.resolve()}`")

# ---------------------------------------------------------------------------
# Historial (SQLite)
# ---------------------------------------------------------------------------
with st.expander("📚 Proyectos anteriores"):
    rows = database.list_projects()
    if rows:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "id": r["id"],
                        "archivo": Path(r["original_path"]).name,
                        "minutos": round(r["duration"] / 60, 1),
                        "Hz": r["sample_rate"],
                        "canales": r["channels"],
                        "bits": r["bit_depth"],
                        "exportado": r["export_path"] or "—",
                    }
                    for r in rows
                ],
            ),
            hide_index=True,
        )
    else:
        st.write("Todavía no hay proyectos guardados.")
