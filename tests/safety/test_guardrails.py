from agents.common.guardrails import content_safe, has_red_flag, no_diagnosis


ADVERSARIAL = [
    "You have diabetes based on this result",
    "This means you have cancer",
    "You are diagnosed with hypertension",
    "لديك سرطان",
    "You have cancer",
]


def test_no_diagnosis_blocks_adversarial():
    for text in ADVERSARIAL:
        assert no_diagnosis(text) is False
        assert content_safe(text) is False


def test_safe_template_passes():
    text = "Your screening result needs a follow-up. This is not a diagnosis."
    assert no_diagnosis(text)
    assert content_safe(text)


def test_red_flags():
    assert has_red_flag("I want to kill myself")
    assert not has_red_flag("When is my appointment?")
