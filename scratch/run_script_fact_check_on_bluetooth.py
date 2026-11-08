from core.project_manager import Project
from core.fact_checker import verify_script_facts

p = Project("bluetooth_7_0_high_data_2")
print("Project loaded:", p.id)

report = verify_script_facts(p, auto_patch=True)
print("\n--- Script Fact Check Report ---")
print("Score:", report.get("validity_score"))
print("Verdict:", report.get("overall_verdict"))
print("Summary:", report.get("summary"))

print("\n--- Claims Verified ---")
for c in report.get("claims", []):
    print(f"[{c.get('verdict')}] {c.get('claim')}")
    if c.get("exact_target"):
        print(f"  Target: '{c.get('exact_target')}' -> '{c.get('correction')}'")
        print(f"  Explanation: {c.get('explanation')}")

# Check updated script text
scr = p.read_json("script/script.json")
print("\n--- Updated Hook ---")
print(scr["sections"][0]["text"])

print("\n--- Updated Introduction ---")
print(scr["sections"][1]["text"])
