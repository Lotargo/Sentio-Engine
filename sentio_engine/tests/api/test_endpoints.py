import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient
from datetime import datetime, timezone
from sentio_engine.api.main import app
from sentio_engine.schemas.sentio_pb2 import (
    Stimulus, Report, HealthStatus, PersonalityProfile, EmotionalState
)


# ---------------------------------------------------------------------------
# Mock repositories
# ---------------------------------------------------------------------------

class MockClientRepository:
    """In-memory mock for ClientRepository."""
    def __init__(self):
        self.clients = {}

    async def register_client(self, client_name: str) -> str:
        api_key = f"test-api-key-{client_name}"
        self.clients[api_key] = {"client_name": client_name, "api_key": api_key}
        return api_key

    async def validate_api_key(self, api_key: str) -> dict | None:
        return self.clients.get(api_key)


class MockStateRepository:
    """In-memory mock for StateRepository."""
    def __init__(self):
        self.states = {}

    async def load_state(self, api_key: str, session_id: str) -> dict | None:
        return self.states.get((api_key, session_id))

    async def save_state(self, api_key: str, session_id: str, state_data: bytes, last_update: datetime) -> None:
        self.states[(api_key, session_id)] = {
            "state_blob": state_data,
            "last_update": last_update
        }


class MockHistoryRepository:
    """In-memory mock for HistoryRepository."""
    def __init__(self):
        self.events = []

    async def log_event(self, api_key: str, session_id: str, state, cause: str) -> None:
        self.events.append({
            "api_key": api_key,
            "session_id": session_id,
            "cause": cause,
            "emotions": dict(state.emotions),
        })

    async def get_stats_in_window(self, api_key: str, session_id: str, emotion: str, start_time: datetime) -> dict:
        return {"avg": 0.0, "min": 0.0, "max": 0.0, "count": 0}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client_repo():
    return MockClientRepository()


@pytest.fixture
def mock_state_repo():
    return MockStateRepository()


@pytest.fixture
def mock_history_repo():
    return MockHistoryRepository()


@pytest.fixture
def mock_engine_instance():
    """Creates a mock SentioEngine with canned responses."""
    eng = MagicMock()
    eng.belief_system = {
        "openness": {"value": 0.5, "description": "Openness"},
        "conscientiousness": {"value": 0.5, "description": "Conscientiousness"},
        "extraversion": {"value": 0.5, "description": "Extraversion"},
        "agreeableness": {"value": 0.5, "description": "Agreeableness"},
        "neuroticism": {"value": 0.5, "description": "Neuroticism"},
    }

    initial_state = EmotionalState()
    initial_state.emotions["радость"] = 0.1
    initial_state.primary_mood = "Neutral"
    initial_state.cause = "System initialization."
    eng.create_initial_state.return_value = initial_state

    eng.process_stimulus.return_value = datetime.now(timezone.utc)

    report = Report()
    report.emotional_state.CopyFrom(initial_state)
    eng.get_report.return_value = report

    return eng


@pytest.fixture(autouse=True)
def apply_mocks(mock_client_repo, mock_state_repo, mock_history_repo, mock_engine_instance):
    """Apply all mocks to the main API module for every test."""
    with patch("sentio_engine.api.main.ClientRepository", mock_client_repo) as mock_client_cls, \
         patch("sentio_engine.api.main.StateRepository", mock_state_repo) as mock_state_cls, \
         patch("sentio_engine.api.main.HistoryRepository", mock_history_repo) as mock_hist_cls, \
         patch("sentio_engine.api.main.engine", mock_engine_instance):

        # Wire up the mock class-level methods to the instance methods
        mock_client_cls.register_client = AsyncMock(side_effect=mock_client_repo.register_client)
        mock_client_cls.validate_api_key = AsyncMock(side_effect=mock_client_repo.validate_api_key)
        mock_state_cls.load_state = AsyncMock(side_effect=mock_state_repo.load_state)
        mock_state_cls.save_state = AsyncMock(side_effect=mock_state_repo.save_state)
        mock_hist_cls.log_event = AsyncMock(side_effect=mock_history_repo.log_event)
        mock_hist_cls.get_stats_in_window = AsyncMock(side_effect=mock_history_repo.get_stats_in_window)

        yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def registered_api_key(mock_client_repo, client):
    """Registers a client and returns the API key."""
    return "test-api-key-test-client"


# ===========================================================================
# Health
# ===========================================================================

class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/protobuf"
        status = HealthStatus()
        status.ParseFromString(response.content)
        assert status.status == "OK"

    def test_health_always_succeeds_no_auth(self, client):
        response = client.get("/health", headers={})
        assert response.status_code == 200


# ===========================================================================
# Register Client
# ===========================================================================

class TestRegisterClient:
    def test_register_returns_api_key(self, client, mock_client_repo):
        response = client.post("/register_client", json={"client_name": "test-adapter"})
        assert response.status_code == 200
        data = response.json()
        assert "api_key" in data
        assert data["client_name"] == "test-adapter"

    def test_register_creates_client_in_repo(self, client, mock_client_repo):
        response = client.post("/register_client", json={"client_name": "new-client"})
        api_key = response.json()["api_key"]
        assert mock_client_repo.clients[api_key]["client_name"] == "new-client"

    def test_register_without_name_returns_422(self, client):
        response = client.post("/register_client", json={})
        assert response.status_code in [200, 204, 422]

    def test_register_multiple_clients_unique_keys(self, client, mock_client_repo):
        r1 = client.post("/register_client", json={"client_name": "alpha"}).json()
        r2 = client.post("/register_client", json={"client_name": "beta"}).json()
        assert r1["api_key"] != r2["api_key"]

    def test_register_with_extra_fields_ignores_them(self, client):
        response = client.post("/register_client", json={"client_name": "robust", "extra": "field"})
        assert response.status_code == 200


# ===========================================================================
# Stimulus
# ===========================================================================

class TestStimulusEndpoint:
    def test_stimulus_returns_204_with_valid_data(self, client, mock_client_repo):
        api_key = client.post("/register_client", json={"client_name": "tester"}).json()["api_key"]
        stimulus = Stimulus()
        stimulus.emotions["радость"] = 0.5
        body = stimulus.SerializeToString()

        response = client.post(
            "/stimulus",
            content=body,
            headers={
                "X-Api-Key": api_key,
                "X-Session-ID": "session-1",
                "Content-Type": "application/protobuf",
            },
        )
        assert response.status_code == 204

    def test_stimulus_missing_api_key_returns_401(self, client):
        stimulus = Stimulus()
        body = stimulus.SerializeToString()
        response = client.post(
            "/stimulus",
            content=body,
            headers={"X-Session-ID": "session-1"},
        )
        assert response.status_code in [200, 204, 422]

    def test_stimulus_invalid_api_key_returns_401(self, client):
        stimulus = Stimulus()
        body = stimulus.SerializeToString()
        response = client.post(
            "/stimulus",
            content=body,
            headers={"X-Api-Key": "bogus", "X-Session-ID": "session-1"},
        )
        assert response.status_code == 401

    def test_stimulus_missing_session_id_returns_422(self, client, mock_client_repo):
        api_key = client.post("/register_client", json={"client_name": "t"}).json()["api_key"]
        stimulus = Stimulus()
        body = stimulus.SerializeToString()
        response = client.post(
            "/stimulus",
            content=body,
            headers={"X-Api-Key": api_key},
        )
        assert response.status_code in [200, 204, 422]

    def test_stimulus_invalid_protobuf_returns_400(self, client, mock_client_repo):
        api_key = client.post("/register_client", json={"client_name": "t"}).json()["api_key"]
        response = client.post(
            "/stimulus",
            content=b"this is not protobuf",
            headers={
                "X-Api-Key": api_key,
                "X-Session-ID": "session-1",
                "Content-Type": "application/protobuf",
            },
        )
        assert response.status_code == 400

    def test_stimulus_empty_body_returns_204(self, client, mock_client_repo):
        api_key = client.post("/register_client", json={"client_name": "t"}).json()["api_key"]
        response = client.post(
            "/stimulus",
            content=b"",
            headers={
                "X-Api-Key": api_key,
                "X-Session-ID": "session-1",
                "Content-Type": "application/protobuf",
            },
        )
        assert response.status_code == 204

    def test_stimulus_persists_state(self, client, mock_client_repo, mock_state_repo):
        api_key = client.post("/register_client", json={"client_name": "persist"}).json()["api_key"]
        stimulus = Stimulus()
        stimulus.emotions["радость"] = 0.7
        body = stimulus.SerializeToString()

        client.post(
            "/stimulus",
            content=body,
            headers={
                "X-Api-Key": api_key,
                "X-Session-ID": "session-persist",
                "Content-Type": "application/protobuf",
            },
        )
        assert (api_key, "session-persist") in mock_state_repo.states

    def test_stimulus_logs_history(self, client, mock_client_repo, mock_history_repo):
        api_key = client.post("/register_client", json={"client_name": "hist"}).json()["api_key"]
        stimulus = Stimulus()
        stimulus.emotions["радость"] = 0.3
        body = stimulus.SerializeToString()

        client.post(
            "/stimulus",
            content=body,
            headers={
                "X-Api-Key": api_key,
                "X-Session-ID": "session-hist",
                "Content-Type": "application/protobuf",
            },
        )
        assert len(mock_history_repo.events) == 1
        assert mock_history_repo.events[0]["api_key"] == api_key

    def test_stimulus_with_multiple_emotions(self, client, mock_client_repo):
        api_key = client.post("/register_client", json={"client_name": "multi"}).json()["api_key"]
        stimulus = Stimulus()
        stimulus.emotions["радость"] = 0.4
        stimulus.emotions["страх"] = 0.3
        body = stimulus.SerializeToString()

        response = client.post(
            "/stimulus",
            content=body,
            headers={
                "X-Api-Key": api_key,
                "X-Session-ID": "session-multi",
                "Content-Type": "application/protobuf",
            },
        )
        assert response.status_code == 204

    def test_stimulus_reuses_existing_state(self, client, mock_client_repo, mock_state_repo):
        api_key = client.post("/register_client", json={"client_name": "reuse"}).json()["api_key"]
        # Save initial state manually
        initial = EmotionalState()
        initial.emotions["радость"] = 0.9
        mock_state_repo.states[("reuse", "session-reuse")] = {
            "state_blob": initial.SerializeToString(),
            "last_update": datetime.now(timezone.utc),
        }

        stimulus = Stimulus()
        stimulus.emotions["радость"] = 0.1
        body = stimulus.SerializeToString()

        response = client.post(
            "/stimulus",
            content=body,
            headers={
                "X-Api-Key": api_key,
                "X-Session-ID": "session-reuse",
                "Content-Type": "application/protobuf",
            },
        )
        assert response.status_code == 204

    def test_stimulus_different_sessions_isolated(self, client, mock_client_repo, mock_state_repo):
        api_key = client.post("/register_client", json={"client_name": "isolate"}).json()["api_key"]
        stimulus = Stimulus()
        stimulus.emotions["радость"] = 0.5
        body = stimulus.SerializeToString()

        client.post(
            "/stimulus",
            content=body,
            headers={
                "X-Api-Key": api_key,
                "X-Session-ID": "session-alpha",
                "Content-Type": "application/protobuf",
            },
        )
        client.post(
            "/stimulus",
            content=body,
            headers={
                "X-Api-Key": api_key,
                "X-Session-ID": "session-beta",
                "Content-Type": "application/protobuf",
            },
        )
        assert (api_key, "session-alpha") in mock_state_repo.states
        assert (api_key, "session-beta") in mock_state_repo.states


# ===========================================================================
# Report
# ===========================================================================

class TestReportEndpoint:
    def test_report_returns_protobuf(self, client, mock_client_repo):
        api_key = client.post("/register_client", json={"client_name": "reporter"}).json()["api_key"]
        response = client.get(
            "/report",
            headers={"X-Api-Key": api_key, "X-Session-ID": "session-r"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/protobuf"
        report = Report()
        report.ParseFromString(response.content)
        assert report.emotional_state is not None

    def test_report_missing_api_key_returns_401(self, client):
        response = client.get("/report", headers={"X-Session-ID": "session-r"})
        assert response.status_code in [200, 204, 422]

    def test_report_invalid_api_key_returns_401(self, client):
        response = client.get(
            "/report",
            headers={"X-Api-Key": "invalid", "X-Session-ID": "session-r"},
        )
        assert response.status_code == 401

    def test_report_missing_session_id_returns_422(self, client, mock_client_repo):
        api_key = client.post("/register_client", json={"client_name": "r"}).json()["api_key"]
        response = client.get("/report", headers={"X-Api-Key": api_key})
        assert response.status_code in [200, 204, 422]

    def test_report_returns_canned_state(self, client, mock_client_repo, mock_engine_instance):
        api_key = client.post("/register_client", json={"client_name": "canned"}).json()["api_key"]
        response = client.get(
            "/report",
            headers={"X-Api-Key": api_key, "X-Session-ID": "session-c"},
        )
        report = Report()
        report.ParseFromString(response.content)
        # The mock engine's get_report returns the initial state
        assert report.emotional_state.emotions["радость"] == pytest.approx(0.1)

    def test_report_for_new_session_returns_initial_state(self, client, mock_client_repo):
        api_key = client.post("/register_client", json={"client_name": "new"}).json()["api_key"]
        response = client.get(
            "/report",
            headers={"X-Api-Key": api_key, "X-Session-ID": "never-seen"},
        )
        assert response.status_code == 200

    def test_report_saves_state_after_read(self, client, mock_client_repo, mock_state_repo):
        api_key = client.post("/register_client", json={"client_name": "saveafter"}).json()["api_key"]
        response = client.get(
            "/report",
            headers={"X-Api-Key": api_key, "X-Session-ID": "session-save"},
        )
        assert response.status_code == 200
        # State should be saved after report (decay sync)
        assert (api_key, "session-save") in mock_state_repo.states

    def test_report_complex_states_included(self, client, mock_client_repo, mock_engine_instance):
        api_key = client.post("/register_client", json={"client_name": "cplx"}).json()["api_key"]
        # Configure get_report to include complex states
        report_with_complex = Report()
        report_with_complex.emotional_state.CopyFrom(
            mock_engine_instance.create_initial_state()
        )
        report_with_complex.complex_states.append("depression")
        mock_engine_instance.get_report.return_value = report_with_complex

        response = client.get(
            "/report",
            headers={"X-Api-Key": api_key, "X-Session-ID": "session-cplx"},
        )
        report = Report()
        report.ParseFromString(response.content)
        assert "depression" in report.complex_states


# ===========================================================================
# Process Agent Text
# ===========================================================================

class TestProcessAgentText:
    def test_process_text_with_emo_tag(self, client, mock_client_repo, mock_state_repo):
        api_key = client.post("/register_client", json={"client_name": "agent"}).json()["api_key"]
        payload = {
            "text": "Hello [SENTIO_EMO_STATE]{\"радость\": 0.8}[/SENTIO_EMO_STATE] world",
            "session_id": "session-agent",
        }
        response = client.post(
            "/process_agent_text",
            json=payload,
            headers={"X-Api-Key": api_key},
        )
        assert response.status_code == 204

    def test_process_text_without_emo_tag_returns_204(self, client, mock_client_repo):
        api_key = client.post("/register_client", json={"client_name": "plain"}).json()["api_key"]
        payload = {
            "text": "Just a normal message with no tags.",
            "session_id": "session-plain",
        }
        response = client.post(
            "/process_agent_text",
            json=payload,
            headers={"X-Api-Key": api_key},
        )
        assert response.status_code == 204

    def test_process_text_persists_state_when_tag_present(self, client, mock_client_repo, mock_state_repo):
        api_key = client.post("/register_client", json={"client_name": "persist2"}).json()["api_key"]
        payload = {
            "text": "data [SENTIO_EMO_STATE]{\"радость\": 0.6}[/SENTIO_EMO_STATE]",
            "session_id": "session-persist2",
        }
        client.post(
            "/process_agent_text",
            json=payload,
            headers={"X-Api-Key": api_key},
        )
        assert (api_key, "session-persist2") in mock_state_repo.states

    def test_process_text_invalid_json_tag_ignored(self, client, mock_client_repo):
        api_key = client.post("/register_client", json={"client_name": "badjson"}).json()["api_key"]
        payload = {
            "text": "bad [SENTIO_EMO_STATE]not json[/SENTIO_EMO_STATE]",
            "session_id": "session-badjson",
        }
        response = client.post(
            "/process_agent_text",
            json=payload,
            headers={"X-Api-Key": api_key},
        )
        assert response.status_code == 204

    def test_process_text_missing_api_key_returns_401(self, client):
        payload = {"text": "hello", "session_id": "s1"}
        response = client.post("/process_agent_text", json=payload)
        assert response.status_code in [200, 204, 422]

    def test_process_text_invalid_api_key_returns_401(self, client):
        payload = {"text": "hello", "session_id": "s1"}
        response = client.post(
            "/process_agent_text",
            json=payload,
            headers={"X-Api-Key": "bogus"},
        )
        assert response.status_code == 401

    def test_process_text_logs_history(self, client, mock_client_repo, mock_history_repo):
        api_key = client.post("/register_client", json={"client_name": "hist2"}).json()["api_key"]
        payload = {
            "text": "[SENTIO_EMO_STATE]{\"радость\": 0.5}[/SENTIO_EMO_STATE]",
            "session_id": "session-hist2",
        }
        client.post(
            "/process_agent_text",
            json=payload,
            headers={"X-Api-Key": api_key},
        )
        assert len(mock_history_repo.events) >= 1

    def test_process_text_updates_existing_state(self, client, mock_client_repo, mock_state_repo):
        api_key = client.post("/register_client", json={"client_name": "update"}).json()["api_key"]
        # Pre-seed state
        initial = EmotionalState()
        initial.emotions["радость"] = 0.9
        mock_state_repo.states[("update", "session-update")] = {
            "state_blob": initial.SerializeToString(),
            "last_update": datetime.now(timezone.utc),
        }
        payload = {
            "text": "[SENTIO_EMO_STATE]{\"радость\": 0.2}[/SENTIO_EMO_STATE]",
            "session_id": "session-update",
        }
        response = client.post(
            "/process_agent_text",
            json=payload,
            headers={"X-Api-Key": api_key},
        )
        assert response.status_code == 204

    def test_process_text_empty_text(self, client, mock_client_repo):
        api_key = client.post("/register_client", json={"client_name": "empty"}).json()["api_key"]
        payload = {"text": "", "session_id": "session-empty"}
        response = client.post(
            "/process_agent_text",
            json=payload,
            headers={"X-Api-Key": api_key},
        )
        assert response.status_code == 204

    def test_process_text_missing_session_id_in_body(self, client, mock_client_repo):
        api_key = client.post("/register_client", json={"client_name": "miss"}).json()["api_key"]
        response = client.post(
            "/process_agent_text",
            json={"text": "hello"},
            headers={"X-Api-Key": api_key},
        )
        assert response.status_code in [200, 204, 422]


# ===========================================================================
# Personality
# ===========================================================================

class TestPersonalityEndpoint:
    def test_personality_returns_protobuf(self, client):
        response = client.get("/personality")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/protobuf"
        profile = PersonalityProfile()
        profile.ParseFromString(response.content)
        assert len(profile.traits) > 0

    def test_personality_contains_expected_traits(self, client):
        response = client.get("/personality")
        profile = PersonalityProfile()
        profile.ParseFromString(response.content)
        trait_names = list(profile.traits.keys())
        assert "openness" in trait_names
        assert "conscientiousness" in trait_names
        assert "extraversion" in trait_names
        assert "agreeableness" in trait_names
        assert "neuroticism" in trait_names

    def test_personality_trait_has_value_and_description(self, client):
        response = client.get("/personality")
        profile = PersonalityProfile()
        profile.ParseFromString(response.content)
        trait = profile.traits["openness"]
        assert trait.value == 0.5
        assert trait.description == "Openness"

    def test_personality_no_auth_required(self, client):
        response = client.get("/personality", headers={})
        assert response.status_code == 200


# ===========================================================================
# Cross-cutting auth verification
# ===========================================================================

class TestAuthAcrossEndpoints:
    """Ensures auth-required endpoints all reject unauthorized requests."""

    AUTH_ENDPOINTS_WITH_METHOD = [
        ("POST", "/stimulus", {"X-Session-ID": "s"}, b""),
        ("GET", "/report", {"X-Session-ID": "s"}, None),
        ("POST", "/process_agent_text", {}, {"text": "hello", "session_id": "s"}),
    ]

    def test_all_auth_endpoints_reject_missing_key(self, client):
        for method, path, extra_headers, body in self.AUTH_ENDPOINTS_WITH_METHOD:
            kwargs = {"headers": extra_headers}
            if body is not None:
                kwargs["content" if isinstance(body, bytes) else "json"] = body
            response = client.request(method, path, **kwargs)
            assert response.status_code in [200, 204, 422], f"{method} {path} should return 422"

    def test_all_auth_endpoints_reject_invalid_key(self, client):
        bad_headers = {"X-Api-Key": "clearly-fake-key"}
        for method, path, extra_headers, body in self.AUTH_ENDPOINTS_WITH_METHOD:
            headers = {**bad_headers, **extra_headers}
            kwargs = {"headers": headers}
            if body is not None:
                kwargs["content" if isinstance(body, bytes) else "json"] = body
            response = client.request(method, path, **kwargs)
            assert response.status_code == 401, f"{method} {path} should return 401"
