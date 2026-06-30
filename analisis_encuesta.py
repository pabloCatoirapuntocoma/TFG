#!/usr/bin/env python3
"""
analisis_encuesta.py — Análisis de encuesta TFG
"El Impacto De La IA En Las Empresas Del Sector Tecnológico"
Universidad Pontificia de Salamanca

Uso:
    python3 analisis_encuesta.py encuesta.csv          → menú interactivo
    python3 analisis_encuesta.py encuesta.csv -o resultado.txt
    python3 analisis_encuesta.py encuesta.csv -p informe.pdf
"""

import sys
import csv
import io
import os
import traceback
import tempfile
import shutil
from collections import Counter
from statistics import mean, median, mode, StatisticsError
from datetime import datetime

# ── Índices de columna ────────────────────────────────────────────────────────
COL = {
    "timestamp":       0,
    "edad":            1,
    "experiencia":     2,
    "sector":          3,
    "empresa_usa_ia":  4,
    "areas_ia":        5,
    "formacion_ia":    6,
    "uso_personal_ia": 7,
    "cambio_carga":    8,
    "automatizo":      9,
    "preocupacion":    10,
    "comentario":      11,
}

# ── Pesos IEA ─────────────────────────────────────────────────────────────────
PESO_EXPERIENCIA = {
    "Menos de 2 años": 3,
    "2-5 años":        2,
    "6-10 años":       1,
    "11-20 años":      1,
    "Más de 20 años":  0,
}
PESO_SECTOR = {
    "Comercio / Retail":                                  3,
    "Industria / Manufactura":                            3,
    "Administración pública":                             2,
    "Marketing / Comunicación":                           2,
    "Finanzas / Banca":                                   2,
    "Servicios profesionales (legal, consultoría, etc.)": 1,
    "Salud":                                              1,
    "Educación":                                          1,
    "Tecnología / IT":                                    1,
    "Otro":                                               1,
}
PESO_USO_IA = {
    "No, nunca":              2,
    "No, pero la he probado": 1,
    "Sí, de forma ocasional": 0,
    "Sí, habitualmente":      0,
}
PESO_AUTOMATIZO = {
    "Sí, bastantes": 2,
    "Sí, algunas":   1,
    "Apenas alguna": 0,
    "Ninguna":       0,
    "No utilizo IA": 1,
}

PALETA = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#44BBA4',
          '#E94F37', '#3B82B5', '#F5A623', '#7BC67E', '#9B59B6']

# Almacena el resultado de la última simulación IEA ejecutada
_ultima_simulacion = None


# ── Utilidades ────────────────────────────────────────────────────────────────

def get(fila, col):
    idx = COL[col]
    return fila[idx].strip() if idx < len(fila) else ""

def barra(valor, total, ancho=28):
    if total == 0:
        return "░" * ancho + "  0/0  (0.0%)"
    llenos = int(round((valor / total) * ancho))
    pct = 100 * valor / total
    return "█" * llenos + "░" * (ancho - llenos) + f"  {valor}/{total}  ({pct:.1f}%)"

def estrellas(valor, maximo=5, ancho=10):
    llenos = round((valor / maximo) * ancho) if maximo else 0
    return "★" * llenos + "☆" * (ancho - llenos) + f"   {valor:.2f} / {maximo:.0f}"

def sep(char="─", ancho=72):
    print(char * ancho)

def titulo(texto, nivel=1):
    if nivel == 1:
        sep("═")
        print(f"  {texto}")
        sep("═")
    else:
        sep()
        print(f"  {texto}")
        sep()

def calcular_iea(fila):
    s  = PESO_EXPERIENCIA.get(get(fila, "experiencia"), 1)
    s += PESO_SECTOR.get(get(fila, "sector"), 1)
    s += PESO_USO_IA.get(get(fila, "uso_personal_ia"), 1)
    s += PESO_AUTOMATIZO.get(get(fila, "automatizo"), 0)
    return min(s, 10)

def nivel_iea(score):
    if score <= 3:   return "BAJO "
    elif score <= 6: return "MEDIO"
    else:            return "ALTO "

def areas_flat_fn(datos):
    out = []
    for f in datos:
        a = get(f, "areas_ia")
        if a:
            out.extend([x.strip() for x in a.split(",") if x.strip()])
    return out

def preo_raw_fn(datos):
    vals = []
    for f in datos:
        try:
            vals.append(int(get(f, "preocupacion")))
        except ValueError:
            pass
    return vals

def calcular_stats(datos):
    n = len(datos)
    usa_ia     = Counter(get(f, "empresa_usa_ia") for f in datos)
    formacion  = Counter(get(f, "formacion_ia") for f in datos)
    uso_pers   = Counter(get(f, "uso_personal_ia") for f in datos)
    auto       = Counter(get(f, "automatizo") for f in datos)
    cambio     = Counter(get(f, "cambio_carga") for f in datos if get(f, "cambio_carga"))
    preo_raw   = preo_raw_fn(datos)
    areas_flat = areas_flat_fn(datos)
    scores     = [calcular_iea(f) for f in datos]

    pct_ia    = 100 * usa_ia.get("Sí", 0) / n
    pct_form  = 100 * formacion.get("Sí", 0) / n
    pct_hab   = 100 * uso_pers.get("Sí, habitualmente", 0) / n
    pct_auto  = 100 * (auto.get("Sí, bastantes", 0) + auto.get("Sí, algunas", 0)) / n
    preo_med  = mean(preo_raw) if preo_raw else 0
    iea_media = mean(scores)
    bajo   = sum(1 for s in scores if s <= 3)
    medio  = sum(1 for s in scores if 4 <= s <= 6)
    alto   = sum(1 for s in scores if s >= 7)

    return dict(
        n=n, pct_ia=pct_ia, pct_form=pct_form, pct_hab=pct_hab,
        pct_auto=pct_auto, preo_media=preo_med, iea_media=iea_media,
        bajo=bajo, medio=medio, alto=alto, scores=scores,
        areas_flat=areas_flat, preo_raw=preo_raw,
        usa_ia=usa_ia, formacion=formacion, uso_pers=uso_pers,
        auto=auto, cambio=cambio,
    )


# ── Secciones de terminal ─────────────────────────────────────────────────────

def s1_demografico(datos, n):
    titulo("S1 · PERFIL DEMOGRÁFICO", 2)
    edades   = [get(f, "edad")        for f in datos]
    exps     = [get(f, "experiencia") for f in datos]
    sectores = [get(f, "sector")      for f in datos]
    print("  Distribución por edad:")
    for v, c in Counter(edades).most_common():
        print(f"    {v:<20} {barra(c, n)}")
    print("\n  Años de experiencia:")
    for v, c in Counter(exps).most_common():
        print(f"    {v:<20} {barra(c, n)}")
    print("\n  Sector de trabajo:")
    for v, c in Counter(sectores).most_common():
        print(f"    {v:<45} {barra(c, n)}")

def s2_adopcion(datos, n):
    titulo("S2 · ADOPCIÓN DE IA EN EMPRESAS", 2)
    usa_ia = Counter(get(f, "empresa_usa_ia") for f in datos)
    for v, c in usa_ia.most_common():
        print(f"  {v:<8} {barra(c, n)}")
    print(f"\n  → El {100*usa_ia.get('Sí',0)/n:.1f}% de las empresas representadas ya usa IA.")

def s3_areas(datos, n):
    titulo("S3 · ÁREAS DE APLICACIÓN DE LA IA", 2)
    af = areas_flat_fn(datos)
    total = len(af)
    print(f"  (Respuesta múltiple — total menciones: {total})\n")
    for v, c in Counter(af).most_common():
        print(f"    {v:<45} {barra(c, total)}")

def s4_formacion(datos, n):
    titulo("S4 · FORMACIÓN EN IA OFRECIDA POR LA EMPRESA", 2)
    formacion = Counter(get(f, "formacion_ia") for f in datos)
    for v, c in formacion.most_common():
        print(f"  {v:<15} {barra(c, n)}")
    print(f"\n  → El {100*formacion.get('Sí',0)/n:.1f}% de las empresas ofrece formación en IA.")

def s5_uso_personal(datos, n):
    titulo("S5 · USO PERSONAL DE IA EN EL TRABAJO", 2)
    uso = Counter(get(f, "uso_personal_ia") for f in datos)
    for v, c in uso.most_common():
        print(f"  {v:<30} {barra(c, n)}")
    print(f"\n  → El {100*uso.get('Sí, habitualmente',0)/n:.1f}% usa IA de forma habitual.")

def s6_cambio_carga(datos, n):
    titulo("S6 · CAMBIO EN CARGA/TIPO DE TRABAJO DESDE LA IA", 2)
    cambio = Counter(get(f, "cambio_carga") for f in datos if get(f, "cambio_carga"))
    total = sum(cambio.values())
    for v, c in cambio.most_common():
        print(f"  {v:<20} {barra(c, total)}")

def s7_automatizacion(datos, n):
    titulo("S7 · AUTOMATIZACIÓN DE TAREAS DEL EQUIPO", 2)
    auto = Counter(get(f, "automatizo") for f in datos)
    for v, c in auto.most_common():
        print(f"  {v:<20} {barra(c, n)}")
    pct = 100 * (auto.get("Sí, bastantes", 0) + auto.get("Sí, algunas", 0)) / n
    print(f"\n  → En el {pct:.1f}% de los casos se han automatizado tareas del equipo.")

def s8_preocupacion(datos, n):
    titulo("S8 · PREOCUPACIÓN POR SUSTITUCIÓN (escala 1–5)", 2)
    preo = preo_raw_fn(datos)
    if not preo:
        print("  (Sin datos)")
        return
    m_mean = mean(preo)
    m_med  = median(preo)
    try:    m_mode = mode(preo)
    except StatisticsError: m_mode = "-"
    print(f"  Media   : {estrellas(m_mean)}")
    print(f"  Mediana : {m_med:.1f} / 5")
    print(f"  Moda    : {m_mode}\n")
    dist = Counter(preo)
    for v in sorted(dist):
        print(f"  Nivel {v}  {barra(dist[v], n)}")
    print(f"\n  → El {100*sum(1 for x in preo if x>=4)/n:.1f}% muestra preocupación alta (≥ 4).")

def s9_comentarios(datos, n):
    titulo("S9 · COMENTARIOS CUALITATIVOS", 2)
    coms = [(i+1, get(f, "comentario")) for i, f in enumerate(datos) if get(f, "comentario")]
    if coms:
        for idx, c in coms:
            print(f"  #{idx:02d}  \"{c}\"")
    else:
        print("  (Sin comentarios registrados)")

def s10_cruzado(datos, n):
    titulo("S10 · ANÁLISIS CRUZADO: PREOCUPACIÓN POR SECTOR", 2)
    sector_preo = {}
    for f in datos:
        sec = get(f, "sector")
        try:    p = int(get(f, "preocupacion"))
        except ValueError: continue
        sector_preo.setdefault(sec, []).append(p)
    print(f"  {'Sector':<48} {'Media':>6}  {'N':>3}")
    sep()
    for sec, vals in sorted(sector_preo.items(), key=lambda x: -mean(x[1])):
        print(f"  {sec:<48} {mean(vals):>5.2f}  {len(vals):>3}")

def s11_iea(datos, n):
    titulo("S11 · ÍNDICE DE EXPOSICIÓN A LA AUTOMATIZACIÓN (IEA)", 2)
    print("  Metodología: puntuación 0–10 (Frey & Osborne, 2013; Arntz et al., 2016)\n")
    print(f"  {'#':>3}  {'Sector':<40} {'Exp.':<18} {'Uso IA':<25} {'IEA':>4}  Nivel")
    sep()
    scores = []
    for i, f in enumerate(datos):
        score = calcular_iea(f)
        scores.append(score)
        print(f"  {i+1:>3}  {get(f,'sector')[:38]:<40} {get(f,'experiencia')[:16]:<18} "
              f"{get(f,'uso_personal_ia')[:23]:<25} {score:>4}  [{nivel_iea(score)}]")
    sep()
    iea_m = mean(scores)
    bajo  = sum(1 for s in scores if s <= 3)
    medio = sum(1 for s in scores if 4 <= s <= 6)
    alto  = sum(1 for s in scores if s >= 7)
    print(f"\n  IEA medio: {iea_m:.2f}/10")
    print(f"  Riesgo BAJO  (0–3)   {barra(bajo,  n)}")
    print(f"  Riesgo MEDIO (4–6)   {barra(medio, n)}")
    print(f"  Riesgo ALTO  (7–10)  {barra(alto,  n)}")
    sec_iea = {}
    for f, s in zip(datos, scores):
        sec_iea.setdefault(get(f, "sector"), []).append(s)
    print(f"\n  {'Sector':<48} {'IEA medio':>9}  {'N':>3}")
    sep()
    for sec, vals in sorted(sec_iea.items(), key=lambda x: -mean(x[1])):
        bar = "█" * round(mean(vals)) + "░" * (10 - round(mean(vals)))
        print(f"  {sec:<48} {mean(vals):>6.2f}/10  {len(vals):>3}  {bar}")

def simulador_iea():
    titulo("SIMULADOR IEA — ¿Cuál es tu exposición a la automatización?", 2)
    print("  Responde las preguntas para calcular tu Índice de Exposición a la Automatización.\n")

    # Experiencia
    opciones_exp = list(PESO_EXPERIENCIA.keys())
    print("  Años de experiencia laboral:")
    for i, o in enumerate(opciones_exp, 1):
        print(f"    {i}. {o}")
    while True:
        try:
            sel = int(input("  Elige (1-5): ").strip())
            if 1 <= sel <= len(opciones_exp):
                experiencia = opciones_exp[sel - 1]; break
        except ValueError: pass
        print("  [!] Opción no válida.")

    # Sector
    opciones_sec = list(PESO_SECTOR.keys())
    print("\n  Sector en el que trabajas:")
    for i, o in enumerate(opciones_sec, 1):
        print(f"    {i}. {o}")
    while True:
        try:
            sel = int(input(f"  Elige (1-{len(opciones_sec)}): ").strip())
            if 1 <= sel <= len(opciones_sec):
                sector = opciones_sec[sel - 1]; break
        except ValueError: pass
        print("  [!] Opción no válida.")

    # Uso personal IA
    opciones_uso = list(PESO_USO_IA.keys())
    print("\n  ¿Usas IA en tu trabajo?")
    for i, o in enumerate(opciones_uso, 1):
        print(f"    {i}. {o}")
    while True:
        try:
            sel = int(input("  Elige (1-4): ").strip())
            if 1 <= sel <= len(opciones_uso):
                uso_ia = opciones_uso[sel - 1]; break
        except ValueError: pass
        print("  [!] Opción no válida.")

    # Automatización — se muestra sin "Sí," pero la clave interna lo mantiene
    opciones_auto = list(PESO_AUTOMATIZO.keys())
    etiquetas_auto = [o.replace("Sí, b", "B").replace("Sí, a", "A") for o in opciones_auto]
    print("\n  ¿Cuántas tareas de tu equipo se han automatizado ya?")
    for i, e in enumerate(etiquetas_auto, 1):
        print(f"    {i}. {e}")
    while True:
        try:
            sel = int(input("  Elige (1-5): ").strip())
            if 1 <= sel <= len(opciones_auto):
                automatizo = opciones_auto[sel - 1]; break
        except ValueError: pass
        print("  [!] Opción no válida.")

    # Calcular con desglose por dimensión
    p_exp  = PESO_EXPERIENCIA.get(experiencia, 1)
    p_sec  = PESO_SECTOR.get(sector, 1)
    p_uso  = PESO_USO_IA.get(uso_ia, 1)
    p_auto = PESO_AUTOMATIZO.get(automatizo, 0)
    score  = min(p_exp + p_sec + p_uso + p_auto, 10)
    nivel  = nivel_iea(score).strip()

    barra_iea = "█" * score + "░" * (10 - score)
    sep()
    print(f"\n  Perfil introducido:")
    print(f"    Experiencia : {experiencia:<30} (+{p_exp})")
    print(f"    Sector      : {sector:<30} (+{p_sec})")
    print(f"    Uso IA      : {uso_ia:<30} (+{p_uso})")
    print(f"    Automatiz.  : {automatizo:<30} (+{p_auto})")
    sep()
    print(f"\n  ► IEA calculado : {score}/10   [{barra_iea}]   Nivel: {nivel}")
    if nivel == "BAJO":
        print("  Tu perfil presenta baja exposición al riesgo de automatización.")
    elif nivel == "MEDIO":
        print("  Tu perfil presenta exposición moderada. Recomendable reforzar competencias en IA.")
    else:
        print("  Tu perfil presenta alta exposición. La formación en IA es una prioridad estratégica.")
    print()

    # Guardar para el PDF
    global _ultima_simulacion
    _ultima_simulacion = {
        "experiencia": experiencia, "p_exp": p_exp,
        "sector":      sector,      "p_sec": p_sec,
        "uso_ia":      uso_ia,      "p_uso": p_uso,
        "automatizo":  automatizo,  "p_auto": p_auto,
        "score": score, "nivel": nivel,
    }


def sc_conclusiones(datos, st):
    titulo("CONCLUSIONES DEL ANÁLISIS", 1)
    n = st["n"]
    pct_bajo  = 100 * st["bajo"]  / n
    pct_medio = 100 * st["medio"] / n
    pct_alto  = 100 * st["alto"]  / n
    print(f"""
  C1 · ADOPCIÓN MASIVA CON BRECHA FORMATIVA
  ──────────────────────────────────────────
  El {st['pct_ia']:.1f}% de las organizaciones ya usa IA. Solo el {st['pct_form']:.1f}%
  ofrece formación específica (Capítulo 2).

  C2 · EL TRABAJADOR HA TOMADO LA INICIATIVA
  ────────────────────────────────────────────
  El {st['pct_hab']:.1f}% usa IA habitualmente sin estrategia formal (Capítulo 5).

  C3 · AUTOMATIZACIÓN REAL Y VISIBLE
  ────────────────────────────────────
  El {st['pct_auto']:.1f}% confirma automatización de tareas del equipo (Capítulo 4).

  C4 · BAJA PREOCUPACIÓN ANTE UN CAMBIO ACELERADO
  ──────────────────────────────────────────────────
  Preocupación media {st['preo_media']:.2f}/5. Posible 'sesgo de optimismo' (Capítulo 6).

  C5 · IEA — DISTRIBUCIÓN DE RIESGO
  ────────────────────────────────────
  IEA medio {st['iea_media']:.2f}/10. {pct_bajo:.1f}% riesgo BAJO, {pct_medio:.1f}% MEDIO, {pct_alto:.1f}% ALTO.""")
    sep("═")
    print(f"  TFG — Universidad Pontificia de Salamanca — {datetime.now().year}")
    sep("═")

def analizar_todo(datos, st):
    n = st["n"]
    titulo("ANÁLISIS DE ENCUESTA — TFG IA EN EMPRESAS TECNOLÓGICAS")
    print(f"  Fecha : {datetime.now().strftime('%d/%m/%Y %H:%M')}  |  Respuestas: {n}\n")
    s1_demografico(datos, n);  s2_adopcion(datos, n);    s3_areas(datos, n)
    s4_formacion(datos, n);    s5_uso_personal(datos, n); s6_cambio_carga(datos, n)
    s7_automatizacion(datos, n); s8_preocupacion(datos, n); s9_comentarios(datos, n)
    s10_cruzado(datos, n);     s11_iea(datos, n);         sc_conclusiones(datos, st)


# ── Menú interactivo ──────────────────────────────────────────────────────────

SECCIONES = [
    ("Perfil demografico",                          s1_demografico),
    ("Adopcion de IA en empresas",                  s2_adopcion),
    ("Areas de aplicacion de la IA",                s3_areas),
    ("Formacion en IA ofrecida por la empresa",     s4_formacion),
    ("Uso personal de IA en el trabajo",            s5_uso_personal),
    ("Cambio en carga/tipo de trabajo desde la IA", s6_cambio_carga),
    ("Automatizacion de tareas del equipo",         s7_automatizacion),
    ("Preocupacion por sustitucion",                s8_preocupacion),
    ("Comentarios cualitativos",                    s9_comentarios),
    ("Analisis cruzado: preocupacion por sector",   s10_cruzado),
    ("Indice de Exposicion a la Automatizacion",    s11_iea),
]

def imprimir_menu(n):
    sep("═")
    print("  ANALISIS DE ENCUESTA — TFG IA EN EMPRESAS TECNOLOGICAS")
    print(f"  Respuestas cargadas: {n}")
    sep("═")
    print()
    print("  Selecciona una seccion para analizar:\n")
    for i, (t, _) in enumerate(SECCIONES, 1):
        print(f"    {i} - {t}")
    print()
    print("    T - Todo el analisis completo")
    print("    C - Conclusiones del analisis")
    print("    P - Exportar informe completo a PDF")
    print("    I - Simulador IEA (calcula tu propio indice)")
    print("    S - Salir")
    print()
    sep()

def menu_interactivo(datos, st):
    n = st["n"]
    while True:
        imprimir_menu(n)
        try:
            opcion = input("  Elige una opcion: ").strip().upper()
        except (KeyboardInterrupt, EOFError):
            print("\n\n  Hasta luego.")
            break
        print()
        if opcion == "S":
            print("  Hasta luego.")
            break
        elif opcion == "T":
            analizar_todo(datos, st)
        elif opcion == "C":
            sc_conclusiones(datos, st)
        elif opcion == "P":
            nombre = input("  Nombre del archivo PDF [informe_tfg.pdf]: ").strip()
            if not nombre:
                nombre = "informe_tfg.pdf"
            generar_pdf(nombre, datos, st)
        elif opcion == "I":
            simulador_iea()
        elif opcion.isdigit():
            idx = int(opcion) - 1
            if 0 <= idx < len(SECCIONES):
                SECCIONES[idx][1](datos, n)
            else:
                print(f"  [!] Opcion no valida. Elige entre 1 y {len(SECCIONES)}.")
        else:
            print("  [!] Opcion no reconocida.")
        print()
        input("  Pulsa Enter para volver al menu...")
        print()


# ── Generación PDF visual ─────────────────────────────────────────────────────

def generar_pdf(ruta_pdf, datos, st):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from fpdf import FPDF
    except ImportError as e:
        print(f"[ERROR] Falta una libreria: {e}")
        print("        Ejecuta: pip3 install matplotlib fpdf2")
        return

    def lat1(t):
        return str(t).encode("latin-1", errors="replace").decode("latin-1")

    def make_pie(ax, datos_dict, titulo_c):
        etqs = list(datos_dict.keys())
        vals = list(datos_dict.values())
        wedges, texts, autotexts = ax.pie(
            vals, labels=etqs, autopct="%1.1f%%",
            colors=PALETA[:len(vals)], startangle=90,
            pctdistance=0.80,
            wedgeprops=dict(linewidth=1.5, edgecolor="white"),
        )
        for t in texts:     t.set_fontsize(8)
        for at in autotexts: at.set_fontsize(9); at.set_fontweight("bold")
        ax.set_title(titulo_c, fontsize=10, fontweight="bold", pad=10)

    def make_hbar(ax, datos_dict, titulo_c, xlabel="n"):
        etqs = [e[:32] + "…" if len(e) > 32 else e for e in datos_dict]
        vals = list(datos_dict.values())
        bars = ax.barh(etqs, vals, color=PALETA[:len(vals)],
                       edgecolor="white", height=0.65)
        ax.bar_label(bars, fmt="%d", padding=4, fontsize=9, fontweight="bold")
        ax.set_xlabel(xlabel, fontsize=9)
        ax.set_title(titulo_c, fontsize=10, fontweight="bold")
        ax.invert_yaxis()
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(axis="y", labelsize=8)
        ax.set_xlim(0, max(vals) * 1.2)

    def save(fig, nombre):
        path = os.path.join(tmpdir, nombre)
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        return path

    print("[...] Generando graficos...")
    tmpdir = tempfile.mkdtemp()
    n = st["n"]

    try:
        # ── Gráfico S1: perfil (3 pies) ───────────────────────────────────────
        edades   = Counter(get(f, "edad")        for f in datos)
        exps     = Counter(get(f, "experiencia") for f in datos)
        sectores = Counter(get(f, "sector")      for f in datos)
        fig, axes = plt.subplots(1, 3, figsize=(14, 5))
        make_pie(axes[0], dict(edades),   "Distribucion por edad")
        make_pie(axes[1], dict(exps),     "Anos de experiencia")
        make_pie(axes[2], dict(sectores), "Sector de trabajo")
        fig.tight_layout(pad=2.0)
        ch_s1 = save(fig, "s1.png")

        # ── S2: empresa usa IA ────────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(5, 4))
        make_pie(ax, dict(st["usa_ia"]), "Adopcion de IA en empresas")
        fig.tight_layout()
        ch_s2 = save(fig, "s2.png")

        # ── S4: formación ─────────────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(5, 4))
        make_pie(ax, dict(st["formacion"]), "Formacion en IA por la empresa")
        fig.tight_layout()
        ch_s4 = save(fig, "s4.png")

        # ── S3: áreas (barras horizontales) ───────────────────────────────────
        af = st["areas_flat"]
        areas_cnt = dict(Counter(af).most_common())
        fig, ax = plt.subplots(figsize=(8, max(3, len(areas_cnt) * 0.55 + 1)))
        make_hbar(ax, areas_cnt, "Areas de aplicacion de la IA", "Menciones")
        fig.tight_layout()
        ch_s3 = save(fig, "s3.png")

        # ── S5: uso personal ──────────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(5, 4))
        make_pie(ax, dict(st["uso_pers"]), "Uso personal de IA en el trabajo")
        fig.tight_layout()
        ch_s5 = save(fig, "s5.png")

        # ── S6: cambio carga ──────────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(5, 4))
        make_pie(ax, dict(st["cambio"]), "Cambio en carga de trabajo")
        fig.tight_layout()
        ch_s6 = save(fig, "s6.png")

        # ── S7: automatización ────────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(5, 4))
        make_pie(ax, dict(st["auto"]), "Automatizacion de tareas del equipo")
        fig.tight_layout()
        ch_s7 = save(fig, "s7.png")

        # ── S8: preocupación (barras con línea media) ─────────────────────────
        preo_dist = Counter(st["preo_raw"])
        colores_p = ["#55A868", "#8CC665", "#CCB974", "#DD8452", "#C44E52"]
        fig, ax = plt.subplots(figsize=(6, 3.5))
        vals_p = [preo_dist.get(i, 0) for i in range(1, 6)]
        bars = ax.bar(["1","2","3","4","5"], vals_p,
                      color=colores_p, edgecolor="white", width=0.65)
        ax.bar_label(bars, padding=2, fontsize=10, fontweight="bold")
        ax.set_xlabel("Nivel de preocupacion (1=nada, 5=mucho)", fontsize=9)
        ax.set_ylabel("Encuestados", fontsize=9)
        ax.set_title("Preocupacion por sustitucion por la IA",
                     fontsize=10, fontweight="bold")
        ax.axhline(y=st["preo_media"], color="red", linestyle="--",
                   alpha=0.7, linewidth=1.5, label=f"Media: {st['preo_media']:.2f}")
        ax.legend(fontsize=9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()
        ch_s8 = save(fig, "s8.png")

        # ── S10: preocupación por sector ──────────────────────────────────────
        sector_preo = {}
        for f in datos:
            sec = get(f, "sector")
            try:    p = int(get(f, "preocupacion"))
            except ValueError: continue
            sector_preo.setdefault(sec, []).append(p)
        medias_s = dict(sorted(
            {sec: mean(v) for sec, v in sector_preo.items()}.items(),
            key=lambda x: x[1]
        ))
        fig, ax = plt.subplots(figsize=(8, max(3, len(medias_s)*0.55 + 1)))
        c_s10 = [colores_p[min(4, max(0, int(v)-1))] for v in medias_s.values()]
        bars = ax.barh(list(medias_s.keys()), list(medias_s.values()),
                       color=c_s10, edgecolor="white", height=0.65)
        ax.bar_label(bars, fmt="%.2f", padding=3, fontsize=9, fontweight="bold")
        ax.set_xlabel("Media de preocupacion (1-5)", fontsize=9)
        ax.set_title("Preocupacion media por sector", fontsize=10, fontweight="bold")
        ax.set_xlim(0, 5.8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(axis="y", labelsize=8)
        fig.tight_layout()
        ch_s10 = save(fig, "s10.png")

        # ── S11a: IEA distribución (pie) ──────────────────────────────────────
        iea_dist = {}
        if st["bajo"]:  iea_dist[f"Riesgo BAJO (0-3)\n{st['bajo']} personas"]  = st["bajo"]
        if st["medio"]: iea_dist[f"Riesgo MEDIO (4-6)\n{st['medio']} personas"] = st["medio"]
        if st["alto"]:  iea_dist[f"Riesgo ALTO (7-10)\n{st['alto']} personas"]  = st["alto"]
        iea_colores = ["#55A868", "#F18F01", "#C44E52"]
        fig, ax = plt.subplots(figsize=(5, 4))
        wedges, texts, autotexts = ax.pie(
            list(iea_dist.values()), labels=list(iea_dist.keys()),
            autopct="%1.1f%%", colors=iea_colores[:len(iea_dist)],
            startangle=90, pctdistance=0.80,
            wedgeprops=dict(linewidth=1.5, edgecolor="white"),
        )
        for t in texts:      t.set_fontsize(8)
        for at in autotexts: at.set_fontsize(9); at.set_fontweight("bold")
        ax.set_title("Distribucion del Indice IEA", fontsize=10, fontweight="bold", pad=10)
        fig.tight_layout()
        ch_s11_pie = save(fig, "s11_pie.png")

        # ── S11b: IEA por sector (barras) ─────────────────────────────────────
        sec_iea = {}
        for f, s in zip(datos, st["scores"]):
            sec_iea.setdefault(get(f, "sector"), []).append(s)
        iea_sorted = dict(sorted(
            {sec: mean(v) for sec, v in sec_iea.items()}.items(),
            key=lambda x: x[1]
        ))
        bar_c = ["#55A868" if v<=3 else "#F18F01" if v<=6 else "#C44E52"
                 for v in iea_sorted.values()]
        fig, ax = plt.subplots(figsize=(8, max(3, len(iea_sorted)*0.55 + 1)))
        bars = ax.barh(list(iea_sorted.keys()), list(iea_sorted.values()),
                       color=bar_c, edgecolor="white", height=0.65)
        ax.bar_label(bars, fmt="%.2f", padding=3, fontsize=9, fontweight="bold")
        ax.set_xlabel("IEA medio (0-10)", fontsize=9)
        ax.set_title("IEA medio por sector", fontsize=10, fontweight="bold")
        ax.set_xlim(0, 11)
        ax.axvline(x=4, color="gray", linestyle="--", alpha=0.4, linewidth=1)
        ax.axvline(x=7, color="gray", linestyle="--", alpha=0.4, linewidth=1)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(axis="y", labelsize=8)
        fig.tight_layout()
        ch_s11_bar = save(fig, "s11_bar.png")

        # ── Conclusiones: 4 pies resumen ──────────────────────────────────────
        fig, axes = plt.subplots(2, 2, figsize=(11, 9))
        make_pie(axes[0,0], dict(st["usa_ia"]),
                 f"Empresas con IA ({st['pct_ia']:.1f}% si)")
        make_pie(axes[0,1], dict(st["formacion"]),
                 f"Formacion en IA ({st['pct_form']:.1f}% si)")
        make_pie(axes[1,0], dict(st["uso_pers"]),
                 f"Uso personal IA ({st['pct_hab']:.1f}% habitual)")
        make_pie(axes[1,1], dict(st["auto"]),
                 f"Tareas automatizadas ({st['pct_auto']:.1f}% si)")
        fig.suptitle("Resumen de indicadores clave", fontsize=13,
                     fontweight="bold", y=1.01)
        fig.tight_layout()
        ch_conc = save(fig, "conclusiones.png")

        # ── Construir PDF ──────────────────────────────────────────────────────
        print("[...] Construyendo PDF...")

        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=15)
        M   = 15
        PW  = 210 - 2 * M   # 180mm útiles
        AZUL = (52, 110, 170)
        VERDE = (40, 110, 60)

        def hdr(texto, rgb=AZUL):
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_fill_color(*rgb)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(0, 8, lat1(texto), ln=True, fill=True)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(3)

        def txt(texto, size=10, bold=False, color=(0,0,0)):
            pdf.set_font("Helvetica", "B" if bold else "", size)
            pdf.set_text_color(*color)
            pdf.multi_cell(0, 5.5, lat1(texto))
            pdf.set_text_color(0, 0, 0)
            pdf.ln(1)

        def img_center(path, w=None):
            w = w or PW
            x = M + (PW - w) / 2
            pdf.image(path, x=x, w=w)
            pdf.ln(3)

        def two_imgs(p1, p2, w_each=None):
            w = w_each or (PW / 2 - 3)
            y0 = pdf.get_y()
            pdf.image(p1, x=M,         y=y0, w=w)
            pdf.image(p2, x=M + w + 6, y=y0, w=w)
            pdf.ln(68)

        # Portada
        pdf.add_page()
        pdf.set_margins(M, M, M)
        pdf.ln(20)
        pdf.set_font("Helvetica", "B", 20)
        pdf.set_text_color(52, 110, 170)
        pdf.multi_cell(0, 10, lat1(
            "El Impacto De La IA En Las\nEmpresas Del Sector Tecnologico"
        ), align="C")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(4)
        pdf.set_font("Helvetica", "", 13)
        pdf.cell(0, 8, "Informe de analisis de encuesta", ln=True, align="C")
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(90, 90, 90)
        pdf.cell(0, 6, "Universidad Pontificia de Salamanca", ln=True, align="C")
        pdf.cell(0, 6, f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align="C")
        pdf.cell(0, 6, f"Respuestas analizadas: {n}", ln=True, align="C")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(12)
        pdf.set_fill_color(235, 242, 250)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, "Contenido", ln=True, fill=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.ln(2)
        for item in [
            "1.  Perfil demografico",
            "2.  Adopcion de IA en empresas",
            "3.  Areas de aplicacion de la IA",
            "4.  Formacion en IA",
            "5.  Uso personal de IA",
            "6.  Cambio en carga de trabajo",
            "7.  Automatizacion de tareas",
            "8.  Preocupacion por sustitucion",
            "9.  Comentarios cualitativos",
            "10. Analisis cruzado por sector",
            "11. Indice de Exposicion a la Automatizacion (IEA)",
            "    Conclusiones del analisis",
        ]:
            pdf.cell(0, 6, f"    {item}", ln=True)

        # S1: Perfil demográfico
        pdf.add_page()
        hdr("1. Perfil demografico")
        txt(f"La muestra esta formada por {n} encuestados del sector tecnologico y afines.")
        img_center(ch_s1, w=PW)

        # S2: Adopción
        pdf.add_page()
        hdr("2. Adopcion de IA en empresas")
        txt(f"El {st['pct_ia']:.1f}% de las empresas representadas ya utiliza herramientas "
            f"de inteligencia artificial en alguno de sus procesos. Este dato confirma la "
            f"hipotesis planteada en el Capitulo 3 del TFG sobre la penetracion acelerada "
            f"de la IA en el sector tecnologico.")
        img_center(ch_s2, w=PW * 0.65)

        # S3: Áreas de aplicación
        pdf.add_page()
        hdr("3. Areas de aplicacion de la IA")
        txt(f"Pregunta de respuesta multiple — total de menciones: {len(af)}. "
            f"El area con mayor presencia es Desarrollo / programacion, lo que senala "
            f"que la automatizacion del codigo esta redefiniendo el perfil del desarrollador "
            f"hacia roles de supervision y diseno arquitectonico (Capitulo 6).")
        img_center(ch_s3, w=PW)

        # S4: Formación
        pdf.add_page()
        hdr("4. Formacion en IA ofrecida por la empresa")
        txt(f"Solo el {st['pct_form']:.1f}% de las empresas ha ofrecido formacion especifica "
            f"en IA a sus empleados. Esto evidencia una brecha importante entre la adopcion "
            f"tecnologica y la capacitacion del capital humano, aspecto clave tratado en el "
            f"Marco conceptual (Capitulo 2) del TFG.")
        img_center(ch_s4, w=PW * 0.65)

        # S5: Uso personal
        pdf.add_page()
        hdr("5. Uso personal de IA en el trabajo")
        txt(f"El {st['pct_hab']:.1f}% de los encuestados usa IA de forma habitual en su "
            f"trabajo diario, incluso en entornos donde la empresa no ha implantado una "
            f"estrategia formal. Esto sugiere un proceso de adopcion bottom-up que las "
            f"organizaciones deberan gestionar para garantizar un uso etico y coherente "
            f"con sus politicas internas (Capitulo 5: Etica y regulacion).")
        img_center(ch_s5, w=PW * 0.65)

        # S6: Cambio de carga
        pdf.add_page()
        hdr("6. Cambio en carga/tipo de trabajo desde la IA")
        txt("Distribucion de los cambios reportados por los encuestados que usan IA. "
            "La mayoria percibe cambios moderados en su carga de trabajo, lo que refleja "
            "una transformacion gradual pero sostenida de las tareas diarias.")
        img_center(ch_s6, w=PW * 0.65)

        # S7: Automatización
        pdf.add_page()
        hdr("7. Automatizacion de tareas del equipo")
        txt(f"El {st['pct_auto']:.1f}% de los participantes confirma que la IA ya ha "
            f"automatizado tareas que antes realizaban ellos o su equipo. Lejos de ser "
            f"una percepcion futura, el impacto en el empleo ya esta ocurriendo, "
            f"respaldando los modelos de sustitucion de Frey & Osborne (2013) y el "
            f"analisis del Capitulo 4 del TFG.")
        img_center(ch_s7, w=PW * 0.65)

        # S8: Preocupación
        pdf.add_page()
        hdr("8. Preocupacion por sustitucion (escala 1-5)")
        txt(f"Media: {st['preo_media']:.2f}/5  |  Mediana: {median(st['preo_raw']):.1f}/5. "
            f"La preocupacion media es notablemente baja dada la magnitud de los cambios "
            f"reportados. Esto puede indicar confianza en la propia adaptabilidad, o bien "
            f"una infravaloración del riesgo a largo plazo, fenomeno documentado en la "
            f"literatura como 'sesgo de optimismo' (Capitulo 6).")
        img_center(ch_s8, w=PW * 0.8)

        # S9: Comentarios
        pdf.add_page()
        hdr("9. Comentarios cualitativos")
        coms = [(i+1, get(f, "comentario")) for i, f in enumerate(datos)
                if get(f, "comentario")]
        if coms:
            for idx, c in coms:
                pdf.set_font("Helvetica", "B", 9)
                pdf.cell(0, 5, f"Encuestado #{idx:02d}:", ln=True)
                pdf.set_font("Helvetica", "I", 9)
                pdf.set_text_color(60, 60, 60)
                pdf.multi_cell(0, 5, lat1(f'"{c}"'))
                pdf.set_text_color(0, 0, 0)
                pdf.ln(3)
        else:
            txt("Sin comentarios registrados.")

        # S10: Análisis cruzado
        pdf.add_page()
        hdr("10. Analisis cruzado: preocupacion media por sector")
        txt("Preocupacion media por sustitucion segun el sector de trabajo del encuestado. "
            "Los colores reflejan el nivel: verde (bajo), naranja (medio), rojo (alto).")
        img_center(ch_s10, w=PW)

        # S11: IEA
        pdf.add_page()
        hdr("11. Indice de Exposicion a la Automatizacion (IEA)")
        txt(f"IEA medio de la muestra: {st['iea_media']:.2f}/10", bold=True)
        txt("Metodologia: puntuacion 0-10 combinando cuatro dimensiones — experiencia "
            "laboral, sector de actividad, nivel de uso personal de IA y grado de "
            "automatizacion ya experimentado. Inspirado en Frey & Osborne (2013) y "
            "Arntz et al. (2016). Permite identificar perfiles con mayor exposicion "
            "al riesgo de sustitucion para orientar politicas de upskilling.")
        two_imgs(ch_s11_pie, ch_s11_bar, w_each=PW/2 - 2)

        # Tabla individual encuestados
        pdf.add_page()
        hdr("11. Tabla de puntuaciones IEA por encuestado")
        # Anchos columnas (mm): #, Sector, Experiencia, Uso IA, IEA, Nivel
        col_w   = [8, 55, 34, 46, 10, 15]
        headers = ["#", "Sector", "Experiencia", "Uso IA", "IEA", "Nivel"]
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_fill_color(52, 110, 170)
        pdf.set_text_color(255, 255, 255)
        for w, h in zip(col_w, headers):
            pdf.cell(w, 5, h, border=1, fill=True)
        pdf.ln()
        pdf.set_text_color(0, 0, 0)
        colores_fila = [(245, 249, 255), (255, 255, 255)]
        for i, (f, score) in enumerate(zip(datos, st["scores"])):
            nivel = nivel_iea(score).strip()
            fila_vals = [
                str(i + 1),
                lat1(get(f, "sector")[:32]),
                lat1(get(f, "experiencia")[:22]),
                lat1(get(f, "uso_personal_ia")[:28]),
                str(score),
                nivel,
            ]
            pdf.set_font("Helvetica", "", 7)
            pdf.set_fill_color(*colores_fila[i % 2])
            for w, v in zip(col_w, fila_vals):
                pdf.cell(w, 4.5, v, border=1, fill=True)
            pdf.ln()
        # Fila resumen
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_fill_color(220, 230, 245)
        resumen_vals = [
            lat1(f"n={n}"),
            "",
            "",
            lat1(f"Media IEA: {st['iea_media']:.2f}/10"),
            "",
            lat1(f"B:{st['bajo']} M:{st['medio']} A:{st['alto']}"),
        ]
        for w, v in zip(col_w, resumen_vals):
            pdf.cell(w, 5, v, border=1, fill=True)
        pdf.ln(3)

        # Simulador IEA — última simulación ejecutada
        pdf.add_page()
        hdr("12. Simulador IEA — Ultima simulacion realizada")
        if _ultima_simulacion is None:
            txt("No se ha ejecutado ninguna simulacion en esta sesion. "
                "Usa la opcion I del menu interactivo antes de generar el PDF "
                "para que tu perfil aparezca en esta pagina.")
        else:
            sim = _ultima_simulacion
            score = sim["score"]
            nivel = sim["nivel"]
            txt("Resultado de la ultima simulacion ejecutada desde el menu interactivo. "
                "Cada dimension contribuye con una puntuacion parcial que se suma "
                "para obtener el IEA final (escala 0-10).")
            pdf.ln(4)

            # Color según nivel
            color_nivel = {
                "BAJO":  (40, 160, 80),
                "MEDIO": (210, 120, 30),
                "ALTO":  (180, 40, 40),
            }.get(nivel, (80, 80, 80))

            # Tabla de desglose
            dim_w = [70, 95, 15]
            dim_headers = ["Dimension", "Respuesta", "Pts"]
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_fill_color(52, 110, 170)
            pdf.set_text_color(255, 255, 255)
            for w, h in zip(dim_w, dim_headers):
                pdf.cell(w, 6, h, border=1, fill=True)
            pdf.ln()
            pdf.set_text_color(0, 0, 0)

            dimensiones = [
                ("Experiencia laboral",          sim["experiencia"], sim["p_exp"]),
                ("Sector de actividad",          sim["sector"],      sim["p_sec"]),
                ("Uso personal de IA",           sim["uso_ia"],      sim["p_uso"]),
                ("Tareas automatizadas ya",      sim["automatizo"],  sim["p_auto"]),
            ]
            colores_fila = [(245, 249, 255), (255, 255, 255)]
            for i, (dim, resp, pts) in enumerate(dimensiones):
                pdf.set_font("Helvetica", "", 9)
                pdf.set_fill_color(*colores_fila[i % 2])
                pdf.cell(dim_w[0], 6, lat1(dim),  border=1, fill=True)
                pdf.cell(dim_w[1], 6, lat1(resp), border=1, fill=True)
                pdf.cell(dim_w[2], 6, f"+{pts}",  border=1, fill=True, align="C")
                pdf.ln()

            # Fila total
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_fill_color(220, 230, 245)
            pdf.cell(dim_w[0] + dim_w[1], 7, "TOTAL IEA", border=1, fill=True)
            pdf.set_fill_color(*color_nivel)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(dim_w[2], 7, str(score), border=1, fill=True, align="C")
            pdf.ln(6)
            pdf.set_text_color(0, 0, 0)

            # Barra visual
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 6, lat1(f"IEA: {score}/10 — Nivel {nivel}"), ln=True)
            bw = 8
            for b in range(10):
                if b < score:
                    pdf.set_fill_color(*color_nivel)
                else:
                    pdf.set_fill_color(210, 210, 210)
                pdf.cell(bw, 7, "", border=0, fill=True)
            pdf.ln(8)

            # Explicación del resultado
            pdf.set_font("Helvetica", "I", 9)
            if nivel == "BAJO":
                explicacion = (
                    f"El perfil analizado obtiene un IEA de {score}/10, lo que indica "
                    "una baja exposicion al riesgo de automatizacion. La combinacion de "
                    "experiencia acumulada, sector de actividad y uso activo de herramientas "
                    "de IA reduce significativamente la probabilidad de que sus tareas sean "
                    "sustituidas por sistemas automatizados en el corto plazo."
                )
            elif nivel == "MEDIO":
                explicacion = (
                    f"El perfil analizado obtiene un IEA de {score}/10, lo que indica "
                    "una exposicion moderada al riesgo de automatizacion. Existen dimensiones "
                    "que elevan el riesgo (sector o bajo uso de IA) pero otras que lo compensan. "
                    "Se recomienda reforzar la formacion en IA y desarrollar competencias "
                    "dificilmente automatizables como la creatividad o la gestion de equipos."
                )
            else:
                explicacion = (
                    f"El perfil analizado obtiene un IEA de {score}/10, lo que indica "
                    "una alta exposicion al riesgo de automatizacion. La escasa experiencia, "
                    "el sector de actividad y la baja adopcion de IA concentran el riesgo. "
                    "La formacion urgente en competencias digitales e IA es la principal "
                    "medida de mitigacion recomendada segun la literatura academica "
                    "(Frey & Osborne, 2013; Arntz et al., 2016)."
                )
            pdf.multi_cell(0, 5, lat1(explicacion))

        pdf.ln(3)

        # Conclusiones
        pdf.add_page()
        hdr("Conclusiones del analisis", rgb=VERDE)
        txt("Resumen visual de los cuatro indicadores principales de la encuesta:")
        img_center(ch_conc, w=PW)
        pdf.ln(2)

        af_local = st["areas_flat"]
        top_area = Counter(af_local).most_common(1)[0][0] if af_local else "N/A"
        top_pct  = 100 * Counter(af_local).most_common(1)[0][1] / len(af_local) if af_local else 0
        pct_bajo  = 100 * st["bajo"]  / n
        pct_medio = 100 * st["medio"] / n
        pct_alto  = 100 * st["alto"]  / n

        conclusiones_pdf = [
            ("C1 - Adopcion masiva con brecha formativa",
             f"El {st['pct_ia']:.1f}% de las organizaciones representadas en la muestra ya ha "
             f"incorporado herramientas de IA en sus procesos. Este dato confirma la hipotesis "
             f"planteada en el Capitulo 3 del TFG sobre la penetracion acelerada de la IA en "
             f"el sector tecnologico. Sin embargo, solo el {st['pct_form']:.1f}% de las empresas "
             f"ha ofrecido formacion especifica, lo que evidencia una brecha entre adopcion "
             f"tecnologica y capacitacion del capital humano (Marco conceptual, Capitulo 2)."),
            ("C2 - El trabajador ha tomado la iniciativa",
             f"El {st['pct_hab']:.1f}% de los encuestados usa IA de forma habitual en su trabajo "
             f"diario, incluso en entornos donde la empresa no ha implantado una estrategia formal. "
             f"Esto sugiere un proceso de adopcion bottom-up que las organizaciones deberan gestionar "
             f"para garantizar un uso etico y coherente con sus politicas internas "
             f"(Capitulo 5: Etica y regulacion)."),
            ("C3 - Automatizacion real y visible",
             f"El {st['pct_auto']:.1f}% de los participantes confirma que la IA ha automatizado "
             f"tareas que antes realizaban ellos o su equipo. Lejos de ser una percepcion futura, "
             f"el impacto en el empleo ya esta ocurriendo, respaldando los modelos de sustitucion "
             f"de Frey & Osborne (2013) y el analisis del Capitulo 4 del TFG."),
            ("C4 - Baja preocupacion ante un cambio acelerado",
             f"La preocupacion media por sustitucion es de {st['preo_media']:.2f}/5, un valor "
             f"notablemente bajo dada la magnitud de los cambios reportados. Esto puede indicar "
             f"confianza en la propia adaptabilidad, o bien una infravaloración del riesgo a largo "
             f"plazo, fenomeno documentado en la literatura como 'sesgo de optimismo' (Capitulo 6)."),
            ("C5 - Desarrollo y programacion: el area mas transformada",
             f"El area con mayor presencia de IA es '{top_area}' ({top_pct:.1f}% de las menciones). "
             f"Esto senala que la automatizacion del codigo —copilots, generadores de tests, "
             f"refactoring automatico— esta redefiniendo el perfil del desarrollador de software "
             f"hacia roles de supervision y diseno arquitectonico (Capitulo 6)."),
            ("C6 - Indice de Exposicion a la Automatizacion (IEA)",
             f"El IEA medio de la muestra es {st['iea_media']:.2f}/10. La distribucion muestra "
             f"que el {pct_bajo:.1f}% de los encuestados se encuentra en riesgo BAJO, "
             f"el {pct_medio:.1f}% en riesgo MEDIO y el {pct_alto:.1f}% en riesgo ALTO. "
             f"Los perfiles mas expuestos combinan poca experiencia laboral, sector con alta "
             f"susceptibilidad de automatizacion (retail, manufactura, administracion) y escasa "
             f"adopcion personal de IA. Esta segmentacion permite a las empresas priorizar planes "
             f"de upskilling diferenciados por perfil (Capitulo 4 y 6 del TFG)."),
            ("C7 - Implicaciones para politicas de RRHH",
             f"Los datos apuntan a que la formacion continua es el factor diferenciador clave. "
             f"Trabajadores con uso habitual de IA presentan puntuaciones IEA inferiores, lo que "
             f"respalda la inversion en programas de capacitacion como estrategia preventiva frente "
             f"a la obsolescencia tecnologica (Capitulo 6: El futuro del trabajo)."),
            ("C8 - Limitaciones y lineas futuras",
             f"La muestra (n={n}) es representativa del entorno cercano del investigador, con "
             f"sesgo hacia perfiles jovenes del sector tech. Futuros estudios deberian ampliar "
             f"la muestra a sectores tradicionales y franjas de edad superiores para contrastar "
             f"si la baja preocupacion observada es generalizable o especifica del colectivo "
             f"tecnologico."),
        ]
        for titulo_c, texto_c in conclusiones_pdf:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_fill_color(235, 242, 250)
            pdf.cell(0, 6, lat1(titulo_c), ln=True, fill=True)
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(0, 5, lat1(texto_c))
            pdf.ln(4)

        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(130, 130, 130)
        pdf.cell(0, 5, lat1(
            f"Generado por analisis_encuesta.py  |  "
            f"TFG — Universidad Pontificia de Salamanca — {datetime.now().year}"
        ), ln=True, align="C")

        pdf.output(ruta_pdf)
        print(f"[✓] PDF generado correctamente: {os.path.abspath(ruta_pdf)}")

    except Exception:
        print("[ERROR] Fallo en la generacion del PDF:")
        traceback.print_exc()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── Carga de datos ────────────────────────────────────────────────────────────

def cargar_csv(ruta):
    if not os.path.isfile(ruta):
        print(f"[ERROR] No se encontro el archivo: {ruta}")
        sys.exit(1)
    datos = []
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader, None)
        for fila in reader:
            if len(fila) > 4:
                datos.append(fila)
    return datos


# ── Entrada principal ─────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Uso:")
        print("  python3 analisis_encuesta.py encuesta.csv")
        print("  python3 analisis_encuesta.py encuesta.csv -o resultado.txt")
        print("  python3 analisis_encuesta.py encuesta.csv -p informe.pdf")
        sys.exit(1)

    ruta_csv = sys.argv[1]
    datos = cargar_csv(ruta_csv)
    st    = calcular_stats(datos)

    if "-p" in sys.argv:
        idx = sys.argv.index("-p")
        ruta_pdf = sys.argv[idx+1] if idx+1 < len(sys.argv) else "informe.pdf"
        generar_pdf(ruta_pdf, datos, st)
    elif "-o" in sys.argv:
        idx = sys.argv.index("-o")
        salida = sys.argv[idx+1] if idx+1 < len(sys.argv) else "resultado.txt"
        buf = io.StringIO()
        sys.stdout = buf
        analizar_todo(datos, st)
        sys.stdout = sys.__stdout__
        texto = buf.getvalue()
        print(texto)
        with open(salida, "w", encoding="utf-8") as f:
            f.write(texto)
        print(f"[✓] Guardado en: {salida}")
    else:
        menu_interactivo(datos, st)


if __name__ == "__main__":
    main()
