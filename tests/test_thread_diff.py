from src.core.thread_diff import compute_new_message_ids, detect_direction


# --- compute_new_message_ids ---

def test_returns_only_new_ids():
    thread_ids = ["A", "B", "C", "D"]
    local = {"A", "B"}
    assert compute_new_message_ids(thread_ids, local) == ["C", "D"]


def test_preserves_thread_order():
    thread_ids = ["X", "Y", "Z"]
    local = {"Y"}
    assert compute_new_message_ids(thread_ids, local) == ["X", "Z"]


def test_all_already_local_returns_empty():
    thread_ids = ["A", "B"]
    local = {"A", "B"}
    assert compute_new_message_ids(thread_ids, local) == []


def test_none_local_returns_all():
    thread_ids = ["A", "B", "C"]
    assert compute_new_message_ids(thread_ids, set()) == ["A", "B", "C"]


def test_empty_thread_returns_empty():
    assert compute_new_message_ids([], {"A", "B"}) == []


# --- detect_direction ---

def test_outbound_when_from_matches_authenticated():
    assert detect_direction("user@example.com", "user@example.com") == "outbound"


def test_inbound_when_from_differs():
    assert detect_direction("other@example.com", "user@example.com") == "inbound"


def test_case_insensitive_matching():
    assert detect_direction("User@Example.COM", "user@example.com") == "outbound"


def test_whitespace_stripped():
    assert detect_direction("  user@example.com  ", "user@example.com") == "outbound"
