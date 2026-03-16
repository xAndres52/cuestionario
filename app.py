import streamlit as st
import pdfplumber
import re
import random

st.set_page_config(page_title="Simulador Médico", layout="wide")

# ---------- SESSION ----------
if "preguntas" not in st.session_state:
    st.session_state.preguntas = []
if "examen" not in st.session_state:
    st.session_state.examen = []
if "respuestas" not in st.session_state:
    st.session_state.respuestas = {}
if "historial" not in st.session_state:
    st.session_state.historial = []
if "fase" not in st.session_state:
    st.session_state.fase = "inicio"


# ---------- EXTRAER TEXTO ----------
def leer_pdf(pdf):
    texto = ""
    with pdfplumber.open(pdf) as pdf_doc:
        for page in pdf_doc.pages:
            contenido = page.extract_text()
            if contenido:
                texto += contenido + "\n"
    return texto


# ---------- PARSER ----------
def extraer_preguntas(texto):
    """
    Formato del PDF CTO:

    Info Pregunta: <uuid>

    N. Enunciado de la pregunta...:
    1. Opción A
    2. Opción B
    3. Opción C
    4. Opción D
    Resp. Correcta: 2
    Comentario: Texto...
    ---o---
    """
    preguntas = []
    bloques = re.split(r"Info Pregunta:\s*[a-f0-9\-]+", texto)

    for bloque in bloques:
        if "Resp. Correcta:" not in bloque:
            continue
        try:
            # Aislar sólo la parte pregunta+opciones (antes de Resp. Correcta)
            resp_pos = bloque.index("Resp. Correcta:")
            question_part = bloque[:resp_pos]
            lines = question_part.split("\n")

            # Encontrar dónde empiezan las opciones:
            # buscamos la línea "1. ..." que esté seguida de líneas "2. " "3. " "4. "
            opts_start_line = None
            for j in range(len(lines) - 3):
                l = lines[j].strip()
                if re.match(r"^1\. ", l):
                    resto = "\n".join(lines[j:])
                    if (re.search(r"^2\. ", resto, re.MULTILINE) and
                            re.search(r"^3\. ", resto, re.MULTILINE) and
                            re.search(r"^4\. ", resto, re.MULTILINE)):
                        opts_start_line = j  # guardamos el último que cumpla

            if opts_start_line is None:
                continue

            # Enunciado: líneas anteriores a las opciones
            enunciado_lines = lines[:opts_start_line]
            enunciado_raw = " ".join(l.strip() for l in enunciado_lines if l.strip())
            enunciado = re.sub(r"^\s*\d+\.\s*", "", enunciado_raw, count=1).strip()

            # Caso especial: número de pregunta = 1
            # (la línea "1. Enunciado:" queda incluida en las opciones)
            if not enunciado:
                primera_linea = lines[opts_start_line].strip()
                if primera_linea.endswith(":"):
                    enunciado = re.sub(r"^\d+\.\s*", "", primera_linea).strip()
                    opts_start_line += 1
                    # Re-buscar la línea real de opción 1
                    for j in range(opts_start_line, len(lines)):
                        if re.match(r"^\s*1\. ", lines[j]):
                            opts_start_line = j
                            break

            # Parsear opciones (pueden ser multilínea)
            opts_text = "\n".join(lines[opts_start_line:])
            partes = re.split(r"\n(?=\d+\. )", opts_text)
            opciones = []
            for p in partes:
                op = re.sub(r"^\d+\.\s*", "", p.strip())
                op = re.sub(r"\s*\n\s*", " ", op).strip()
                if op:
                    opciones.append(op)

            if len(opciones) < 4:
                continue

            # Respuesta correcta
            correcta_match = re.search(r"Resp\.\s*Correcta:\s*(\d+)", bloque)
            if not correcta_match:
                continue
            correcta = int(correcta_match.group(1)) - 1
            if correcta >= len(opciones):
                continue

            # Comentario
            comentario = ""
            com_match = re.search(r"Comentario:\s*(.+?)(?=\n-{5,}|\Z)", bloque, re.S)
            if com_match:
                comentario = re.sub(r"\s*\n\s*", " ", com_match.group(1).strip())

            preguntas.append({
                "pregunta": enunciado,
                "opciones": opciones[:4],
                "correcta": correcta,
                "comentario": comentario
            })

        except Exception:
            pass

    return preguntas


def generar_examen():
    total = len(st.session_state.preguntas)
    disponibles = [i for i in range(total) if i not in st.session_state.historial]

    if len(disponibles) < 50:
        st.session_state.historial = []
        disponibles = list(range(total))

    seleccion = random.sample(disponibles, min(50, len(disponibles)))
    st.session_state.examen = seleccion
    st.session_state.historial += seleccion
    st.session_state.respuestas = {}
    st.session_state.fase = "examen"


# ============================================================
# FASE: INICIO
# ============================================================
if st.session_state.fase == "inicio":
    st.title("🫀 Simulador de Examen Médico")

    # Si ya hay un banco cargado, ofrecer continuar
    if len(st.session_state.preguntas) > 0:
        st.success(f"Banco cargado: **{len(st.session_state.preguntas)} preguntas**")
        respondidas = len(st.session_state.historial)
        pendientes = len(st.session_state.preguntas) - respondidas
        st.info(f"Preguntas ya vistas: {respondidas} | Pendientes: {pendientes}")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Generar nuevas 50 preguntas", type="primary"):
                generar_examen()
                st.rerun()
        with col2:
            if st.button("📂 Cargar nuevo PDF"):
                st.session_state.preguntas = []
                st.session_state.historial = []
                st.rerun()

    else:
        st.header("Cargar banco de preguntas")
        pdf = st.file_uploader("Sube tu PDF", type="pdf")

        if pdf:
            with st.spinner("Leyendo PDF..."):
                texto = leer_pdf(pdf)
                preguntas = extraer_preguntas(texto)

            if len(preguntas) == 0:
                st.error("No se pudieron detectar preguntas en el PDF.")
                with st.expander("Ver texto extraído (para depurar)"):
                    st.text(texto[:3000])
            else:
                st.session_state.preguntas = preguntas
                st.success(f"✅ Se encontraron {len(preguntas)} preguntas")

                if st.button("Generar examen de 50 preguntas", type="primary"):
                    generar_examen()
                    st.rerun()


# ============================================================
# FASE: EXAMEN
# ============================================================
elif st.session_state.fase == "examen":
    st.title("🫀 Simulador de Examen Médico")
    st.header(f"Examen — {len(st.session_state.examen)} preguntas")

    if len(st.session_state.examen) == 0:
        st.warning("No hay preguntas generadas.")
        if st.button("Ir al inicio"):
            st.session_state.fase = "inicio"
            st.rerun()
    else:
        for i, idx in enumerate(st.session_state.examen):
            p = st.session_state.preguntas[idx]

            respuesta = st.radio(
                f"**{i+1}. {p['pregunta']}**",
                p["opciones"],
                key=f"pregunta_{i}",
                index=None
            )

            if respuesta is not None:
                st.session_state.respuestas[i] = respuesta

        st.divider()
        if st.button("✅ Terminar examen", type="primary"):
            st.session_state.fase = "resultados"
            st.rerun()


# ============================================================
# FASE: RESULTADOS
# ============================================================
elif st.session_state.fase == "resultados":
    st.title("🫀 Simulador de Examen Médico")
    st.header("Resultados del examen")

    puntaje = 0
    total = len(st.session_state.examen)

    for i, idx in enumerate(st.session_state.examen):
        p = st.session_state.preguntas[idx]
        correcta = p["opciones"][p["correcta"]]
        respuesta_usuario = st.session_state.respuestas.get(i, None)

        st.subheader(f"Pregunta {i+1}")
        st.write(p["pregunta"])

        if respuesta_usuario:
            st.write("**Tu respuesta:**", respuesta_usuario)
        else:
            st.write("**Tu respuesta:** *(sin responder)*")

        st.write("**Respuesta correcta:**", correcta)

        if respuesta_usuario == correcta:
            st.success("✔ Correcta")
            puntaje += 1
        else:
            st.error("❌ Incorrecta")

        if p["comentario"]:
            st.info(f"💬 {p['comentario']}")

        st.divider()

    # Puntaje final con color
    porcentaje = int(puntaje / total * 100)
    if porcentaje >= 70:
        st.success(f"🎯 Puntaje final: {puntaje} / {total}  ({porcentaje}%)")
    elif porcentaje >= 50:
        st.warning(f"🎯 Puntaje final: {puntaje} / {total}  ({porcentaje}%)")
    else:
        st.error(f"🎯 Puntaje final: {puntaje} / {total}  ({porcentaje}%)")

    st.divider()
    st.subheader("¿Qué quieres hacer ahora?")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🔄 Nuevo examen (mismo banco)", type="primary"):
            generar_examen()
            st.rerun()
    with col2:
        if st.button("📂 Cargar otro PDF"):
            st.session_state.preguntas = []
            st.session_state.historial = []
            st.session_state.examen = []
            st.session_state.respuestas = {}
            st.session_state.fase = "inicio"
            st.rerun()
    with col3:
        if st.button("🏠 Volver al inicio"):
            st.session_state.examen = []
            st.session_state.respuestas = {}
            st.session_state.fase = "inicio"
            st.rerun()