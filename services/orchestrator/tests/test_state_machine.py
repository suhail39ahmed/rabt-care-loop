from hypothesis import given, strategies as st

from app.state_machine import ALLOWED, S, IllegalTransition, transition


def test_sc01_happy_path():
    path = [
        (S.NEW, S.TRIAGED),
        (S.TRIAGED, S.AWAITING_OWNER),
        (S.AWAITING_OWNER, S.OWNED),
        (S.OWNED, S.NOTIFIED),
        (S.NOTIFIED, S.UNDERSTOOD),
        (S.UNDERSTOOD, S.REFERRED),
        (S.REFERRED, S.BOOKED),
        (S.BOOKED, S.ATTENDED),
        (S.ATTENDED, S.CLOSURE_PENDING),
        (S.CLOSURE_PENDING, S.CLOSED),
    ]
    for cur, nxt in path:
        rec = transition(cur, nxt, actor="test", reason="ok", evidence={"closure_ok": True})
        assert rec["to"] == nxt.value


def test_illegal_new_to_closed():
    try:
        transition(S.NEW, S.CLOSED, actor="test", reason="nope", evidence={"closure_ok": True})
        assert False, "should raise"
    except IllegalTransition:
        pass


def test_closed_requires_evidence():
    try:
        transition(S.CLOSURE_PENDING, S.CLOSED, actor="agent:closure", reason="x", evidence={})
        assert False
    except IllegalTransition:
        pass


def test_closed_by_human_requires_human_actor():
    try:
        transition(S.ON_HOLD_CONSENT, S.CLOSED_BY_HUMAN, actor="agent:x", reason="x")
        assert False
    except IllegalTransition:
        pass
    rec = transition(S.ON_HOLD_CONSENT, S.CLOSED_BY_HUMAN, actor="human:coord", reason="declined_care")
    assert rec["to"] == "ClosedByHuman"


@given(
    cur=st.sampled_from(list(ALLOWED.keys())),
    nxt=st.sampled_from(list(S)),
)
def test_random_walk_respects_allowed(cur: S, nxt: S):
    if nxt in ALLOWED[cur]:
        evidence = {"closure_ok": True} if nxt is S.CLOSED else {}
        actor = "human:t" if nxt is S.CLOSED_BY_HUMAN else "test"
        transition(cur, nxt, actor=actor, reason="hyp", evidence=evidence)
    else:
        try:
            transition(cur, nxt, actor="human:t", reason="hyp", evidence={"closure_ok": True})
            assert False
        except IllegalTransition:
            pass
