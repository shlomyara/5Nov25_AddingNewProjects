
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
        "main": [
            174.058, 197.084, 127.063, 147.055, 87.055,
            200.095, 170.113, 207.113, 114.042, 114.042,
            101.047, 129.042, 131.040
        ],
        "list2_raw": [
            174.058, 173.051, 197.084, 127.063, 147.055,
            87.055, 200.095, 170.113, 207.113, 114.042,
            101.047, 129.042, 130.032, 131.040, 42.010,
            0.984, 2.015, '+71.037', '+242.109', '+56.06', '-15.977', '+252.082',
            '+230.11', '-18.010', '-14.015', '-17.026',
            '+100.05', '+222.06', '-33.987', '-1.007', '+1896.83'
        ]
    },
    "I_Tide_Syclic": {
        "main": [
            173.051, 197.084, 127.063, 147.055, 87.055,
            200.095, 170.113, 207.113, 114.042, 114.042,
            101.047, 129.042, 130.032
        ],
        "list2_raw": [
            87.055, 114.042, 130.032, '+71.037', '+56.06', '-15.977', '+1896.83'
        ]
    },
    "S_Tide": {
        "main": [
             138.066, 97.052, 128.058, 57.021, 101.047, 147.068, 101.047, 87.032, 115.026,
             163.063, 87.032, 128.094, 163.063, 113.084, 115.026, 129.042, 156.101, 71.037,
             71.037, 128.094, 115.026, 147.068, 113.084, 128.094, 186.079, 113.084, 129.042,
             87.032, 87.055, 57.021, 57.021, 87.032, 57.021, 87.032, 57.021, 129.042, 297.243
        ],
        "list2_raw": [
            138.066, 97.052, 128.058, 57.021, 101.047, 87.032, 115.026,
            87.032, 128.094, 163.063, 113.084, 129.042, 156.101, 71.037,
            115.026, 147.068, 186.079, 129.042,
            129.042, 297.243, 42.010, 0.984, 2.015, '+71.037', '+242.109', '+56.06', '-15.977', '+252.082',
            '+230.11', '-18.010', '-14.015', '-17.026',
            '+100.05', '+222.06', '-33.987', '-1.007'
        ]
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
                st.experimental_rerun()
    with col2:
        if st.button("Delete", key="delete_btn"):
            delete_dataset(selected_manage)
            st.experimental_rerun()
    with col3:
        if st.button("Reload Cloud Data", key="reload_btn"):
            st.experimental_rerun()
else:
    st.info("No cloud datasets found yet. Add one above 👆")
# ===========================================================
# 🔧 CALCULATION LOGIC
# ===========================================================
list2_add, list2_sub = [], []
for item in list2_raw:
    if isinstance(item, str):
        if item.startswith('+'):
            list2_add.append(float(item[1:]))
        elif item.startswith('-'):
            list2_sub.append(float(item[1:]))
        else:
            try:
                val = float(item)
                list2_add.append(val)
                list2_sub.append(val)
            except:
                pass
    else:
        list2_add.append(item)
        list2_sub.append(item)
st.subheader("⚙️ Choose combination types:")
run_main_only = st.checkbox(f"{selected_list_name} only", True)
run_additions = st.checkbox(f"{selected_list_name} + additions", True)
run_subtractions = st.checkbox(f"{selected_list_name} - subtractions", True)
run_sub_add = st.checkbox(f"{selected_list_name} - sub + add", True)
run_list2_only = st.checkbox("List2 only combinations", False)
def within_tolerance(value):
    return abs(value - target) <= tolerance
def add_result(description, value, steps, results):
    if within_tolerance(value):
        error = abs(value - target)
        results.append((len(steps), error, description, value, error))
st.divider()
run_button = st.button("▶️ Run Matching Search")
results = []
if run_button:
    with st.spinner("Running calculations... please wait ⏳"):
        progress = st.progress(0)
        total_steps, current_step = 1, 0
        if run_main_only:
            add_result(f"{selected_list_name} only", sum_selected, [], results)
            progress.progress(0.05)
        if run_additions:
            for r in range(1, 4):
                for combo in itertools.combinations_with_replacement(list2_add, r):
                    value = sum_selected + sum(combo)
                    add_result(f"{selected_list_name} + {combo}", value, combo, results)
        if run_subtractions:
            for r in range(1, 4):
                for combo in itertools.combinations(list2_sub, r):
                    value = sum_selected - sum(combo)
                    add_result(f"{selected_list_name} - {combo}", value, combo, results)
        if run_sub_add:
            for sub in list2_sub:
                for add in list2_add:
                    value = sum_selected - sub + add
                    add_result(f"{selected_list_name} - ({sub},) + ({add},)", value, [sub, add], results)
        if run_list2_only:
            all_list2 = list2_add + [-v for v in list2_sub]
            for r in range(2, 6):
                for combo in itertools.combinations_with_replacement(all_list2, r):
                    value = sum(combo)
                    add_result(f"List2 only {combo}", value, combo, results)
        progress.progress(1.0)
    if results:
        st.success(f"✅ Found {len(results)} matches within ±{tolerance:.5f}")
        for _, _, desc, val, error in sorted(results, key=lambda x: (x[0], x[1])):
            st.write(f"🔹 `{desc}` = **{val:.5f}** (error: {error:.5f})")
    else:
        st.warning("No matches found with current settings.")
