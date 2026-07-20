import streamlit as st
import pandas as pd
from datetime import date
import requests
import uuid
import io 

# --- NASTAVENIA STRÁNKY ---
st.set_page_config(page_title="Minúty 2026", layout="centered")

# --- GITHUB GIST KONFIGURÁCIA ---
GIST_ID = st.secrets["github"]["gist_id"]
TOKEN = st.secrets["github"]["token"]
NAMES_FILE = "Zoznam_mien.txt"

# --- VÝBER ČLNU V ĽAVOM PANELU ---
st.sidebar.header("Správa dát")
vybrany_cln = st.sidebar.selectbox(
    "Aktuálny čln:",
    options=["🔴 Červený čln", "🟡 Žltý čln"],
    index=0  
)

if vybrany_cln == "🔴 Červený čln":
    DATA_FILE = "data.csv"
else:
    DATA_FILE = "data_zlty.csv"

# --- POMOCNÉ FUNKCIE PRE GIST ---
def load_from_gist(filename, default_content=""):
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {TOKEN}"}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            files = response.json().get('files', {})
            if filename in files:
                return files[filename]['content']
        return default_content
    except:
        return default_content

def save_to_gist(filename, content):
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {TOKEN}"}
    payload = {"files": {filename: {"content": content}}}
    requests.patch(url, headers=headers, json=payload)

# --- FUNKCIE PRE DÁTA ---
def load_names():
    content = load_from_gist(NAMES_FILE, "Jozef\nMichal\n")
    return sorted([line.strip() for line in content.splitlines() if line.strip()])

def save_name(new_name):
    names = load_names()
    if new_name not in names:
        names.append(new_name)
        save_to_gist(NAMES_FILE, "\n".join(names))

def load_data():
    content = load_from_gist(DATA_FILE, "ID,Date,Meno,Hodnota,Tankovanie")
    df = pd.read_csv(io.StringIO(content))
    if not df.empty:
        df['Date'] = pd.to_datetime(df['Date']).dt.date
        df['Hodnota'] = df['Hodnota'].astype(str).str.zfill(3)
    return df

def save_data(df):
    df['Hodnota'] = df['Hodnota'].astype(str).str.zfill(3)
    csv_content = df.to_csv(index=False)
    save_to_gist(DATA_FILE, csv_content)

# --- VÝPOČET MINÚT ---
def process_dataframe(df):
    if df.empty:
        return df
    
    def prep_sort(group):
        vals = group['Hodnota'].astype(int)
        has_high = (vals >= 900).any()
        has_low = (vals <= 100).any()
        if has_high and has_low:
            group['SortValue'] = group['Hodnota'].apply(lambda x: int(x) + 1000 if int(x) < 500 else int(x))
        else:
            group['SortValue'] = vals
        return group

    processed_days = []
    unique_dates = sorted(df['Date'].unique())
    for d in unique_dates:
        day_df = df[df['Date'] == d].copy()
        day_df = prep_sort(day_df)
        processed_days.append(day_df)
    
    full_df = pd.concat(processed_days)
    full_df = full_df.sort_values(['Date', 'SortValue'])
    
    vals = full_df['Hodnota'].astype(int).tolist()
    minutes = []
    prev_val = None
    for v in vals:
        if prev_val is None:
            minutes.append(0)
        else:
            diff = v - prev_val
            if diff < -500: diff += 1000
            minutes.append(diff)
        prev_val = v
        
    full_df['Minúty'] = minutes
    return full_df.sort_values(['Date', 'SortValue'], ascending=[False, False])

# --- CALLBACK ---
def save_record_callback():
    hodnota_in = st.session_state.get('input_hodnota', '')
    pridat_nove = st.session_state.get('pridat_nove_checkbox', False)
    vybrane_meno = st.session_state.get('vybrane_meno_selectbox', None)
    nove_meno = st.session_state.get('input_nove_meno', '')
    zaznam_datum = st.session_state.get('zaznam_datum', date.today())
    
    if not pridat_nove and (vybrane_meno is None or vybrane_meno == ""):
        st.session_state.action_msg = ("error", "Vyber meno lyžiara alebo pridaj nové!")
        return

    meno_na_zapis = nove_meno if pridat_nove else vybrane_meno
    if not hodnota_in.isdigit():
        st.session_state.action_msg = ("error", "Zadaj číselnú hodnotu!")
        return
    
    if pridat_nove:
        save_name(meno_na_zapis)
        
    tank = []
    if st.session_state.get('input_t20', False): tank.append("20 L")
    if st.session_state.get('input_t40', False): tank.append("40 L")
    
    new_row = {
        "ID": str(uuid.uuid4()),
        "Date": zaznam_datum,
        "Meno": meno_na_zapis,
        "Hodnota": hodnota_in.zfill(3),
        "Tankovanie": " + ".join(tank) if tank else "-"
    }
    
    current_df = load_data()
    updated_df = pd.concat([current_df, pd.DataFrame([new_row])], ignore_index=True)
    save_data(updated_df)
    
    st.session_state.input_hodnota = ""
    st.session_state.pridat_nove_checkbox = False
    st.session_state.input_t20 = False
    st.session_state.input_t40 = False
    st.session_state.vybrane_meno_selectbox = None
    if 'input_nove_meno' in st.session_state:
        st.session_state.input_nove_meno = ""
    st.session_state.action_msg = ("success", "Záznam uložený do Cloudu!")

# --- HLAVNÁ APP ---
if vybrany_cln == "🔴 Červený čln":
    st.title("Minúty 2026 🏄")
else:
    st.title(f"Minúty 2026 – {vybrany_cln} 🏄")

raw_df = load_data()
full_df_with_minutes = process_dataframe(raw_df)

# --- BOČNÝ PANEL ---
if not full_df_with_minutes.empty:
    export_df = full_df_with_minutes.copy().sort_values(['Date', 'SortValue'])
    export_df = export_df[['Date', 'Meno', 'Hodnota', 'Minúty', 'Tankovanie']]
