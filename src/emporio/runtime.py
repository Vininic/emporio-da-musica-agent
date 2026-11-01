from pathlib import Path

from emporio.agent import Agent
from emporio.config import ROOT, Clock, Provider
from emporio.i18n import LANGS, Lang
from emporio.journal import Journal
from emporio.llm import LLM, OpenAICompatibleLLM, build_embedder
from emporio.policies import load_sections
from emporio.retrieval import HybridIndex
from emporio.store import Store
from emporio.tools import Session, ToolContext, catalog_documents

UNSEARCHABLE = {"1.2"}
MANUALS = {"pt": "policies.md", "en": "policies.en.md"}


class Runtime:
    def __init__(
        self,
        clock: Clock | None = None,
        journal: Journal | None = None,
        data_dir: Path = ROOT / "data",
    ):
        self.clock = clock or Clock.from_env()
        self.journal = journal or Journal()
        self.store = Store(data_dir / "raw")
        self.sections = {
            lang: {s.id: s for s in load_sections(data_dir / MANUALS[lang])} for lang in LANGS
        }
        self._index_dir = data_dir / "index"
        self._indexes: dict[str, tuple[HybridIndex, HybridIndex]] = {}

    def indexes(
        self, provider: Provider | None, lang: Lang = "pt"
    ) -> tuple[HybridIndex, HybridIndex]:
        key = f"{lang}:{provider.name}:{provider.api_key}" if provider else f"{lang}:keyword"
        if key not in self._indexes:
            embedder = build_embedder(provider, self._index_dir) if provider else None
            documents = [
                section.as_document()
                for section in self.sections[lang].values()
                if section.id not in UNSEARCHABLE
            ]
            self._indexes[key] = (
                HybridIndex(catalog_documents(self.store), embedder),
                HybridIndex(documents, embedder),
            )
        return self._indexes[key]

    def context(
        self, session: Session, provider: Provider | None, lang: Lang = "pt"
    ) -> ToolContext:
        catalog_index, policy_index = self.indexes(provider, lang)
        return ToolContext(
            store=self.store,
            catalog_index=catalog_index,
            policy_index=policy_index,
            sections=self.sections[lang],
            clock=self.clock,
            journal=self.journal,
            session=session,
            lang=lang,
        )

    def agent(
        self, session: Session, provider: Provider, llm: LLM | None = None, lang: Lang = "pt"
    ) -> Agent:
        return Agent(llm or OpenAICompatibleLLM(provider), self.context(session, provider, lang))
