"""Typed case lookup errors — do not use bare KeyError for missing cases."""


class CaseNotFound(Exception):
    """Raised when a case id is unknown. Maps to HTTP 404."""

    def __init__(self, case_id: str = "") -> None:
        self.case_id = case_id
        super().__init__("case not found")
