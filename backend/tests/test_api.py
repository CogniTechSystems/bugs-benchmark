from fastapi.testclient import TestClient

from app.context import AppContext
from app.models import DownloadStatus, LanguageModel


def test_bug_hunt_catalogue_is_listed_by_difficulty(client: TestClient):
    hunts = client.get("/api/bug-hunts").json()
    assert [hunt["difficulty"] for hunt in hunts] == sorted(
        (hunt["difficulty"] for hunt in hunts), key=["easy", "medium", "hard"].index
    )
    assert {"inventory-ledger", "bank-ledger"} <= {hunt["slug"] for hunt in hunts}


def test_managed_runtime_requires_command_template(client: TestClient):
    response = client.post("/api/runtimes", json={"name": "llama.cpp", "kind": "managed"})
    assert response.status_code == 422


def test_external_runtime_requires_url(client: TestClient):
    response = client.post(
        "/api/runtimes", json={"name": "Ollama", "kind": "external", "base_url": "localhost"}
    )
    assert response.status_code == 422


def test_runtime_crud(client: TestClient):
    payload = {
        "name": "llama.cpp",
        "kind": "managed",
        "command_template": "llama-server -m {model_path} --port {port} --jinja",
    }
    created = client.post("/api/runtimes", json=payload)
    assert created.status_code == 201
    runtime_id = created.json()["id"]

    assert client.post("/api/runtimes", json=payload).status_code == 409

    updated = client.put(
        f"/api/runtimes/{runtime_id}", json={**payload, "description": "CPU and GPU inference"}
    )
    assert updated.json()["description"] == "CPU and GPU inference"
    assert client.delete(f"/api/runtimes/{runtime_id}").status_code == 204
    assert client.get("/api/runtimes").json() == []


def test_deployment_validates_model_file(client: TestClient, context: AppContext, tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "weights.gguf").write_bytes(b"gguf")
    with context.session_factory() as db:
        model = LanguageModel(
            repo_id="example/model", local_path=str(model_dir), status=DownloadStatus.READY
        )
        db.add(model)
        db.commit()
        model_id = model.id
    runtime_id = client.post(
        "/api/runtimes",
        json={"name": "llama.cpp", "kind": "managed", "command_template": "llama-server"},
    ).json()["id"]

    base = {"name": "Local", "model_id": model_id, "runtime_id": runtime_id}
    missing = client.post("/api/deployments", json={**base, "model_file": "absent.gguf"})
    assert missing.status_code == 422

    created = client.post("/api/deployments", json={**base, "model_file": "weights.gguf"})
    assert created.status_code == 201
    assert created.json()["status"] == "stopped"
    assert created.json()["model_repo_id"] == "example/model"

    files = client.get(f"/api/models/{model_id}/files").json()
    assert files == [{"path": "weights.gguf", "size_bytes": 4}]

    assert client.delete(f"/api/runtimes/{runtime_id}").status_code == 409
    assert client.delete(f"/api/models/{model_id}").status_code == 409


def test_unknown_resources_return_not_found(client: TestClient):
    assert client.get("/api/jobs/999").status_code == 404
    assert client.get("/api/sessions/999").status_code == 404
    assert client.post("/api/deployments/999/start").status_code == 404


def test_model_can_be_registered_without_downloading(client: TestClient):
    response = client.post(
        "/api/models", json={"repo_id": "example/served-elsewhere", "register_only": True}
    )
    assert response.status_code == 202
    assert response.json()["status"] == "ready"
    assert response.json()["downloaded_bytes"] == 0


def test_invalid_repository_id_is_rejected(client: TestClient):
    assert client.post("/api/models", json={"repo_id": "not a repo"}).status_code == 422
