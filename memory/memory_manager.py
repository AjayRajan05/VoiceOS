from memory.memory_graph import MemoryGraph
from memory.entity_extractor import EntityExtractor


class _InMemoryVectorStore:
    def __init__(self):
        self._docs = []

    def add_memory(self, text):
        self._docs.append(text)

    def search(self, query):
        q = query.lower()
        hits = [d for d in self._docs if q in d.lower()]
        return [hits[-3:]]


def _build_vector_store():
    try:
        from memory.vector_store import VectorStore
        return VectorStore()
    except ImportError:
        return _InMemoryVectorStore()


class MemoryManager:

    def __init__(self):
        self.vector_store = _build_vector_store()
        self.graph = MemoryGraph()
        self.extractor = EntityExtractor()

    def store(self, text):
        self.vector_store.add_memory(text)
        fact = self.extractor.extract(text)
        if fact:
            self.graph.add_fact(
                fact["entity"],
                fact["relation"],
                fact["value"],
            )

    def retrieve(self, query):
        return self.vector_store.search(query)
