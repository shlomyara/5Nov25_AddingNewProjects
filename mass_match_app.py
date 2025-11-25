import streamlit as st
import itertools, json, pandas as pd
from supabase import create_client, Client
from streamlit.runtime.scriptrunner import RerunException, get_script_run_ctx
import re  # for extracting numbers from description strings

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
    """
    Global name logic (using app 'tolerance'):
    - Signed entries in table:
        '+x' -> match only positive shifts near +x
        '-x' -> match only negative shifts near -x
    - Unsigned entries 'x':
        match both +x and -x by magnitude within ±tolerance:
            +x -> '+name'
            -x -> '-name'
    - Returns *all* matching names as a list (may be multiple).
    """
    try:
        num_f = float(num)
    except:
        return []

    # Use the same tolerance as the main mass matching.
    try:
        tol_val = float(tolerance)
    except Exception:
        tol_val = 1e-5

    matches = []

    for k, v in GLOBAL_NAME_MAP.items():
        k_str = str(k).strip()
        try:
            k_val = float(k_str)
        except:
            continue

        # Signed entries: explicit + or -
        if k_str.startswith(('+', '-')):
            # Require the signed value to match within tol_val
            if abs(k_val - num_f) <= tol_val:
                matches.append(v)

        # Unsigned entries: can match both +x and -x by magnitude
        else:
            if abs(abs(k_val) - abs(num_f)) <= tol_val:
                if num_f < 0:
                    matches.append("-" + v)
                else:
                    matches.append("+" + v)

    # Remove duplicates while preserving order
    seen = set()
    unique_matches = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            unique_matches.append(m)

    return unique_matches

GLOBAL_NAME_MAP = load_global_names()

# ════════════════════════════════════════════════
# 🧮 APP UI
# ════════════════════════════════════════════════
st.title("🧬🔍 MassMatchFinder — NewProjects")

# --- New: choose input type: direct mass or m/z + charge ---
input_mode = st.radio(
    "Input type",
    ["Mass", "m/z"],
    index=0,
    horizontal=True,
)

target_mass_direct = None
mz_value = None
selected_charges = []

if input_mode == "Mass":
    target_mass_direct = st.number_input("🎯 Target mass", format="%.5f", key="target_mass")
else:
    mz_value = st.number_input("📡 m/z", format="%.5f", key="mz_value")
    st.markdown("**Charge states to use (1–5):**")
    charge_cols = st.columns(5)
    for i, z in enumerate(range(1, 6)):
        with charge_cols[i]:
            if st.checkbox(f"z={z}", value=(z == 1), key=f"charge_{z}"):
                selected_charges.append(z)

tolerance = st.number_input("🎯 Tolerance ±", value=0.1, format="%.5f")

data_config = load_datasets()

# ────────────── Manage Global Names ──────────────
with st.expander("🧩 Manage Global Modifier Names", expanded=False):
    # Current global modifiers table
    if GLOBAL_NAME_MAP:
        st.table(pd.DataFrame(
            [{"Number": k, "Name": v} for k, v in sorted(GLOBAL_NAME_MAP.items(), key=lambda x: float(x[0]))]
        ))

    # ────────────── Manual add / update ──────────────
    st.markdown("### ➕ Add / update a single modifier")
    num_val = st.text_input("Number (e.g. -1.007)")
    name_val = st.text_input("Description (e.g. Hydrogen loss)")
    if st.button("💾 Save Name"):
        if num_val and name_val:
            if save_global_name(num_val.strip(), name_val.strip()):
                st.success(f"Saved {num_val} → {name_val}")
                rerun()
        else:
            st.warning("Please fill both Number and Description.")

    # ────────────── Delete a modifier ──────────────
    del_key = st.selectbox("🗑️ Delete a name", ["-- Select --"] + list(GLOBAL_NAME_MAP.keys()))
    if st.button("Delete Selected"):
        if del_key != "-- Select --":
            if delete_global_name(del_key):
                st.success(f"Deleted {del_key}")
                rerun()

    # ────────────── NEW: Upload modifiers from CSV ──────────────
    st.divider()
    st.markdown("### 📂 Upload modifiers from CSV")
    st.markdown(
        "CSV format: **first column = Number**, **second column = Name**. "
        "Additional columns (if any) will be ignored."
    )

    mod_csv = st.file_uploader(
        "Upload CSV of global modifiers",
        type=["csv"],
        key="global_mod_csv"
    )

    if mod_csv is not None:
        try:
            gdf = pd.read_csv(mod_csv)

            if len(gdf.columns) < 2:
                st.error("❌ The CSV must have at least two columns (Number, Name).")
            else:
                col_num = gdf.columns[0]
                col_name = gdf.columns[1]

                st.success(f"✅ Loaded {len(gdf)} rows from `{mod_csv.name}`")
                st.write("**Preview (first 5 rows):**")
                st.dataframe(gdf[[col_num, col_name]].head())

                if st.button("💾 Save all modifiers from CSV"):
                    count = 0
                    for _, row in gdf.iterrows():
                        num_raw = row[col_num]
                        name_raw = row[col_name]

                        if pd.isna(num_raw) or pd.isna(name_raw):
                            continue

                        num_str = str(num_raw).strip()
                        name_str = str(name_raw).strip()

                        if not num_str or not name_str:
                            continue

                        if save_global_name(num_str, name_str):
                            count += 1

                    st.success(f"✅ Saved / updated {count} modifiers from CSV.")
                    rerun()
        except Exception as e:
            st.error(f"Failed to read CSV: {e}")

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
    run_list2_only = st.checkbox("Shorters-combos", False)

# ════════════════════════════════════════════════
# 🧠 Calculation Helpers
# ════════════════════════════════════════════════
def within_tolerance(value, target_mass):
    return abs(value - target_mass) <= tolerance

def add_result(desc, val, steps, results, target_mass, prefix=None):
    if within_tolerance(val, target_mass):
        err = abs(val - target_mass)
        full_desc = desc if not prefix else f"[{prefix}] {desc}"
        results.append((len(steps), err, full_desc, val, err))

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
    # Build list of target masses to search
    target_pairs = []  # list of (target_mass, prefix_str)

    if input_mode == "Mass":
        if target_mass_direct is None:
            st.warning("Please enter a target mass.")
        else:
            target_pairs.append((float(target_mass_direct), None))
    else:
        if mz_value is None:
            st.warning("Please enter an m/z value.")
        else:
            if not selected_charges:
                st.warning("Please select at least one charge state.")
            else:
                for z in selected_charges:
                    # Generalized rule: neutral mass ~ m/z * z - z
                    target_mass = float(mz_value) * z - z
                    prefix = f"m/z={mz_value:.5f}, z={z}"
                    target_pairs.append((target_mass, prefix))

    results = []
    total_main = sum(main_list)
    progress = st.progress(0)
    done = 0

    if target_pairs:
        for target_mass, prefix in target_pairs:
            # Main-only
            if run_main_only:
                add_result(f"{selected_name} only", total_main, [], results, target_mass, prefix)

            # + modifiers
            if run_additions:
                for r in range(1, 4):
                    for combo in itertools.combinations_with_replacement(list2_add, r):
                        add_result(f"+{combo}", total_main + sum(combo), combo, results, target_mass, prefix)
                        done += 1
                        if done % 200 == 0:
                            progress.progress(min(done / 5000, 1.0))

            # - modifiers
            if run_subtractions:
                for r in range(1, 4):
                    for combo in itertools.combinations(list2_sub, r):
                        add_result(f"-{combo}", total_main - sum(combo), combo, results, target_mass, prefix)
                        done += 1
                        if done % 200 == 0:
                            progress.progress(min(done / 5000, 1.0))

            # - and +
            if run_sub_add:
                for sub in list2_sub:
                    for add in list2_add:
                        if sub == add:
                            continue
                        add_result(
                            f"-({sub},) +({add},)",
                            total_main - sub + add,
                            [sub, add],
                            results,
                            target_mass,
                            prefix,
                        )
                        done += 1
                        if done % 200 == 0:
                            progress.progress(min(done / 5000, 1.0))

            # ────────────── NEW Shorters-combos (List2-only logic) ──────────────
            if run_list2_only:
                # ==========================================
                # Fragments of main_list with optional list2 mods
                # and one-time substitution by neighbour AA.
                # ==========================================
                n = len(main_list)

                # --- Precompute main masses as a set (for skipping overlaps) ---
                main_masses_set = {round(float(x), 6) for x in main_list}

                # --- Build signed modifiers from list2 ---
                signed_mods = []
                seen = set()

                # positive shifts from list2_add
                for v in list2_add:
                    v = float(v)
                    mag = round(abs(v), 6)
                    if mag in main_masses_set:
                        continue
                    key = ('+', mag)
                    if key not in seen:
                        seen.add(key)
                        signed_mods.append(v)  # +v

                # negative shifts from list2_sub
                for v in list2_sub:
                    v = float(v)
                    mag = round(abs(v), 6)
                    if mag in main_masses_set:
                        continue
                    key = ('-', mag)
                    if key not in seen:
                        seen.add(key)
                        signed_mods.append(-v)  # -v

                # --- Prefix sums to get fragment masses quickly ---
                prefix_sums = [0.0]
                for x in main_list:
                    prefix_sums.append(prefix_sums[-1] + float(x))

                # Loop over all contiguous fragments i..j
                for start in range(n):
                    for end in range(start + 1, n + 1):
                        frag_sum = prefix_sums[end] - prefix_sums[start]
                        frag_label = f"{start + 1}-{end}"

                        # 0) fragment only
                        add_result(f"frag {frag_label}", frag_sum, [], results, target_mass, prefix)
                        done += 1
                        if done % 200 == 0:
                            progress.progress(min(done / 5000, 1.0))

                        # 1) fragment + list2 (no substitution)
                        if signed_mods:
                            # one modification
                            for m in signed_mods:
                                val = frag_sum + m
                                desc = f"frag {frag_label} {m:+.5f}"
                                add_result(desc, val, [m], results, target_mass, prefix)
                                done += 1
                                if done % 200 == 0:
                                    progress.progress(min(done / 5000, 1.0))

                            # two modifications
                            for i_m, m1 in enumerate(signed_mods):
                                for m2 in signed_mods[i_m:]:
                                    total_mod = m1 + m2
                                    val = frag_sum + total_mod
                                    desc = f"frag {frag_label} {m1:+.5f} {m2:+.5f}"
                                    add_result(desc, val, [m1, m2], results, target_mass, prefix)
                                    done += 1
                                    if done % 200 == 0:
                                        progress.progress(min(done / 5000, 1.0))

                        # 2) single substitution inside fragment
                        for k in range(start, end):
                            old_mass = float(main_list[k])
                            pos_in_frag = k - start + 1

                            neighbour_indices = []
                            if k - 1 >= 0:
                                neighbour_indices.append(k - 1)
                            if k + 1 < n:
                                neighbour_indices.append(k + 1)

                            for neigh_idx in neighbour_indices:
                                subst_mass = float(main_list[neigh_idx])

                                if abs(subst_mass - old_mass) < 1e-9:
                                    continue

                                sub_base = frag_sum - old_mass + subst_mass
                                base_desc = (
                                    f"frag {frag_label} subst pos{pos_in_frag} "
                                    f"{old_mass:.5f}->{subst_mass:.5f}"
                                )

                                # substitution ONLY
                                add_result(base_desc, sub_base, [sub_base - frag_sum], results, target_mass, prefix)
                                done += 1
                                if done % 200 == 0:
                                    progress.progress(min(done / 5000, 1.0))

                                if not signed_mods:
                                    continue

                                # substitution + one mod
                                for m in signed_mods:
                                    val = sub_base + m
                                    desc = f"{base_desc} {m:+.5f}"
                                    add_result(desc, val, [sub_base - frag_sum, m], results, target_mass, prefix)
                                    done += 1
                                    if done % 200 == 0:
                                        progress.progress(min(done / 5000, 1.0))

                                # substitution + two mods
                                for i_m, m1 in enumerate(signed_mods):
                                    for m2 in signed_mods[i_m:]:
                                        total_mod = m1 + m2
                                        val = sub_base + total_mod
                                        desc = f"{base_desc} {m1:+.5f} {m2:+.5f}"
                                        add_result(
                                            desc,
                                            val,
                                            [sub_base - frag_sum, m1, m2],
                                            results,
                                            target_mass,
                                            prefix,
                                        )
                                        done += 1
                                        if done % 200 == 0:
                                            progress.progress(min(done / 5000, 1.0))

    progress.progress(1.0)

    if results:
        st.success(f"✅ Found {len(results)} matches within ±{tolerance:.5f}")
        for _, _, desc, val, err in sorted(results, key=lambda x: (x[0], x[1])):
            st.write(f"🔹 `{desc}` = **{val:.5f}** (error: {err:.5f})")

            # Extract numeric tokens with correct sign, including cases like "-(15.977,)"
            raw = str(desc)
            nums = []
            for m in re.finditer(r'\d*\.?\d+', raw):
                x_str = m.group()
                v = float(x_str)

                # Default sign is +, but inspect characters before the number
                sign = 1.0
                j = m.start() - 1

                # Skip whitespace going backwards
                while j >= 0 and raw[j].isspace():
                    j -= 1

                if j >= 0 and raw[j] in '()':
                    # If directly before the number is '(' or ')',
                    # look one more step back for a sign, like "-(" or "+("
                    k = j - 1
                    while k >= 0 and raw[k].isspace():
                        k -= 1
                    if k >= 0 and raw[k] == '-':
                        sign = -1.0
                    elif k >= 0 and raw[k] == '+':
                        sign = 1.0
                else:
                    # Otherwise, the sign may be directly before the number
                    if j >= 0 and raw[j] == '-':
                        sign = -1.0
                    elif j >= 0 and raw[j] == '+':
                        sign = 1.0

                nums.append(sign * v)

            # Show ALL matching names for each numeric value
            for n in nums:
                name_list = get_global_name(n)
                for nm in name_list:
                    st.caption(f"↳ {n} → {nm}")
    else:
        st.warning("No matches found.")





