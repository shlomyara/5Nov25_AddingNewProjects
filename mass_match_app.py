import streamlit as st
import itertools
import pandas as pd
import io
import time
import json
from supabase import create_client

# --- Title ---
st.title("🧮 MassMatchFinder | Upload & Manage Datasets")
st.markdown("""
Enter a target mass and tolerance, choose or create a dataset,  
and select which combinations to run.  
You can upload, type, or select from built-in or cloud-saved datasets.
""")

# --- Inputs ---
target = st.number_input("🎯 Target number to match", format="%.5f")
tolerance = st.number_input("🎯 Acceptable error/tolerance (e.g., 0.1)", value=0.1, format="%.5f")

# ===========================================================
# ☁️ SUPABASE CONNECTION
# ===========================================================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Helper Functions ---
def load_all_datasets():
    """Fetch all user-saved datasets from Supabase."""
    try:
        res = supabase.table("datasets").select("*").execute()
        rows = res.data or []
        data = {}
        for r in rows:
            try:
                data[r["name"]] = {
                    "main": json.loads(r["main_list"]),
                    "list2_raw": json.loads(r["list2_list"])
                }
            except Exception:
                pass
        return data
    except Exception as e:
        st.error(f"❌ Failed to load datasets: {e}")
        return {}

def save_dataset(name, main_list, list2_list):
    """Save (insert or update) a dataset in Supabase."""
    try:
        supabase.table("datasets").upsert({
            "name": name,
            "main_list": json.dumps(main_list),
            "list2_list": json.dumps(list2_list)
        }).execute()
        st.success(f"✅ Saved '{name}' to cloud.")
    except Exception as e:
        st.error(f"❌ Failed to save dataset to cloud: {e}")

def rename_dataset(old_name, new_name):
    """Rename an existing dataset."""
    try:
        supabase.table("datasets").update({"name": new_name}).eq("name", old_name).execute()
        st.success(f"✅ Renamed '{old_name}' → '{new_name}'")
    except Exception as e:
        st.error(f"❌ Failed to rename: {e}")

def delete_dataset(name):
    """Delete a dataset permanently."""
    try:
        supabase.table("datasets").delete().eq("name", name).execute()
        st.warning(f"🗑️ Deleted dataset '{name}' from cloud.")
    except Exception as e:
        st.error(f"❌ Failed to delete: {e}")

# ===========================================================
# 📚 BUILT-IN DATASETS
# ===========================================================
data_config = {
    "I_Tide_Linear": {
        "main": [174.058, 197.084, 127.063, 147.055, 87.055, 200.095, 170.113, 207.113, 114.042, 114.042, 101.047, 129.042, 131.040],
        "list2_raw": [174.058, 173.051, 197.084, 127.063, 147.055, 87.055, 200.095, 170.113, 207.113, 114.042, 101.047, 129.042, 130.032, 131.040]
    },
    "I_Tide_Syclic": {
        "main": [173.051, 197.084, 127.063, 147.055, 87.055, 200.095, 170.113, 207.113, 114.042, 114.042, 101.047, 129.042, 130.032],
        "list2_raw": [87.055, 114.042, 130.032, '+71.037', '+56.06', '-15.977', '+1896.83']
    },
    "S_Tide": {
        "main": [138.066, 97.052, 128.058, 57.021, 101.047],
        "list2_raw": [138.066, 97.052, 128.058, '+71.037']
    }
}

# --- Merge with Cloud Data ---
cloud_data = load_all_datasets()
data_config.update(cloud_data)

# ===========================================================
# 📤 UPLOAD FILE
# ===========================================================
st.subheader("📤 Upload your own dataset (optional)")
uploaded_file = st.file_uploader("Upload a .csv or .txt file", type=["csv", "txt"])

def parse_uploaded_file(file):
    """Parse uploaded file into main_list and list2_list."""
    content = file.read().decode("utf-8").strip()
    try:
        df = pd.read_csv(io.StringIO(content))
        if df.shape[1] >= 2:
            main_list = df.iloc[:, 0].dropna().astype(float).tolist()
            list2_list = [str(x) for x in df.iloc[:, 1].dropna().tolist()]
            return main_list, list2_list
        else:
            main_list = df.iloc[:, 0].dropna().astype(float).tolist()
            return main_list, main_list
    except Exception:
        pass
    try:
        items = [float(x.strip()) for x in content.replace("\n", ",").split(",") if x.strip()]
        return items, items
    except Exception:
        raise ValueError("Could not parse file format.")

if uploaded_file is not None:
    try:
        main_list, list2_list = parse_uploaded_file(uploaded_file)
        name = uploaded_file.name.split(".")[0]
        save_dataset(name, main_list, list2_list)
        data_config[name] = {"main": main_list, "list2_raw": list2_list}
        st.success(f"✅ Uploaded dataset '{name}' added and saved to cloud.")
    except Exception as e:
        st.error(f"Error reading file: {e}")

# ===========================================================
# ✍️ MANUAL LIST ENTRY
# ===========================================================
st.subheader("✍️ Add a New Custom Dataset")
with st.expander("➕ Add New Custom Dataset"):
    custom_name = st.text_input("Dataset name (e.g., MyExperiment1)")
    main_text = st.text_area("Main list values", "")
    list2_text = st.text_area("List2 modifiers", "")

if st.button("Add Custom Dataset"):
    try:
        main_list = [float(x.strip()) for x in main_text.replace("\n", ",").split(",") if x.strip()]
        if list2_text.strip():
            list2_raw = [x.strip() for x in list2_text.replace("\n", ",").split(",") if x.strip()]
        else:
            list2_raw = main_list
        if not custom_name:
            custom_name = f"Custom_{len(data_config) + 1}"
        data_config[custom_name] = {"main": main_list, "list2_raw": list2_raw}
        save_dataset(custom_name, main_list, list2_raw)
        st.success(f"✅ Custom dataset '{custom_name}' added and saved to cloud.")
        st.rerun()
    except Exception as e:
        st.error(f"Error adding dataset: {e}")

# ===========================================================
# 📂 SELECT DATASET
# ===========================================================
selected_list_name = st.selectbox("Select dataset to use:", list(data_config.keys()))
selected_data = data_config[selected_list_name]
selected_list = selected_data["main"]
sum_selected = sum(selected_list)
list2_raw = selected_data["list2_raw"]
st.markdown(f"**Using `{selected_list_name}`** with {len(list2_raw)} modifiers.")

# ===========================================================
# 🗂️ CLOUD DATASET MANAGEMENT
# ===========================================================
st.divider()
st.subheader("🗂️ Manage Cloud Datasets")

if cloud_data:
    selected_manage = st.selectbox("Select dataset to manage:", list(cloud_data.keys()))
    col1, col2, col3 = st.columns(3)
    with col1:
        new_name = st.text_input("Rename to:", key="rename_input")
        if st.button("Rename", key="rename_btn"):
            if new_name.strip():
                rename_dataset(selected_manage, new_name.strip())
                st.rerun()
    with col2:
        if st.button("Delete", key="delete_btn"):
            delete_dataset(selected_manage)
            st.rerun()
    with col3:
        if st.button("Reload Cloud Data", key="reload_btn"):
            st.rerun()
else:
    st.info("No cloud datasets found yet. Add one above 👆")
