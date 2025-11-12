# ════════════════════════════════════════════════
# 🧠 Calculation Helpers  (fixed for parity with Code 1)
# ════════════════════════════════════════════════

def within_tolerance(value):
    return abs(value - target) <= tolerance


def add_result(desc, val, steps, results):
    if within_tolerance(val):
        err = abs(val - target)
        results.append((len(steps), err, desc, val, err))


# --- Parse modifiers exactly like Code 1 ---
list2_add, list2_sub = [], []
for item in list2_raw:
    if isinstance(item, str):
        if item.startswith('+'):
            list2_add.append(float(item[1:]))
        elif item.startswith('-'):
            list2_sub.append(float(item[1:]))
        else:
            # Only numeric strings are treated as values, not both by default
            try:
                val = float(item)
                list2_add.append(val)
                list2_sub.append(val)
            except ValueError:
                pass
    else:
        # numeric
        list2_add.append(float(item))
        list2_sub.append(float(item))


# ════════════════════════════════════════════════
# ▶️ Run Matching Search (fixed to match Code 1)
# ════════════════════════════════════════════════

st.divider()
if st.button("▶️ Run Matching Search"):
    results = []
    total_main = sum(main_list)

    progress = st.progress(0)
    done = 0

    # --- main only ---
    if run_main_only:
        add_result(f"{selected_name} only", total_main, [], results)
        done += 1
        progress.progress(min(done / 5000, 1.0))

    # --- additions ---
    if run_additions:
        for r in range(1, 4):
            for combo in itertools.combinations_with_replacement(list2_add, r):
                add_result(f"{selected_name} + {combo}", total_main + sum(combo), combo, results)
                done += 1
                if done % 50 == 0:
                    progress.progress(min(done / 5000, 1.0))

    # --- subtractions ---
    if run_subtractions:
        for r in range(1, 4):
            for combo in itertools.combinations(list2_sub, r):
                add_result(f"{selected_name} - {combo}", total_main - sum(combo), combo, results)
                done += 1
                if done % 50 == 0:
                    progress.progress(min(done / 5000, 1.0))

    # --- sub + add combinations ---
    if run_sub_add:
        for sub in list2_sub:
            for add in list2_add:
                if sub == add:  # prevent duplicates like Code 1
                    continue
                add_result(f"{selected_name} - ({sub},) + ({add},)", total_main - sub + add, [sub, add], results)
                done += 1
                if done % 50 == 0:
                    progress.progress(min(done / 5000, 1.0))

    # --- list2 only combinations ---
    if run_list2_only:
        combined = list2_add + [-v for v in list2_sub]
        for r in range(2, 6):
            for combo in itertools.combinations_with_replacement(combined, r):
                add_result(f"List2 only {combo}", sum(combo), combo, results)
                done += 1
                if done % 100 == 0:
                    progress.progress(min(done / 5000, 1.0))

    progress.progress(1.0)

    # --- results display ---
    if results:
        st.success(f"✅ Found {len(results)} matches within ±{tolerance:.5f}")
        for _, _, desc, val, err in sorted(results, key=lambda x: (x[0], x[1])):
            st.write(f"🔹 `{desc}` = **{val:.5f}** (error: {err:.5f})")

            # optional global name caption (non-affecting)
            nums = [float(x) for x in str(desc).replace("(", "").replace(")", "").replace("+", "").replace("-", "").split(",")
                    if x.strip().replace('.', '', 1).isdigit()]
            for n in nums:
                nm = get_global_name(n)
                if nm:
                    st.caption(f"↳ {n} → {nm}")
    else:
        st.warning("No matches found.")

