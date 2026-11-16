# Approved expert-call script — CRITICAL (demo)

Clinician identity: use your name and clinic. Do not diagnose over the phone.

1. Confirm patient identity (name + DOB) without reading lab values aloud over insecure channels if possible.
2. State: "Your recent screening result needs urgent clinician review today. This is not a diagnosis."
3. Ask: Are you able to go to the emergency department / urgent clinic now?
4. If yes → log outcome `reached_going_now` and book/confirm arrival path.
5. If refusing → explore barrier (cost/fear/time); offer coordinator callback; log `reached_refusing`.
6. If no answer → log `not_reached` and continue ladder.
