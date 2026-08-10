from app.core.errors import BatchNotFoundError
from app.schemas.kpi import BatchResult


class BatchStore:
    def __init__(self) -> None:
        self._batches: dict[str, BatchResult] = {}

    def save(self, batch: BatchResult) -> None:
        self._batches[batch.batch_id] = batch

    def get(self, batch_id: str) -> BatchResult:
        """Raises BatchNotFoundError if the id is unknown."""
        batch = self._batches.get(batch_id)
        if batch is None:
            raise BatchNotFoundError(
                f"No batch with id {batch_id!r}.", {"batch_id": batch_id}
            )
        return batch

    def list(self) -> list[BatchResult]:
        """Newest first."""
        return sorted(self._batches.values(), key=lambda b: b.created_at, reverse=True)

    def clear(self) -> None:
        self._batches.clear()


_store = BatchStore()


def get_store() -> BatchStore:
    """FastAPI dependency / accessor for the process-wide store."""
    return _store
