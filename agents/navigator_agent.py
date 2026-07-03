import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'llm'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'retrieval'))


from llm_setup import get_llm
from reranker import get_reranking_retriever

def optimize_query (query: str) -> str:

    llm = get_llm(temperature=0)

    prompt = f"""You are a medical search query optimizer.
Convert the user's question into a clear, concise medical search query.
Remove personal details, keep only the core medical concept.

Respond with ONLY the optimized query, nothing else.

User question: {query}

Optimized query:"""

    response = llm.invoke (prompt)
    optimized = response.content.strip()

    print (f"original : {query}")
    print (f"optimized : {optimized}")

    return optimized



def navigator (query: str, k: int = 10, top_n: int = 3):

    optimized_query = optimize_query(query)

    retriever = get_reranking_retriever (k=k, top_n = top_n)

    chunks = retriever.invoke (optimized_query)

    print (f"\n {len(chunks)} relevent chunks retrieved")

    return chunks



if __name__ == "__main__":
    user_query = "My grandmother has high blood pressure, what treatment is there?"

    print ("-------Navigator testing------\n")

    chunks = navigator(user_query)


    print ("--------Retrieved chunks--------\n")

    for i, doc in enumerate (chunks):
        print (f"\nchunk {i+1} (page {doc.metadata.get('page', '?')}):")
        print (f"{doc.page_content[:500]}")


