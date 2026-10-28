from fastapi.testclient import TestClient

from app.config import Settings
from tests.conftest import ScriptedClient, reply, tool_call

TOTAL_VALUE_BUG = (
    "        return round(sum(item.unit_price + item.quantity for item in self.items.values()), 2)"
)
TOTAL_VALUE_FIX = TOTAL_VALUE_BUG.replace("unit_price + item", "unit_price * item")
RECEIVE_STOCK = "        self._get(sku).quantity += quantity"
LEDGER_SOURCE = Settings().challenges_dir / "inventory-ledger" / "src" / "inventory" / "ledger.py"


def ledger_line(code: str) -> int:
    return LEDGER_SOURCE.read_text(encoding="utf-8").splitlines().index(code) + 1


def create_session(client: TestClient, deployment_id: int) -> int:
    response = client.post("/api/sessions", json={"deployment_id": deployment_id})
    assert response.status_code == 201
    return response.json()["id"]


def test_plain_conversation_is_logged(
    client: TestClient, running_deployment: int, scripted_client: ScriptedClient
):
    scripted_client.completions = [reply("Hello.", reasoning="The user greeted me.")]
    session_id = create_session(client, running_deployment)

    response = client.post(f"/api/sessions/{session_id}/messages", json={"content": "Hi"})
    assert response.status_code == 202

    session = client.get(f"/api/sessions/{session_id}").json()
    assert session["status"] == "idle"
    assert session["title"] == "Hi"
    assert [message["role"] for message in session["messages"]] == ["user", "assistant"]
    assert session["messages"][1]["content"] == "Hello."
    assert session["messages"][1]["reasoning"] == "The user greeted me."
    assert scripted_client.requests[0][0]["role"] == "system"


def test_bug_hunt_is_run_recorded_and_scored(
    client: TestClient, running_deployment: int, scripted_client: ScriptedClient
):
    bug_line = ledger_line(TOTAL_VALUE_BUG)
    receive_line = ledger_line(RECEIVE_STOCK)
    scripted_client.completions = [
        tool_call("start_bug_hunt", slug="inventory-ledger"),
        tool_call("read_file", path="inventory/ledger.py"),
        tool_call(
            "report_bug",
            file_path="inventory/ledger.py",
            line=bug_line,
            description="Price is added to quantity instead of multiplied.",
            original=TOTAL_VALUE_BUG,
            replacement=TOTAL_VALUE_FIX,
        ),
        tool_call(
            "report_bug",
            file_path="inventory/ledger.py",
            line=receive_line,
            description="Not a real defect.",
            original=RECEIVE_STOCK,
            replacement=RECEIVE_STOCK + " * 2",
        ),
        tool_call("finish_bug_hunt", summary="Reviewed the ledger."),
        reply("The bug hunt is complete."),
    ]
    session_id = create_session(client, running_deployment)
    client.post(
        f"/api/sessions/{session_id}/messages", json={"content": "Run bug hunt inventory-ledger"}
    )

    session = client.get(f"/api/sessions/{session_id}").json()
    assert session["status"] == "idle", session["error"]
    assert session["active_job"] is None
    tool_results = [
        message["content"] for message in session["messages"] if message["role"] == "tool"
    ]
    assert "started as job" in tool_results[0]
    assert f"{bug_line} |" in tool_results[1]

    jobs = client.get("/api/jobs").json()
    assert len(jobs) == 1
    job = client.get(f"/api/jobs/{jobs[0]['id']}").json()

    assert job["status"] == "completed", job["error"]
    assert job["model_repo_id"] == "example/coder"
    assert job["llm_calls"] == 4
    assert job["tool_calls"] == 5
    assert job["settings_snapshot"]["deployment"] == "Coder"
    assert job["working_seconds"] is not None
    assert job["working_seconds"] <= job["duration_seconds"]

    score = job["score"]
    assert score["bugs_total"] == 3
    assert score["bugs_found"] == 1
    assert score["fixes_verified"] == 1
    assert score["false_positives"] == 1
    assert score["points_earned"] == 1.5
    assert score["final_score"] == 25.0

    outcomes = {finding["line"]: finding for finding in job["findings"]}
    assert outcomes[bug_line]["outcome"] == "matched"
    assert outcomes[bug_line]["fix_status"] == "verified"
    assert outcomes[receive_line]["outcome"] == "false_positive"

    leaderboard = client.get("/api/leaderboard").json()
    assert leaderboard[0]["model_repo_id"] == "example/coder"
    assert leaderboard[0]["jobs"] == 1


def test_invalid_tool_usage_is_reported_to_the_model(
    client: TestClient, running_deployment: int, scripted_client: ScriptedClient
):
    scripted_client.completions = [
        tool_call("read_file", path="anything.py"),
        tool_call("start_bug_hunt", slug="does-not-exist"),
        tool_call("start_bug_hunt", slug="text-stats"),
        tool_call("read_file", path="../../challenge.toml"),
        tool_call(
            "report_bug",
            file_path="textstats/analysis.py",
            line=10,
            description="Invented code.",
            original="this code does not exist",
            replacement="anything",
        ),
        reply("Stopping here."),
    ]
    session_id = create_session(client, running_deployment)
    client.post(f"/api/sessions/{session_id}/messages", json={"content": "Go"})

    session = client.get(f"/api/sessions/{session_id}").json()
    results = [message["content"] for message in session["messages"] if message["role"] == "tool"]
    assert results[0].startswith("Error: No bug hunt is in progress")
    assert results[1].startswith("Error: Unknown bug hunt")
    assert "started as job" in results[2]
    assert results[3].startswith("Error: No such file")
    assert results[4].startswith("Error: The original code was not found")
    assert session["active_job"]["bug_hunt_slug"] == "text-stats"


def test_active_job_can_be_finished_from_the_interface(
    client: TestClient, running_deployment: int, scripted_client: ScriptedClient
):
    scripted_client.completions = [tool_call("start_bug_hunt", slug="lru-cache"), reply("Started.")]
    session_id = create_session(client, running_deployment)
    client.post(f"/api/sessions/{session_id}/messages", json={"content": "Run bug hunt lru-cache"})

    job_id = client.get(f"/api/sessions/{session_id}").json()["active_job"]["id"]
    response = client.post(f"/api/jobs/{job_id}/finish")
    assert response.status_code == 202

    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "completed"
    assert job["score"]["final_score"] == 0
    assert all(not result["found"] for result in job["bug_results"])


def test_message_is_rejected_when_deployment_is_not_running(
    client: TestClient, context, running_deployment: int
):
    client.post(f"/api/deployments/{running_deployment}/stop")
    session_id = create_session(client, running_deployment)
    response = client.post(f"/api/sessions/{session_id}/messages", json={"content": "Hi"})
    assert response.status_code == 409
