"""An append-only audit trail of the operations a bank performs."""

from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal

ACCEPTED = "accepted"
REJECTED = "rejected"


@dataclass(frozen=True)
class AuditEntry:
    """One audited operation with its sequence number, action, account, optional amount, accepted or
    rejected outcome and free-text detail.
    """

    sequence: int
    action: str
    account_id: str
    amount: Decimal | None
    outcome: str
    detail: str = ""


class AuditLog:
    """An ordered, append-only collection of audit entries."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def __len__(self) -> int:
        """Return the number of entries recorded so far."""
        return len(self._entries)

    def __iter__(self) -> Iterator[AuditEntry]:
        """Iterate over the entries in the order they were recorded."""
        return iter(self._entries)

    def record(
        self,
        action: str,
        account_id: str,
        amount: Decimal | None = None,
        outcome: str = ACCEPTED,
        detail: str = "",
    ) -> AuditEntry:
        """Append and return an entry numbered after the last one, raising ValueError for an outcome
        other than accepted or rejected.
        """
        if outcome not in (ACCEPTED, REJECTED):
            raise ValueError(f"Unknown outcome: {outcome}")
        entry = AuditEntry(len(self._entries) + 1, action, account_id, amount, outcome, detail)
        self._entries.append(entry)
        return entry

    def for_account(self, account_id: str) -> list[AuditEntry]:
        """Return every entry requested on the given account, oldest first."""
        return [entry for entry in self._entries if entry.account_id == account_id]

    def rejected(self) -> list[AuditEntry]:
        """Return every entry whose operation was rejected, oldest first."""
        return [entry for entry in self._entries if entry.outcome == REJECTED]
