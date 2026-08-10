import pytest
from fastapi.testclient import TestClient

from app.core.store import get_store
from app.main import create_app

SUPPORT_CSV = (
    "Employee ID,Name,Period,Tickets Resolved,Avg Response Time,CSAT,"
    "Reopened Tickets,Attendance Rate,Deadlines Met\n"
    "E1,Alice,2026-07,120,15,0.92,2,0.99,0.96\n"
    "E2,Bob,2026-07,60,30,0.70,9,0.90,0.80\n"
)


@pytest.fixture
def client() -> TestClient:
    get_store().clear()
    return TestClient(create_app())


def upload(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/uploads",
        files={"file": ("perf.csv", SUPPORT_CSV.encode(), "text/csv")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_health(client: TestClient):
    body = client.get("/api/v1/health").json()
    assert body["status"] == "ok"
    assert "ai_enabled" in body


def test_profiles_expose_expected_columns(client: TestClient):
    body = client.get("/api/v1/profiles").json()
    keys = {p["key"] for p in body}
    assert keys == {"support", "developer"}
    support = next(p for p in body if p["key"] == "support")
    assert any("csat" in m["accepted_columns"] for m in support["metrics"])


def test_upload_returns_scored_employees(client: TestClient):
    body = upload(client)

    assert body["profile"] == "support"
    assert body["profile_detected"] is True
    assert body["row_count"] == 2
    assert body["scored_count"] == 2

    alice = body["employees"][0]
    assert alice["employee_id"] == "E1"
    assert alice["families"]["productivity"]["score"] == 100.0
    assert alice["families"]["compliance"]["score"] is not None
    assert 0 <= alice["overall_score"] <= 100
    # Every component reports the column it came from.
    tickets = next(
        c
        for c in alice["families"]["productivity"]["components"]
        if c["metric"] == "tickets_resolved"
    )
    assert tickets["source_field"] == "Tickets Resolved"
    # Alice hits every target; Bob misses them.
    assert body["employees"][0]["overall_score"] > body["employees"][1]["overall_score"]


def test_upload_reports_mapping_provenance(client: TestClient):
    body = upload(client)

    # Every column was recognized by the alias tables, so the agent was never consulted
    # even though the request defaulted to hybrid mode.
    assert body["mapping_mode"] == "aliases"
    assert body["unmapped_columns"] == []
    assert all(m["source"] == "alias" for m in body["resolved_mappings"])

    by_field = {m["field"]: m["column"] for m in body["resolved_mappings"]}
    assert by_field["employee_id"] == "Employee ID"
    assert by_field["tickets_resolved"] == "Tickets Resolved"


def test_upload_uses_the_agent_for_unrecognized_columns(client: TestClient, monkeypatch):
    from tests.test_mapping_agent import GOOD_PROPOSAL, NOVEL_CSV, scripted_model

    from app.services import mapping_agent as agent_module

    monkeypatch.setattr(
        agent_module, "_build_model", lambda: scripted_model(GOOD_PROPOSAL)
    )

    response = client.post(
        "/api/v1/uploads",
        files={"file": ("novel.csv", NOVEL_CSV.encode(), "text/csv")},
        data={"mapping_mode": "hybrid"},
    )
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["mapping_mode"] == "hybrid"
    assert body["scored_count"] == 2
    ai_mapped = {m["field"]: m for m in body["resolved_mappings"] if m["source"] == "ai"}
    assert ai_mapped["tickets_resolved"]["column"] == "Cases Wrapped Up"
    assert ai_mapped["tickets_resolved"]["confidence"] == 0.9
    assert ai_mapped["tickets_resolved"]["reasoning"]
    assert body["employees"][0]["families"]["productivity"]["score"] is not None


def test_upload_rejects_unmappable_file_in_aliases_mode(client: TestClient):
    from tests.test_mapping_agent import NOVEL_CSV

    response = client.post(
        "/api/v1/uploads",
        files={"file": ("novel.csv", NOVEL_CSV.encode(), "text/csv")},
        data={"mapping_mode": "aliases"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "schema_validation_error"


def test_upload_rejects_unsupported_type(client: TestClient):
    response = client.post(
        "/api/v1/uploads", files={"file": ("notes.txt", b"hello", "text/plain")}
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_batches_can_be_listed_and_fetched(client: TestClient):
    batch_id = upload(client)["batch_id"]

    listing = client.get("/api/v1/batches").json()
    assert [b["batch_id"] for b in listing] == [batch_id]

    detail = client.get(f"/api/v1/batches/{batch_id}").json()
    assert len(detail["employees"]) == 2


def test_unknown_batch_returns_404(client: TestClient):
    response = client.get("/api/v1/batches/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "batch_not_found"


def test_report_uses_fallback_without_api_key(client: TestClient, monkeypatch):
    from app.core import openai_client

    monkeypatch.setattr(openai_client, "get_openai_client", lambda: None)
    batch_id = upload(client)["batch_id"]

    response = client.post(
        "/api/v1/reports", json={"batch_id": batch_id, "employee_id": "E2"}
    )
    assert response.status_code == 200
    body = response.json()

    assert body["generated_by"] == "fallback"
    assert "## Summary" in body["narrative"]
    # The scores travel with the narrative, unchanged by the AI layer.
    assert body["kpi"]["employee_id"] == "E2"


def test_report_for_unknown_employee_returns_404(client: TestClient):
    batch_id = upload(client)["batch_id"]
    response = client.post(
        "/api/v1/reports", json={"batch_id": batch_id, "employee_id": "NOPE"}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "employee_not_found"
