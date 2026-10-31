from pathlib import Path

from emporio.agent import Agent
from emporio.config import ROOT, Clock, Provider
from emporio.journal import Journal
from emporio.llm import LLM, OpenAICompatibleLLM, build_embedder
from emporio.policies import load_sections
from emporio.retrieval import HybridIndex
from emporio.store import Store
from emporio.tools import Session, ToolContext, catalog_documents


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
        self.section_list = load_sections(data_dir / "policies.md")
        self.sections = {section.id: section for section in self.section_list}
        self._index_dir = data_dir / "index"
        self._indexes: dict[str, tuple[HybridIndex, HybridIndex]] = {}

    def indexes(self, provider: Provider | None) -> tuple[HybridIndex, HybridIndex]:
        key = f"{provider.name}:{provider.api_key}" if provider else "keyword"
        if key not in self._indexes:
            embedder = build_embedder(provider, self._index_dir) if provider else None
            self._indexes[key] = (
                HybridIndex(catalog_documents(self.store), embedder),
                HybridIndex([s.as_document() for s in self.section_list], embedder),
            )
        return self._indexes[key]

    def context(self, session: Session, provider: Provider | None) -> ToolContext:
        catalog_index, policy_index = self.indexes(provider)
        return ToolContext(
            store=self.store,
            catalog_index=catalog_index,
            policy_index=policy_index,
            sections=self.sections,
            clock=self.clock,
            journal=self.journal,
            session=session,
        )

    def agent(self, session: Session, provider: Provider, llm: LLM | None = None) -> Agent:
        return Agent(llm or OpenAICompatibleLLM(provider), self.context(session, provider))
