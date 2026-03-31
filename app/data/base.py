from abc import ABC, abstractmethod


class DataBackend(ABC):

    @abstractmethod
    def list_biographies(self) -> list[dict]:
        """Return list of {slug, name, paragraph_count, volume}."""
        ...

    @abstractmethod
    def get_paragraphs(self, slug: str) -> list[dict]:
        """Return all paragraph objects for a biography."""
        ...

    @abstractmethod
    def get_paragraph(self, slug: str, paragraph_id: int) -> dict | None:
        """Return one paragraph with viewer_data built, or None if not found."""
        ...