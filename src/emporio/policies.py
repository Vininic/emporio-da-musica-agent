import re
from dataclasses import dataclass
from pathlib import Path

from emporio.retrieval import Document


@dataclass(frozen=True)
class Section:
    id: str
    title: str
    text: str

    def as_document(self) -> Document:
        return Document(self.id, f"{self.id} {self.title}", self.text)


def load_sections(path: Path) -> list[Section]:
    content = path.read_text(encoding="utf-8")
    matches = list(re.finditer(r"^## (\d+(?:\.\d+)?) (.+)$", content, flags=re.M))
    sections = []
    for match, following in zip(matches, [*matches[1:], None], strict=True):
        end = following.start() if following else len(content)
        sections.append(Section(match[1], match[2], content[match.end() : end].strip()))
    return sections
