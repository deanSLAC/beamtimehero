"""Session lifecycle: failed first turns and failed resumes must re-mint
the session instead of wedging the conversation, and the persisted
manifest must round-trip across a restart."""
import conversation as conv_mod
from conversation import ConversationService


def _failing_send(*args, **kwargs):
    raise RuntimeError("claude exited with code 1: boom")


def test_first_turn_failure_remints_session(monkeypatch):
    monkeypatch.setattr(conv_mod, "send_and_collect", _failing_send)
    svc = ConversationService(persist=False)
    original = svc.session_id

    result = svc.handle_message("hello")

    assert result.text.startswith("Error:")
    assert svc.session_id != original, (
        "retry would re-run --session-id with a possibly-created UUID"
    )
    assert svc.is_started is False


def test_resume_failure_remints_and_resets(monkeypatch):
    monkeypatch.setattr(conv_mod, "send_and_collect", _failing_send)
    svc = ConversationService(persist=False)
    svc.is_started = True
    original = svc.session_id

    result = svc.handle_message("hello again")

    assert svc.session_id != original
    assert svc.is_started is False
    assert "could not be resumed" in result.text


def test_manifest_round_trip(monkeypatch, tmp_path):
    state_file = tmp_path / "conversation_state.json"
    monkeypatch.setattr(conv_mod, "STATE_FILE", state_file)

    def ok_send(client, session_id, user_text, **kwargs):
        return "the reply", [], ["b64plotdata"]

    monkeypatch.setattr(conv_mod, "send_and_collect", ok_send)
    svc = ConversationService()
    svc.handle_message("question")
    assert state_file.exists()

    restored = ConversationService.from_state()
    assert restored is not None
    assert restored.session_id == svc.session_id
    assert restored.is_started is True
    roles = [m["role"] for m in restored.messages]
    assert roles == ["user", "assistant"]
    # Image payloads are stripped from the manifest, count is kept.
    assert "images" not in restored.messages[1]
    assert restored.messages[1]["plot_count"] == 1


def test_clear_state_removes_manifest(monkeypatch, tmp_path):
    state_file = tmp_path / "conversation_state.json"
    monkeypatch.setattr(conv_mod, "STATE_FILE", state_file)
    state_file.write_text("{}")
    ConversationService.clear_state()
    assert not state_file.exists()
