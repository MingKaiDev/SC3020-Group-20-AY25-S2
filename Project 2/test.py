# Use dummy data to write test assertions before real data is ready
from dummy_data import get_dummy_qep, get_dummy_aqps
from annotation import generate_annotations

result = generate_annotations(get_dummy_qep(), get_dummy_aqps())
assert "Hash Join" in result["full_text"]
assert "Sequential Scan" in result["full_text"] or "Seq Scan" in result["full_text"]
assert len(result["scans"]) > 0
assert len(result["joins"]) > 0
print("All tests passed")
