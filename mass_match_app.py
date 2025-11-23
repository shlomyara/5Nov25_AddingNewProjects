import streamlit as st
import itertools, json, pandas as pd
from supabase import create_client, Client
from streamlit.runtime.scriptrunner import RerunException, get_script_run_ctx

# ════════════════════════════════════════════════
# 🔐 Secure Supabase connection (via Streamlit Secrets)
# ════════════════════════════════════════════════
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ════════════════════════════════════════════════
# 🔁 Utility: Safe Rerun
# ════════════════════════════════════════════════
def rerun():
    ctx = get_script_run_ctx()
    if ctx is not None:
        raise RerunException(ctx)

# ════════════════════════════════════════════════
# ☁️ Dataset Helpers
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
        st.warning(f"Could not load datasets from Supabase: {e}")
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
        res = supabase.table("datasets").delete().eq("name", name).execute()
        if res.data:
            st.success(f"🗑️ Deleted '{name}' from cloud.")
        else:
            st.warning(f"⚠️ No dataset named '{name}' found or delete blocked by RLS.")
    except Exception as e:
        st.error(f"❌ Delete failed: {e}")

# ════════════════════════════════════════════════
# 🌐 Global Name Storage (Supabase)
# ════════════════════════════════════════════════
def load_global_names():
    try:
        res = supabase.table("global_names").select("*").execute()
        if res.data and len(res.data) > 0:
            return {r["number"]: r["name"] for r in res.data}

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
        for k, v in default_map.items():
            supabase.table("global_names").upsert({"number": k, "name": v}).execute()
        return default_map
    except Exception as e:
        st.error(f"Failed to load global names from Supabase: {e}")
        return {}

def save_global_name(number, name):
    try:
        supabase.table("global_names").upsert({"number": number, "name": name}).execute()
        return True
    except Exception as e:
        st.error(f"Save failed: {e}")
        return False

def delete_global_name(number):
    try:
        supabase.table("global_names").delete().eq("number", number).execute()
        return True
    except Exception as e:
        st.error(f"Delete failed: {e}")
        return False

def get_global_name(num):
    for k, v in GLOBAL_NAME_MAP.items():
        try:
            if abs(float(k) - float(num)) < 1e-5:
                return v
        except:
            continue
    return None

GLOBAL_NAME_MAP = load_global_names()

# ════════════════════════════════════════════════
# 🧮 APP UI
# ════════════════════════════════════════════════
st.title("🧬🔍 MassMatchFinder — NewProjects")

target = st.number_input("🎯 Target mass", format="%.5f")
tolerance = st.number_input("🎯 Tolerance ±", value=0.1, format="%.5f")

data_config = load_datasets()

# ────────────── Manage Global Names ──────────────
with st.expander("🧩 Manage Global Modifier Names", expanded=False):
    if GLOBAL_NAME_MAP:
        st.table(pd.DataFrame(
            [{"Number": k, "Name": v} for k, v in sorted(GLOBAL_NAME_MAP.items(), key=lambda x: float(x[0]))]
        ))
    num_val = st.text_input("Number (e.g. -1.007)")
    name_val = st.text_input("Description (e.g. Hydrogen loss)")
    if st.button("💾 Save Name"):
        if num_val and name_val:
            if save_global_name(num_val.strip(), name_val.strip()):
                st.success(f"Saved {num_val} → {name_val}")
                rerun()
    del_key = st.selectbox("🗑️ Delete a name", ["-- Select --"] + list(GLOBAL_NAME_MAP.keys()))
    if st.button("Delete Selected"):
        if del_key != "-- Select --":
            if delete_global_name(del_key):
                st.success(f"Deleted {del_key}")
                rerun()

# ────────────── Add Dataset ──────────────
# ────────────── Add New Dataset (Collapsible) ──────────────
with st.expander("➕ Add New Dataset", expanded=False):
    st.markdown("You can **add a dataset manually** or **upload from a 2-column CSV file** (Column A = main list, Column B = modifiers).")

    # --- Option 1: Manual Entry ---



