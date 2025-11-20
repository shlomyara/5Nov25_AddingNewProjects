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
        st.table(pd.DataFrame([{"Number": k, "Name": v} for k, v in sorted(GLOBAL_NAME_MAP.items(), key=lambda x: float(x[0]))]))
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
    name = st.text_input("Dataset name")
    main_text = st.text_area("Main list values (comma or newline separated)")
    list2_text = st.text_area("List2 modifiers (optional, use + or - signs)")

    # --- Option 2: CSV Upload ---
    st.divider()
    st.markdown("### 📂 Or upload a 2-column CSV file")
    uploaded_file = st.file_uploader("Upload CSV (2 columns only)", type=["csv"])

    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            if len(df.columns) < 2:
                st.error("❌ The CSV must have at least two columns (A and B).")
            else:
                colA = df.columns[0]
                colB = df.columns[1]
                list_A = df[colA].dropna().astype(str).tolist()
                list_B = df[colB].dropna().astype(str).tolist()

                st.success(f"✅ Loaded {len(list_A)} main values and {len(list_B)} modifiers from `{uploaded_file.name}`")
                st.write("**Preview:**")
                st.dataframe(df.head())

                # Optional: Fill inputs automatically
                if not main_text and not list2_text:
                    main_text = ", ".join(list_A)
                    list2_text = ", ".join(list_B)

                # Display combined summary
                st.markdown(f"**Main list (A):** {', '.join(list_A[:10])} ...")
                st.markdown(f"**List2 (B):** {', '.join(list_B[:10])} ...")
        except Exception as e:
            st.error(f"Failed to read CSV: {e}")

    # --- Save Dataset Button ---
    st.divider()
    if st.button("💾 Save Dataset"):
        try:
            main_list = [float(x.strip()) for x in main_text.replace("\n", ",").split(",") if x.strip()]
            list2_list = [x.strip() for x in list2_text.replace("\n", ",").split(",") if x.strip()] or main_list

            if name:
                if save_dataset(name, main_list, list2_list):
                    st.success(f"✅ Dataset '{name}' saved to cloud.")
                    rerun()
            else:
                st.warning("Please enter a dataset name.")
        except Exception as e:
            st.error(f"Error saving dataset: {e}")


# ────────────── Select Dataset ──────────────
if not data_config:
    st.info("No datasets found.")
    st.stop()

st.divider()
selected_name = st.selectbox("Select dataset to use:", list(data_config.keys()))
selected_data = data_config[selected_name]
main_list = selected_data["main"]
list2_raw = selected_data["list2_raw"]
st.markdown(f"**Using dataset:** `{selected_name}`  ({len(main_list)} main, {len(list2_raw)} modifiers)")

# ────────────── Manage Datasets ──────────────
with st.expander("🛠 Manage Datasets", expanded=False):
    manage_name = st.selectbox("Choose dataset to manage:", list(data_config.keys()), key="manage")
    col1, col2 = st.columns(2)
    with col1:
        new_name = st.text_input(f"Rename '{manage_name}' to:", "")
        if st.button("Rename"):
            if new_name:
                rename_dataset(manage_name, new_name)
                st.success(f"Renamed '{manage_name}' → '{new_name}'")
                rerun()
    with col2:
        confirm = st.checkbox(f"Confirm delete '{manage_name}'", key="confirm")
        if st.button("Delete"):
            if confirm:
                delete_dataset(manage_name)
                rerun()

# ────────────── Combination Settings ──────────────
with st.expander("⚙️ Combination Settings", expanded=False):
    run_main_only = st.checkbox(f"{selected_name} only", True)
    run_additions = st.checkbox("Include + modifiers", True)
    run_subtractions = st.checkbox("Include - modifiers", True)
    run_sub_add = st.checkbox("Include - and + combined", True)
    run_list2_only = st.checkbox("List2-only combos", False)

# ════════════════════════════════════════════════
# 🧠 Calculation Helpers
# ════════════════════════════════════════════════
def within_tolerance(value): 
    return abs(value - target) <= tolerance

def add_result(desc, val, steps, results):
    if within_tolerance(val):
        err = abs(val - target)
        results.append((len(steps), err, desc, val, err))

# --- Parse modifiers (handles extra quotes & exact Code 1 behaviour) ---
list2_add, list2_sub = [], []

for item in list2_raw:
    # Normalize weird Supabase cases like "'+56.06'"
    s = str(item).strip().strip("'").strip('"')
    try:
        if s.startswith('+'):
            list2_add.append(float(s[1:]))
        elif s.startswith('-'):
            list2_sub.append(abs(float(s)))
        else:
            val = float(s)
            if val >= 0:
                list2_add.append(val)
                list2_sub.append(val)
            else:
                list2_sub.append(abs(val))
    except ValueError:
        pass

# ════════════════════════════════════════════════
# ▶️ Run Match Search
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
                if sub == add:
                    continue
                add_result(f"-({sub},) +({add},)", total_main - sub + add, [sub, add], results)
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
            nums = [float(x) for x in str(desc).replace("(", "").replace(")", "").replace("+", "").replace("-", "").split(",") if x.strip().replace('.', '', 1).isdigit()]
            for n in nums:
                nm = get_global_name(n)
                if nm:
                    st.caption(f"↳ {n} → {nm}")
    else:
        st.warning("No matches found.")


