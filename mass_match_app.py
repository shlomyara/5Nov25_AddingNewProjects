
import streamlit as st
import itertools

# --- Title ---
st.title("🧮 Mass Match Finder")
st.markdown("Enter a target mass and tolerance to find matching combinations.")

# --- Input ---
target = st.number_input("🎯 Target number to match", format="%.5f")
tolerance = st.number_input("🎯 Acceptable error/tolerance (e.g., 0.1)", value=0.1, format="%.5f")

# --- Data ---
cyclic = [
    173.051, 197.084, 127.063, 147.055, 87.055,
    200.095, 170.113, 207.113, 114.042, 114.042,
    101.047, 129.042, 130.032
]

linear = [
    174.058, 197.084, 127.063, 147.055, 87.055,
    200.095, 170.113, 207.113, 114.042, 114.042,
    101.047, 129.042, 131.040
]

list2_raw = [
    174.058, 173.051, 197.084, 127.063, 147.055,
    87.055, 200.095, 170.113, 207.113, 114.042,
    101.047, 129.042, 130.032, 131.040, 42.010,
    0.984, 2.015, '+71.037', '+242.109', '+56.06', '-15.977', '+252.082',
    '+230.11', '-18.010', '-14.015', '-17.026',
    '+100.05', '+222.06', '-33.987', '-1.007', '+1896.83'
]

list2_add = []
list2_sub = []

for item in list2_raw:
    if isinstance(item, str):
        if item.startswith('+'):
            list2_add.append(float(item[1:]))
        elif item.startswith('-'):
            list2_sub.append(float(item[1:]))
    else:
        list2_add.append(item)
        list2_sub.append(item)

results = []
# Custom names for specific result descriptions
custom_names = {
    "Linear + (1896.83,)": "Linear_Dimer",
    "Cyclic + (1896.83,)": "Cyclic_Dimer",
    "Cyclic + (0.984,)": "Cyclic_Deamination",
    "Linear + (56.06,)": "Linear + tBu"
}

def within_tolerance(value):
    return abs(value - target) <= tolerance

def add_result(description, value, steps):
    if within_tolerance(value):
        error = abs(value - target)
        description = description.replace("List1", "Cyclic").replace("List3", "Linear")
        
        # If a custom name exists, append it to the description
        if description in custom_names:
            description += f" = {custom_names[description]}"
        
        results.append((len(steps), error, description, value, error))

sum_cyclic = sum(cyclic)
sum_linear = sum(linear)

add_result("Cyclic only", sum_cyclic, [])
add_result("Linear only", sum_linear, [])

for base_label, base_sum in [("List1", sum_cyclic), ("List3", sum_linear)]:
    for r in range(1, 4):
        for combo in itertools.combinations_with_replacement(list2_add, r):
            value = base_sum + sum(combo)
            add_result(f"{base_label} + {combo}", value, combo)

for base_label, base_sum in [("List1", sum_cyclic), ("List3", sum_linear)]:
    for r in range(1, 4):
        for combo in itertools.combinations(list2_sub, r):
            value = base_sum - sum(combo)
            add_result(f"{base_label} - {combo}", value, combo)

for base_label, base_sum in [("List1", sum_cyclic), ("List3", sum_linear)]:
    for sub in list2_sub:
        for add in list2_add:
            if sub == add:
                continue
            value = base_sum - sub + add
            add_result(f"{base_label} - ({sub},) + ({add},)", value, [sub, add])

all_list2 = list2_add + [-v for v in list2_sub]
for r in range(2, 6):
    for combo in itertools.combinations_with_replacement(all_list2, r):
        value = sum(combo)
        add_result(f"List2 only {combo}", value, combo)

if results:
    st.success(f"Found {len(results)} matching combinations within ±{tolerance:.5f}")
    for _, _, desc, val, error in sorted(results, key=lambda x: (x[0], x[1])):
        st.write(f"🔹 `{desc}` = **{val:.5f}** (error: {error:.5f})")
else:
    st.warning(f"No matches found within ±{tolerance:.5f}")
