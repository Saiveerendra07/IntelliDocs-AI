from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class PageContent(BaseModel):
    page_number: int
    text: str
    ocr_applied: bool = False
    section_title: Optional[str] = None
    tables_json: Optional[Any] = None


class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, file_path: str) -> List[PageContent]:
        """
        Extracts structured PageContent instances from the provided file path.
        """
        pass
