import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from io import BytesIO

# --- 1. CONFIGURACIÓN ---
st.set_page_config(
    page_title="Admin de Gastos V2.0", 
    page_icon="🧾", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. SISTEMA DE SEGURIDAD (LOGIN) ---
def check_password():
    """Retorna True si el usuario ingresó la contraseña correcta."""
    SECRETO = "CS2026"  # Tu contraseña

    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    # Interfaz de Login
    st.markdown("""<style>.stTextInput > label {display:none;}</style>""", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔒 Acceso Restringido")
        st.caption("Administrador de Gastos CS")
        pwd_input = st.text_input("Ingrese Clave de Acceso", type="password")
        
        if st.button("Ingresar"):
            if pwd_input == SECRETO:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("⛔ Clave incorrecta")
            
    return False

if not check_password():
    st.stop()

# ==========================================
# --- 3. LÓGICA DE GASTOS ---
# ==========================================

st.title("📂 Administrador de Gastos (XML a Excel)")
st.markdown("Sube tus facturas para generar el reporte contable y detectar duplicados.")

# --- CATÁLOGO FORMAS DE PAGO SAT ---
CATALOGO_PAGO = {
    "01": "01 Efectivo",
    "02": "02 Cheque nominativo",
    "03": "03 Transferencia electrónica de fondos",
    "04": "04 Tarjeta de crédito",
    "05": "05 Monedero electrónico",
    "06": "06 Dinero electrónico",
    "08": "08 Vales de despensa",
    "28": "28 Tarjeta de débito",
    "29": "29 Tarjeta de servicios",
    "99": "99 Por definir"
}

def get_forma_pago_texto(codigo):
    return CATALOGO_PAGO.get(codigo, f"{codigo} (Otro)")

# --- FUNCIÓN DE LIMPIEZA ---
def strip_namespace(tag):
    if '}' in tag:
        return tag.split('}', 1)[1]
    return tag

# --- FUNCIÓN DE PARSEO ---
def parsear_xml(file):
    try:
        tree = ET.parse(file)
        root = tree.getroot()
        
        data = {
            "Fecha": "",
            "Forma Pago": "",
            "Emisor": "",
            "RFC": "",
            "Lugar Exp. (CP)": "", # Nuevo Campo
            "Subtotal": 0.0,
            "IVA": 0.0,
            "Otros Imp": 0.0,
            "Total": 0.0,
            "UUID": "",
            "Archivo": file.name
        }

        # 1. Datos Generales
        data["Fecha"] = root.get("Fecha", "").split("T")[0]
        data["Lugar Exp. (CP)"] = root.get("LugarExpedicion", "N/A") # Código Postal
        
        # Forma de Pago (Traducción)
        codigo_pago = root.get("FormaPago", "99")
        data["Forma Pago"] = get_forma_pago_texto(codigo_pago)
        
        data["Subtotal"] = float(root.get("SubTotal", "0"))
        data["Total"] = float(root.get("Total", "0"))

        # 2. Navegar Nodos
        iva_acumulado = 0.0
        otros_impuestos = 0.0
        
        for child in root:
            tag = strip_namespace(child.tag)
            
            if tag == "Emisor":
                data["Emisor"] = child.get("Nombre", "Sin Nombre")
                data["RFC"] = child.get("Rfc", "")
            
            if tag == "Complemento":
                for sub in child:
                    if strip_namespace(sub.tag) == "TimbreFiscalDigital":
                        data["UUID"] = sub.get("UUID", "")

            if tag == "Impuestos":
                for imp in child:
                    if strip_namespace(imp.tag) == "Traslados":
                        for tras in imp:
                            tipo = tras.get("Impuesto", "")
                            monto = float(tras.get("Importe", "0"))
                            if tipo == "002":
                                iva_acumulado += monto
                            else:
                                otros_impuestos += monto
                    
                    if strip_namespace(imp.tag) == "Retenciones":
                        for ret in imp:
                            otros_impuestos += float(ret.get("Importe", "0"))

        data["IVA"] = iva_acumulado
        data["Otros Imp"] = otros_impuestos
        
        # Ajuste de seguridad
        if iva_acumulado == 0 and otros_impuestos == 0:
            diff = data["Total"] - data["Subtotal"]
            if diff > 0: data["IVA"] = diff

        return data

    except Exception as e:
        st.error(f"Error en {file.name}: {e}")
        return None

# --- INTERFAZ DE CARGA ---
uploaded_files = st.file_uploader("Arrastra aquí tus archivos XML", type=["xml"], accept_multiple_files=True)

if uploaded_files:
    lista_datos = []
    with st.spinner("Procesando facturas..."):
        for f in uploaded_files:
            info = parsear_xml(f)
            if info:
                lista_datos.append(info)
    
    if lista_datos:
        df = pd.DataFrame(lista_datos)
        
        # --- DETECCIÓN DE DUPLICADOS ---
        # Buscamos UUIDs repetidos en el lote subido
        duplicados = df[df.duplicated(subset=['UUID'], keep=False)]
        
        if not duplicados.empty:
            st.error(f"⚠️ ¡ALERTA! Se detectaron {len(duplicados)} facturas duplicadas (Mismo UUID). Revísalas abajo:")
            st.dataframe(duplicados[["Archivo", "Total", "Emisor", "UUID"]], use_container_width=True)
            st.markdown("---")
            # Opcional: Eliminar duplicados automáticamente para el reporte final
            # df = df.drop_duplicates(subset=['UUID']) 
            # st.info("Se han eliminado los duplicados del reporte final.")

        # Ordenar columnas
        cols = ["Fecha", "Forma Pago", "Emisor", "RFC", "Lugar Exp. (CP)", 
                "Subtotal", "IVA", "Otros Imp", "Total", "Archivo"]
        df = df[cols]
        
        # Mostrar Tabla
        st.success(f"✅ Reporte generado con {len(df)} registros únicos.")
        st.dataframe(df, use_container_width=True)
        
        # Totales
        c1, c2, c3 = st.columns(3)
        with c1: st.metric("Gasto Total", f"${df['Total'].sum():,.2f}")
        with c2: st.metric("IVA Total", f"${df['IVA'].sum():,.2f}")
        with c3: st.metric("Subtotal", f"${df['Subtotal'].sum():,.2f}")
        
        # --- EXPORTAR A EXCEL ---
        def to_excel(dataframe):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                dataframe.to_excel(writer, index=False, sheet_name='Gastos')
                workbook = writer.book
                worksheet = writer.sheets['Gastos']
                money_fmt = workbook.add_format({'num_format': '$#,##0.00'})
                worksheet.set_column('F:I', 15, money_fmt) # Formato moneda a columnas F,G,H,I
            return output.getvalue()

        excel_file = to_excel(df)
        
        st.download_button(
            label="📥 Descargar Excel",
            data=excel_file,
            file_name="Reporte_Gastos_CS.xlsx",
            mime="application/vnd.ms-excel"
        )
