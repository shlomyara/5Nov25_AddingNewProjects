import streamlit as st
import itertools, json, os, pandas as pd
from supabase import create_client, Client
from streamlit.runtime.scriptrunner import RerunException, get_script_run_ctx

# ════════════════════════════════════════════════
# 🔐 Supabase Connection
# ════════════════════════════════════════════════
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ════════════════════════════════════════════════
# 📁 Global Name Storage (JSON File)
# ════════════════════════════════════════════════
NAME_FILE = "global_names.json"

def load_global_names():
    """Load global name mappings from file or create default."""
    if os.path.exists(NAME_FILE):
        with open(NAME_FILE, "r") as f:
            return json.load(f)
    default_map = {
        "-1.007": "Hydrogen loss",
        "1.008": "Hydrogen gain",
        "2.016": "Deuterium gain",
        "15.995": "Oxygen gain",
        "18.011": "Water loss",
        "17.003": "Ammonia loss",
        "14.003": "Nitrogen addition",
        "43.989": "CO₂ loss"
    }
    with open(NAME_FILE, "w") as f:
        json.dump(default_map, f, indent=2)
    return default_map

def save_global_names(mapping):
    """Save updated name mappings to file."""
    with open(NAME_FILE, "w") as f:
        json.dump(mapping, f, indent=2)

GLOBAL_NAME_MAP = load_global_names()

# ════════════════════════════════════════════════
# 🔁 Utility — Safe Rerun
# ════════════════════════════════════════════════
def rerun():
    ctx = get_script_run_ctx()
    if ctx is not None:
        raise RerunException(ctx)

# ════════════════════════════════════════════════
# ☁️ Dataset Functions
# ════════════════════════════════════════════════
def load_datasets():
    config = {}
    try:
        res = supabase.table("datasets").select("*").execute()
        for r in res.data or []:
            config[r["name"]] = {
                "main": json.loads(r["main_list"]),
                "list2_raw": json.loads(r["list2_list"])
            }
    except Exception as e:
        st.warning(f"Could not load datasets: {e}")
    return config


def save_dataset(name, main_list, list2_list):
    try:
        supabase.table("datasets").upsert({
            "name": name,
            "main_list": json.dumps(main_list),
            "list2_list": json.dumps(list2_list)
        }).execute()
        return True
    except Exception as e:
        st.error(f"Save failed: {e}")
        return False


def rename_dataset(old, new):
    try:
        row = supabase.table("datasets").select("*").eq("name", old).execute()
        if row.data:
            data = row.data[0]
            data["name"] = new
            supabase.table("datasets").delete().eq("name", old).execute()
            supabase.table("datasets").upsert(data).execute()
    except Exception as e:
        st.error(f"Rename failed: {e}")


def delete_dataset(name):
    try:
        supabase.table("datasets").delete().eq("name", name).execute()
        st.success(f"🗑️ Deleted '{name}'")
    except Exception as e:
        st.error(f"Delete failed: {e}")

# ════════════════════════════════════════════════
# 🧮 APP UI
# ════════════════════════════════════════════════
st.title("🧮 MassMatchFinder — Cloud Dataset Manager")

target = st.number_input("🎯 Target mass", format="%.5f")
tolerance = st.number_input("🎯 Tolerance ±", value=0.1, format="%.5f")

data_config = load_datasets()

# ────────────── Manage Global Modifier Names ──────────────
with st.expander("🧩 Manage Global Modifier Names", expanded=False):
    st.markdown("Add or update global names for modifiers. These apply to **all datasets automatically**.")

    # show table
    if GLOBAL_NAME_MAP:
        st.write("### Current Modifier Names")
        st.table(pd.DataFrame([
            {"Number": k, "Name": v} for k, v in sorted(GLOBAL_NAME_MAP.items(), key=lambda x: float(x[0]))
        ]))
    else:
        st.info("No global modifier names yet.")

    # add new
    st.divider()
    st.write("### ➕ Add or Update Name")
    num_val = st.text_input("Number (e.g. -1.007)")
    name_val = st.text_input("Description (e.g. Hydrogen loss)")
    if st.button("💾 Save Name"):
        if num_val and name_val:
            GLOBAL_NAME_MAP[num_val.strip()] = name_val.strip()
            save_global_names(GLOBAL_NAME_MAP)
            st.success(f"Saved {num_val} → {name_val}")
            rerun()
        else:
            st.warning("Please fill both fields.")

    # delete existing
    st.divider()
    del_key = st.selectbox("🗑️ Delete a name", ["-- Select --"] + list(GLOBAL_NAME_MAP.keys()))
    if st.button("Delete Selected"):
        if del_key != "-- Select --":
            GLOBAL_NAME_MAP.pop(del_key, None)
            save_global_names(GLOBAL_NAME_MAP)
            st.success(f"Deleted {del_key}")
            rerun()
        else:
            st.warning("Select a name to delete.")

# ────────────── ADD NEW DATASET (COLLAPSIBLE) ──────────────
with st.expander("➕ Add New Dataset", expanded=False):
    name = st.text_input("Dataset name")
    main_text = st.text_area("Main list values (comma or newline separated)")
    list2_text = st.text_area("List2 modifiers (optional, use + or - signs)")

    if st.button("💾 Save Dataset"):
        try:
            main_list = [float(x.strip()) for x in main_text.replace("\n", ",").split(",") if x.strip()]
            list2_list = [x.strip() for x in list2_text.replace("\n", ",").split(",") if x.strip()] or main_list
            if name:
                if save_dataset(name, main_list, list2_list):
                    st.success(f"✅ Dataset '{name}' saved.")
                    rerun()
            else:
                st.warning("Please enter a dataset name.")
        except Exception as e:
            st.error(f"Error: {e}")

# ────────────── SELECT DATASET ──────────────
if not data_config:
    st.info("No datasets found.")
    st.stop()

st.divider()
selected_name = st.selectbox("Select dataset:", list(data_config.keys()))
selected_data = data_config[selected_name]
main_list = selected_data["main"]
list2_raw = selected_data["list2_raw"]

# ════════════════════════════════════════════════
# ⚙️ Settings
# ════════════════════════════════════════════════
st.divider()
st.subheader("⚙️ Combination Settings")

run_main_only = st.checkbox(f"{selected_name} only", True)
run_additions = st.checkbox("Include + modifiers", True)
run_subtractions = st.checkbox("Include - modifiers", True)
run_sub_add = st.checkbox("Include - and + combined", True)
run_list2_only = st.checkbox("List2-only combos", False)

# ════════════════════════════════════════════════
# 🧠 Helpers
# ════════════════════════════════════════════════
def within_tolerance(value): return abs(value - target) <= tolerance
def add_result(desc, val, steps, results):
    if within_tolerance(val):
        err = abs(val - target)
        results.append((len(steps), err, desc, val, err))

def get_global_name(num):
    """Find human-readable name from global map"""
    for k, v in GLOBAL_NAME_MAP.items():
        try:
            if abs(float(k) - float(num)) < 1e-5:
                return v
        except:
            continue
    return None

# Split modifiers
list2_add, list2_sub = [], []
for item in list2_raw:
    try:
        if isinstance(item, str):
            if item.startswith('+'): list2_add.append(float(item[1:]))
            elif item.startswith('-'): list2_sub.append(float(item[1:]))
            else:
                val = float(item)
                list2_add.append(val)
                list2_sub.append(val)
        else:
            list2_add.append(item)
            list2_sub.append(item)
    except:
        pass

# ════════════════════════════════════════════════
# ▶️ Run Matching Search
# ════════════════════════════════════════════════
st.divider()
if st.button("▶️ Run Matching Search"):
    results = []
    total_main = sum(main_list)
    progress = st.progress(0)
    done = 0

    if run_main_only:
        add_result(f"{selected_name} only", total_main, [], results)

    if run_additions:
        for r in range(1, 4):
            for combo in itertools.combinations_with_replacement(list2_add, r):
                add_result(f"+{combo}", total_main + sum(combo), combo, results)
                done += 1
                if done % 200 == 0: progress.progress(min(done / 5000, 1.0))

    if run_subtractions:
        for r in range(1, 4):
            for combo in itertools.combinations(list2_sub, r):
                add_result(f"-{combo}", total_main - sum(combo), combo, results)
                done += 1
                if done % 200 == 0: progress.progress(min(done / 5000, 1.0))

    if run_sub_add:
        for sub in list2_sub:
            for add in list2_add:
                add_result(f"-{sub} +{add}", total_main - sub + add, [sub, add], results)
                done += 1
                if done % 200 == 0: progress.progress(min(done / 5000, 1.0))

    if run_list2_only:
        combined = list2_add + [-v for v in list2_sub]
        for r in range(2, 6):
            for combo in itertools.combinations_with_replacement(combined, r):
                add_result(f"List2 {combo}", sum(combo), combo, results)
                done += 1
                if done % 200 == 0: progress.progress(min(done / 5000, 1.0))

    progress.progress(1.0)

    if results:
        st.success(f"✅ Found {len(results)} matches within ±{tolerance:.5f}")
        for _, _, desc, val, err in sorted(results, key=lambda x: (x[0], x[1])):
            st.write(f"🔹 `{desc}` = **{val:.5f}** (error: {err:.5f})")

            # Show names for known numbers
            nums = [float(x) for x in str(desc).replace("(", "").replace(")", "").replace("+", "").replace("-", "").split(",") if x.strip().replace('.', '', 1).isdigit()]
            for n in nums:
                nm = get_global_name(n)
                if nm:
                    st.caption(f"↳ {n} → {nm}")
    else:
        st.warning("No matches found.")
