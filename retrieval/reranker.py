import sys
import os

from dotenv import load_dotenv

load_dotenv()

from langchain_cohere import CohereRerank
from langchain_classic.retrievers import  ContextualCompressionRetriever
from qdrant_client.models import Filter, FieldCondition, MatchValue

sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'vectorstore'))
from retriever import get_retriever
from qdrant_store import load_vectorstore

# Qdrant filter that matches only RxPrep chunks (payload field metadata.book)
RXPREP_FILTER = Filter(
    must=[FieldCondition(key="metadata.book", match=MatchValue(value="rxprep"))]
)


class BalancedRetriever:
    """
    Source-balanced retrieval across both books.

    The store holds far more DiPiro vectors than RxPrep, so a plain top-k
    search is numerically dominated by DiPiro and RxPrep never reaches the
    reranker. Here we pull a global candidate set AND a guaranteed RxPrep
    set (via metadata filter), merge them, and let Cohere rerank decide what
    is genuinely most relevant — so both books always get a fair hearing.
    """

    def __init__(self, vectorstore, reranker, k_global: int = 14, k_rxprep: int = 8):
        self.vs = vectorstore
        self.reranker = reranker
        self.k_global = k_global
        self.k_rxprep = k_rxprep

    def invoke(self, query: str):
        glob = self.vs.similarity_search(query, k=self.k_global)
        rx = self.vs.similarity_search(query, k=self.k_rxprep, filter=RXPREP_FILTER)

        seen, candidates = set(), []
        for d in glob + rx:
            key = d.page_content[:120]
            if key in seen:
                continue
            seen.add(key)
            candidates.append(d)

        if not candidates:
            return []
        reranked = self.reranker.compress_documents(candidates, query)
        n_rx = sum(1 for d in reranked if d.metadata.get("book") == "rxprep")
        print(f"Balanced retrieve: {len(candidates)} candidates -> {len(reranked)} kept "
              f"({n_rx} RxPrep, {len(reranked) - n_rx} DiPiro)")
        return list(reranked)


def get_balanced_retriever(k_global: int = 14, k_rxprep: int = 8, top_n: int = 5):
    vectorstore = load_vectorstore()
    reranker = CohereRerank(
        model="rerank-english-v3.0",
        top_n=top_n,
        cohere_api_key=os.getenv("COHERE_API_KEY"),
    )
    print(f"Balanced retriever ready - global {k_global} + RxPrep {k_rxprep}, rerank to top {top_n}")
    return BalancedRetriever(vectorstore, reranker, k_global, k_rxprep)


def get_reranking_retriever (k: int = 10, top_n: int = 3):

    base_retriever = get_retriever(search_type= "mmr", k=k)


    reranker = CohereRerank(
        model ="rerank-english-v3.0",
        top_n =top_n,
        cohere_api_key=os.getenv ("COHERE_API_KEY")

    
    )


    compression_retriever = ContextualCompressionRetriever(
    base_compressor=reranker,
    base_retriever=base_retriever
    
    )



    print (f"Reranking retriever ready - retrieve {k}, rerank to top {top_n}")

    return compression_retriever

if __name__ == "__main__":

    retriever = get_reranking_retriever (k=10, top_n = 3)
    query = "what is diabetes mellitus"

    print (f"\nQuery: {query}")

    results = retriever.invoke(query)

    print (f"\n-------top {len(results)} reranked chunks------")
    for i, doc in enumerate (results):
        score = doc.metadata.get ('relevance_score', 'N/A')
        print (f"\nRank {i+1}(page {doc.metadata.get ('page','?')}, score:{score}):")
        print (f"{doc.page_content [:1000]}")
        



