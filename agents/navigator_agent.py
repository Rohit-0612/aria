from llm.llm_setup import get_llm
from retrieval.reranker import get_balanced_retriever

# Built once and reused: creating it loads the embedding model and opens
# the Qdrant connection, which is far too slow to repeat per query.
_retriever = None


def optimize_query(query: str) -> str:
    llm = get_llm(temperature=0)

    prompt = f"""You are a medical search query optimizer.
Convert the user's question into a clear, concise medical search query.
Remove personal details, keep only the core medical concept.

Respond with ONLY the optimized query, nothing else.

User question: {query}

Optimized query:"""

    response = llm.invoke(prompt)
    optimized = response.content.strip()

    print(f"original : {query}")
    print(f"optimized : {optimized}")

    return optimized


def navigator(query: str):
    global _retriever
    if _retriever is None:
        _retriever = get_balanced_retriever()

    optimized_query = optimize_query(query)
    chunks = _retriever.invoke(optimized_query)

    print(f"\n {len(chunks)} relevant chunks retrieved")

    return chunks


if __name__ == "__main__":
    user_query = "My grandmother has high blood pressure, what treatment is there?"

    print("-------Navigator testing------\n")
    chunks = navigator(user_query)

    print("--------Retrieved chunks--------\n")
    for i, doc in enumerate(chunks):
        print(f"\nchunk {i+1} (page {doc.metadata.get('page', '?')}):")
        print(f"{doc.page_content[:500]}")
