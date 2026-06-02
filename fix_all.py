import os
import json
from pathlib import Path
import re

# Paths
base_dir = Path("sentio_engine")
engine_py = base_dir / "sentio_engine/core/engine.py"
main_py = base_dir / "sentio_engine/api/main.py"
proxy_py = base_dir / "sentio_engine/api/proxy.py"
manager_py = base_dir / "sentio_engine/personas/manager.py"
db_py = base_dir / "sentio_engine/data/database.py"
belief_json = base_dir / "config/BeliefSystem.json"
drives_json = base_dir / "config/drives.json"
pyproject = base_dir / "pyproject.toml"
integration_test = base_dir / "tests/integration_test.py"
test_engine = base_dir / "tests/core/test_engine.py"
test_endpoints = base_dir / "tests/api/test_endpoints.py"

# 1. Fix engine.py
if engine_py.exists():
    with open(engine_py, "r") as f:
        content = f.read()

    # Mutability fix
    content = content.replace(
        "self._synchronize_decay(state, last_update_time)\n\n        report = Report()\n        report.emotional_state.CopyFrom(state)",
        "report = Report()\n        report.emotional_state.CopyFrom(state)\n        self._synchronize_decay(report.emotional_state, last_update_time)"
    )
    # Remove global logging
    content = content.replace("logging.basicConfig(level=logging.INFO)", "")

    # fix datetime
    content = content.replace("datetime.datetime.utcnow()", "datetime.datetime.now(datetime.timezone.utc)")
    if "import datetime" in content and "timezone" not in content:
        content = content.replace("import datetime", "import datetime\nfrom datetime import timezone")

    with open(engine_py, "w") as f:
        f.write(content)

# 2. Fix main.py
if main_py.exists():
    with open(main_py, "r") as f:
        content = f.read()

    # Fix x_session_id header
    content = content.replace(
        "x_session_id: Annotated[str, Header()],",
        "x_session_id: Annotated[str, Header(alias=\"x-session-id\")] = None,"
    )
    content = re.sub(
        r"async def _check_and_update_complex_states\(api_key: str, session_id: str\):",
        "async def _check_and_update_complex_states(api_key: str, session_id: str, engine_instance):",
        content
    )
    content = content.replace(
        "report = engine.get_report(state, datetime.utcnow())",
        "report = engine_instance.get_report(state, datetime.utcnow())"
    )
    content = content.replace(
        "active_complex_states = await _check_and_update_complex_states(api_key, x_session_id)",
        "active_complex_states = await _check_and_update_complex_states(api_key, x_session_id, engine)"
    )
    # fix datetime
    content = content.replace("datetime.utcnow()", "datetime.now(timezone.utc)")

    with open(main_py, "w") as f:
        f.write(content)

# 3. Fix proxy.py
if proxy_py.exists():
    with open(proxy_py, "r") as f:
        content = f.read()

    content = content.replace(
        "engine = SentioEngine(CONFIG_DIR)",
        "from sentio_engine.api.main import engine"
    )
    # fix datetime
    content = content.replace("datetime.utcnow()", "datetime.now(timezone.utc)")

    with open(proxy_py, "w") as f:
        f.write(content)

# 4. Fix manager.py
if manager_py.exists():
    with open(manager_py, "r") as f:
        content = f.read()

    content = content.replace(
        "def build_system_prompt(self, emotional_state: dict) -> str:",
        "def build_system_prompt(self, emotional_state: dict) -> tuple[str, str]:"
    )
    with open(manager_py, "w") as f:
        f.write(content)

# 5. Fix configs
if belief_json.exists():
    with open(belief_json, "r") as f:
        data = json.load(f)
    if "personality" in data:
        data["personality"]["extraversion"]["value"] = 0.8
        data["personality"]["neuroticism"]["value"] = 0.7
        data["personality"]["agreeableness"]["value"] = 0.6
        data["personality"]["conscientiousness"]["value"] = 0.7
        data["personality"]["openness"]["value"] = 0.3
    with open(belief_json, "w") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

if drives_json.exists():
    with open(drives_json, "r") as f:
        data = json.load(f)
    if "Curiosity" in data:
        data["Curiosity"]["target_emotions"] = {"удивление": 0.8, "радость": 0.5}
    if "Socialization" in data:
        data["Socialization"]["target_emotions"] = {"доверие": 0.9, "радость": 0.7}
    with open(drives_json, "w") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# 6. Delete database.py
if db_py.exists():
    os.remove(db_py)

# 7. Fix tests for datetime
for test_file in [test_engine, test_endpoints, integration_test]:
    if test_file.exists():
        with open(test_file, "r") as f:
            content = f.read()
        content = content.replace("datetime.datetime.utcnow()", "datetime.datetime.now(datetime.timezone.utc)")
        content = content.replace("datetime.utcnow()", "datetime.now(timezone.utc)")
        with open(test_file, "w") as f:
            f.write(content)

# 8. Fix pyproject dependencies
if pyproject.exists():
    with open(pyproject, "r") as f:
        content = f.read()
    if "motor = " not in content:
        content = content.replace(
            "[tool.poetry.dependencies]\npython = \"^3.10\"\nfastapi = \"^0.110.0\"\n",
            "[tool.poetry.dependencies]\npython = \"^3.10\"\nfastapi = \"^0.110.0\"\nmotor = \"^3.3.2\"\npymongo = \"^4.6.1\"\nhttpx = \"^0.26.0\"\n"
        )
    with open(pyproject, "w") as f:
        f.write(content)

# 9. Create dataset lesson
dataset_dir = Path(".dataset/lessons")
dataset_dir.mkdir(parents=True, exist_ok=True)
lesson_file = dataset_dir / "prefer_dict_get_over_bracket_access_for_optional_keys.json"
lesson_data = {
    "name": "prefer_dict_get_over_bracket_access_for_optional_keys",
    "description": "When accessing optional keys in a dictionary, use .get() instead of bracket access to avoid KeyError."
}
with open(lesson_file, "w") as f:
    json.dump(lesson_data, f, indent=2)

print("Fixes applied successfully.")
