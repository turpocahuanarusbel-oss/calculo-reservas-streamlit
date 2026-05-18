import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO

st.set_page_config(
    page_title="Sistema de Evaluación de Reservas Minerales",
    page_icon="⛏️",
    layout="wide"
)

# --------------------------
# ESTILO
# --------------------------
st.markdown("""
    <style>
    .main-title {
        font-size: 40px;
        font-weight: 800;
        color: #E8EEF7;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 17px;
        color: #B8C4D6;
        margin-bottom: 1.2rem;
    }
    .card {
        background-color: #111827;
        padding: 18px;
        border-radius: 16px;
        border: 1px solid #263244;
        box-shadow: 0 4px 14px rgba(0,0,0,0.25);
    }
    .section-title {
        font-size: 24px;
        font-weight: 700;
        color: #E8EEF7;
        margin-top: 0.6rem;
        margin-bottom: 0.8rem;
    }
    </style>
""", unsafe_allow_html=True)

# --------------------------
# FUNCIONES
# --------------------------
def validar_dataframe(df):
    columnas_requeridas = [
        "Bloque", "Largo_m", "Ancho_m", "Espesor_m",
        "Densidad_t_m3", "Ley_pct"
    ]

    faltantes = [c for c in columnas_requeridas if c not in df.columns]
    if faltantes:
        return False, f"Faltan columnas en el archivo CSV: {', '.join(faltantes)}"

    for col in ["Largo_m", "Ancho_m", "Espesor_m", "Densidad_t_m3", "Ley_pct"]:
        if (df[col] < 0).any():
            return False, f"La columna {col} tiene valores negativos."

    return True, "Archivo válido"


def clasificar_bloque(ley, cutoff):
    if ley < cutoff:
        return "Desmonte"
    elif ley < cutoff * 1.25:
        return "Baja ley"
    elif ley < cutoff * 1.75:
        return "Ley media"
    else:
        return "Alta ley"


def calcular_reservas(df, dilucion_pct, perdida_pct, recuperacion_pct, cutoff_pct):
    df = df.copy()

    df["Es_mineral"] = df["Ley_pct"] >= cutoff_pct
    df["Clasificacion"] = df["Ley_pct"].apply(lambda x: clasificar_bloque(x, cutoff_pct))

    df["Volumen_m3"] = df["Largo_m"] * df["Ancho_m"] * df["Espesor_m"]
    df["Tonelaje_bruto_t"] = df["Volumen_m3"] * df["Densidad_t_m3"]

    df["Tonelaje_mineral_t"] = df.apply(
        lambda x: x["Tonelaje_bruto_t"] if x["Es_mineral"] else 0,
        axis=1
    )

    df["Ley_mineral_pct"] = df.apply(
        lambda x: x["Ley_pct"] if x["Es_mineral"] else 0,
        axis=1
    )

    factor_dilucion = 1 + dilucion_pct / 100
    df["Tonelaje_diluido_t"] = df["Tonelaje_mineral_t"] * factor_dilucion

    df["Ley_diluida_pct"] = df.apply(
        lambda x: x["Ley_mineral_pct"] / factor_dilucion if x["Tonelaje_mineral_t"] > 0 else 0,
        axis=1
    )

    factor_perdida = 1 - perdida_pct / 100
    df["Tonelaje_recuperable_t"] = df["Tonelaje_diluido_t"] * factor_perdida

    df["Contenido_metalico_t"] = df["Tonelaje_recuperable_t"] * df["Ley_diluida_pct"] / 100
    df["Metal_recuperable_t"] = df["Contenido_metalico_t"] * recuperacion_pct / 100

    total_bloques = len(df)
    bloques_mineral = int(df["Es_mineral"].sum())
    bloques_desmonte = total_bloques - bloques_mineral

    volumen_total = df["Volumen_m3"].sum()
    tonelaje_bruto_total = df["Tonelaje_bruto_t"].sum()
    tonelaje_mineral_total = df["Tonelaje_mineral_t"].sum()
    tonelaje_diluido_total = df["Tonelaje_diluido_t"].sum()
    tonelaje_recuperable_total = df["Tonelaje_recuperable_t"].sum()
    contenido_metalico_total = df["Contenido_metalico_t"].sum()
    metal_recuperable_total = df["Metal_recuperable_t"].sum()

    if tonelaje_mineral_total > 0:
        ley_promedio_mineral = (
            (df["Tonelaje_mineral_t"] * df["Ley_mineral_pct"]).sum() / tonelaje_mineral_total
        )
    else:
        ley_promedio_mineral = 0

    if tonelaje_diluido_total > 0:
        ley_promedio_diluida = (
            (df["Tonelaje_diluido_t"] * df["Ley_diluida_pct"]).sum() / tonelaje_diluido_total
        )
    else:
        ley_promedio_diluida = 0

    resumen = {
        "Total de bloques": total_bloques,
        "Bloques minerales": bloques_mineral,
        "Bloques desmonte": bloques_desmonte,
        "Volumen total (m3)": volumen_total,
        "Tonelaje bruto total (t)": tonelaje_bruto_total,
        "Tonelaje mineral total (t)": tonelaje_mineral_total,
        "Ley promedio mineral (%)": ley_promedio_mineral,
        "Tonelaje diluido total (t)": tonelaje_diluido_total,
        "Ley promedio diluida (%)": ley_promedio_diluida,
        "Tonelaje recuperable (t)": tonelaje_recuperable_total,
        "Contenido metálico (t)": contenido_metalico_total,
        "Metal recuperable (t)": metal_recuperable_total,
    }

    return df, resumen


# --------------------------
# BARRA LATERAL
# --------------------------
st.sidebar.title("⚙️ Parámetros técnicos")
st.sidebar.markdown("Configura los parámetros del modelo de evaluación.")

dilucion_pct = st.sidebar.number_input("Dilución (%)", min_value=0.0, value=10.0, step=1.0)
perdida_pct = st.sidebar.number_input("Pérdida minera (%)", min_value=0.0, value=5.0, step=1.0)
recuperacion_pct = st.sidebar.number_input("Recuperación metalúrgica (%)", min_value=0.0, value=90.0, step=1.0)
cutoff_pct = st.sidebar.number_input("Cut-off grade (%)", min_value=0.0, value=1.20, step=0.10)

st.sidebar.markdown("---")
st.sidebar.info(
    "El aplicativo clasifica bloques, calcula tonelajes, ley promedio, contenido metálico "
    "y metal recuperable."
)

# --------------------------
# TITULO
# --------------------------
st.markdown('<div class="main-title">Sistema de Evaluación Simplificada de Reservas Minerales</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Aplicativo técnico para evaluación por bloques, clasificación económica y análisis de recuperación.</div>', unsafe_allow_html=True)

# --------------------------
# CARGA DE DATOS
# --------------------------
st.markdown('<div class="section-title">1. Carga y validación de datos</div>', unsafe_allow_html=True)

archivo = st.file_uploader("Cargar archivo CSV de bloques mineralizados", type=["csv"])

if archivo is not None:
    try:
        df_bloques = pd.read_csv(archivo)
        st.success("Archivo cargado correctamente.")
    except Exception as e:
        st.error(f"Error al leer el archivo: {e}")
        st.stop()
else:
    try:
        df_bloques = pd.read_csv("datos_bloques.csv")
        st.info("Se está usando el archivo de ejemplo: datos_bloques.csv")
    except Exception:
        st.error("No se encontró el archivo datos_bloques.csv en la misma carpeta del programa.")
        st.stop()

valido, mensaje = validar_dataframe(df_bloques)
if not valido:
    st.error(mensaje)
    st.stop()

# --------------------------
# CALCULO
# --------------------------
df_resultados, resumen = calcular_reservas(
    df_bloques,
    dilucion_pct=dilucion_pct,
    perdida_pct=perdida_pct,
    recuperacion_pct=recuperacion_pct,
    cutoff_pct=cutoff_pct
)

# --------------------------
# KPIs
# --------------------------
st.markdown('<div class="section-title">2. Indicadores principales</div>', unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Bloques minerales", int(resumen["Bloques minerales"]))
k2.metric("Bloques desmonte", int(resumen["Bloques desmonte"]))
k3.metric("Tonelaje recuperable (t)", f'{resumen["Tonelaje recuperable (t)"]:.2f}')
k4.metric("Metal recuperable (t)", f'{resumen["Metal recuperable (t)"]:.2f}')

k5, k6, k7, k8 = st.columns(4)
k5.metric("Volumen total (m³)", f'{resumen["Volumen total (m3)"]:.2f}')
k6.metric("Tonelaje bruto total (t)", f'{resumen["Tonelaje bruto total (t)"]:.2f}')
k7.metric("Ley promedio mineral (%)", f'{resumen["Ley promedio mineral (%)"]:.2f}')
k8.metric("Ley promedio diluida (%)", f'{resumen["Ley promedio diluida (%)"]:.2f}')

# --------------------------
# TABS
# --------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Datos de entrada",
    "📊 Resultados por bloque",
    "📈 Visualización",
    "🧾 Resumen ejecutivo"
])

with tab1:
    st.markdown("### Base de datos de entrada")
    st.dataframe(df_bloques, use_container_width=True)

with tab2:
    st.markdown("### Evaluación detallada por bloque")
    columnas_mostrar = [
        "Bloque", "Clasificacion", "Ley_pct", "Es_mineral",
        "Volumen_m3", "Tonelaje_bruto_t", "Tonelaje_mineral_t",
        "Tonelaje_diluido_t", "Ley_diluida_pct",
        "Tonelaje_recuperable_t", "Contenido_metalico_t", "Metal_recuperable_t"
    ]
    st.dataframe(df_resultados[columnas_mostrar], use_container_width=True)

    excel_buffer = BytesIO()

with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
    df_resultados.to_excel(writer, index=False, sheet_name="Resultados")
    df_bloques.to_excel(writer, index=False, sheet_name="Datos_entrada")

excel_data = excel_buffer.getvalue()

st.download_button(
    label="⬇️ Descargar resultados en Excel",
    data=excel_data,
    file_name="resultados_reservas_profesional.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

with tab3:
    st.markdown("### Análisis gráfico")

    fig1 = px.bar(
        df_resultados,
        x="Bloque",
        y="Tonelaje_recuperable_t",
        color="Clasificacion",
        title="Tonelaje recuperable por bloque",
        text_auto=".2f"
    )
    fig1.update_layout(xaxis_title="Bloque", yaxis_title="Tonelaje recuperable (t)")
    st.plotly_chart(fig1, use_container_width=True)

    fig2 = px.bar(
        df_resultados,
        x="Bloque",
        y="Ley_pct",
        color="Clasificacion",
        title="Ley por bloque"
    )
    fig2.add_hline(
        y=cutoff_pct,
        line_dash="dash",
        annotation_text=f"Cut-off = {cutoff_pct:.2f}%",
        annotation_position="top left"
    )
    fig2.update_layout(xaxis_title="Bloque", yaxis_title="Ley (%)")
    st.plotly_chart(fig2, use_container_width=True)

    resumen_clases = df_resultados["Clasificacion"].value_counts().reset_index()
    resumen_clases.columns = ["Clasificacion", "Cantidad"]

    fig3 = px.pie(
        resumen_clases,
        names="Clasificacion",
        values="Cantidad",
        title="Distribución de bloques por clasificación"
    )
    st.plotly_chart(fig3, use_container_width=True)

    fig4 = go.Figure()
    fig4.add_trace(go.Scatter(
        x=df_resultados["Bloque"],
        y=df_resultados["Contenido_metalico_t"],
        mode="lines+markers",
        name="Contenido metálico"
    ))
    fig4.add_trace(go.Scatter(
        x=df_resultados["Bloque"],
        y=df_resultados["Metal_recuperable_t"],
        mode="lines+markers",
        name="Metal recuperable"
    ))
    fig4.update_layout(
        title="Contenido metálico vs metal recuperable",
        xaxis_title="Bloque",
        yaxis_title="Toneladas"
    )
    st.plotly_chart(fig4, use_container_width=True)

with tab4:
    st.markdown("### Resumen técnico del modelo")
    st.write(f"""
**Evaluación general**

- Se evaluaron **{int(resumen["Total de bloques"])} bloques**.
- De ellos, **{int(resumen["Bloques minerales"])}** cumplen el criterio económico del cut-off.
- El **tonelaje bruto total** asciende a **{resumen["Tonelaje bruto total (t)"]:.2f} t**.
- El **tonelaje mineral total** es de **{resumen["Tonelaje mineral total (t)"]:.2f} t**.
- La **ley promedio mineral** es de **{resumen["Ley promedio mineral (%)"]:.2f}%**.
- Luego de aplicar una **dilución de {dilucion_pct:.2f}%** y una **pérdida minera de {perdida_pct:.2f}%**, el **tonelaje recuperable** es de **{resumen["Tonelaje recuperable (t)"]:.2f} t**.
- El **contenido metálico** resultante es de **{resumen["Contenido metálico (t)"]:.2f} t**.
- Con una **recuperación metalúrgica de {recuperacion_pct:.2f}%**, el **metal recuperable final** asciende a **{resumen["Metal recuperable (t)"]:.2f} t**.
""")

    df_resumen = pd.DataFrame({
        "Indicador": list(resumen.keys()),
        "Valor": [round(v, 4) if isinstance(v, float) else v for v in resumen.values()]
    })
    st.dataframe(df_resumen, use_container_width=True)

    st.markdown("### Comentario técnico")
    st.success(
        "El aplicativo permite una evaluación preliminar por bloques, útil para fines académicos, "
        "demostrativos y de análisis inicial. No reemplaza un software especializado de modelamiento "
        "geológico y estimación de reservas."
    )