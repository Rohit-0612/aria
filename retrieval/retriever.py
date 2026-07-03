import sys
import os

sys.path.append(os.path.join (os.path.dirname(__file__), '..','vectorstore'))
from qdrant_store import load_vectorstore


def get_retriever (search_type: str = "mmr", k: int = 5):
    # Embeddings now live in Qdrant Cloud instead of local ChromaDB
    vectorstore = load_vectorstore()


    if search_type == "mmr":
        search_kwargs = {"k": k, "fetch_k": k * 4}

    else:
        search_kwargs = {"k": k}

    retriever = vectorstore.as_retriever(
        search_type= search_type,
        search_kwargs=search_kwargs

    )

    print(f"Retriever ready — type: {search_type}, k: {k}")
    
    return retriever


if __name__=="__main__":
    retriever = get_retriever(search_type= "mmr", k =5)

    query = "what is treatment of hypertension"
    print (f"\nquery: {query}")

    results = retriever.invoke(query)

    print (f"\n-- {len(results)} chunks retrieved__")
    for i, doc in enumerate (results):
        print (f"\nresult {i+1} (page{doc.metadata.get ('page','?')}):")
        print(f"{doc.page_content}")
    
