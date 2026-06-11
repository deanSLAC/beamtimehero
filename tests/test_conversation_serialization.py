"""Turns on one ConversationService must serialize: a staff reply from
the Slack LLM thread arriving mid-web-turn queues instead of spawning a
concurrent `claude --resume` against the same session."""
import threading
import time

import conversation as conv_mod


def test_concurrent_turns_serialize(monkeypatch):
    in_flight = []
    overlaps = []

    def fake_send(client, session_id, user_text, **kwargs):
        in_flight.append(user_text)
        if len(in_flight) > 1:
            overlaps.append(list(in_flight))
        time.sleep(0.1)
        in_flight.remove(user_text)
        return f"reply:{user_text}", [], []

    monkeypatch.setattr(conv_mod, "send_and_collect", fake_send)
    svc = conv_mod.ConversationService(persist=False)

    threads = [
        threading.Thread(target=svc.handle_message, args=(f"msg{i}",))
        for i in range(3)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not overlaps, f"turns overlapped: {overlaps}"
    roles = [m["role"] for m in svc.messages]
    assert roles == ["user", "assistant"] * 3, roles


def test_staff_turn_uses_same_lock(monkeypatch):
    order = []

    def fake_send(client, session_id, user_text, **kwargs):
        order.append(("start", user_text))
        time.sleep(0.05)
        order.append(("end", user_text))
        return "ok", [], []

    monkeypatch.setattr(conv_mod, "send_and_collect", fake_send)
    svc = conv_mod.ConversationService(persist=False)

    t1 = threading.Thread(target=svc.handle_message, args=("web",))
    t2 = threading.Thread(
        target=svc.handle_staff_llm, args=("staff says hi", "Alice")
    )
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    # Strict start/end nesting: no start before the previous end.
    for i in range(0, len(order), 2):
        assert order[i][0] == "start" and order[i + 1][0] == "end"
        assert order[i][1] == order[i + 1][1]
