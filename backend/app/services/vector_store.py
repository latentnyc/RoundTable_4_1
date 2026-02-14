import logging
from typing import List

class VectorStore:
    def __init__(self):
        pass

    def add_document(self, doc_id: str, content: str, metadata: dict = {}):
        logging.warning(f"Vector Store is currently disabled. Document {doc_id} was not added.")

    def query(self, query_text: str, n_results: int = 3) -> List[str]:
        logging.warning("Vector Store is currently disabled. Returning empty results.")
        return []

# Global instance
vector_store = None

def get_vector_store():
    global vector_store
    if vector_store is None:
        vector_store = VectorStore()
    return vector_store
