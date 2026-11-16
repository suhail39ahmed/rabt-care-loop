from agents.common.pii import scrub_pii_uae

def test_emirates_id():
    assert "[EMIRATES_ID]" in scrub_pii_uae("ID 784-1234-1234567-1")
