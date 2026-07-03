from langchain_huggingface import HuggingFaceEmbeddings

def load_embedding_model(model_name: str = "all-MiniLM-L6-v2"):

    print(f"Loading embedding model : {model_name}")
    print(f"It amy take some time to download from the internet")

    embeddings = HuggingFaceEmbeddings(
        model_name = model_name,
        model_kwargs = {"device": "cpu"},
        encode_kwargs = {"normalize_embeddings": True}
    )

    print (f"Embedding model is ready")
    return embeddings

def get_embeddings_for_text (text: str, embeddings_model):

    embeddings = embeddings_model.embed_query (text)
 
    print(f" \nText = '{text}'")
    print(f" Embedding size : {len(embeddings)} numbers")
    print(f"First 5 numbers: {embeddings[:5]}")
    
    return embeddings

if __name__ == "__main__":
    model = load_embedding_model()

    texts = [
        "AI chips demand increased",
        "GPU sales went up",
        "Cricket match was exciting"
    ]

    embeddings = []

    for text in texts:
        emb = get_embeddings_for_text(text, model)
        embeddings.append(emb)

    print (f"-----------similarity_check-----------")
    print (f" AI Chips and GPU Similarity")

    similarity = sum (a * b for a, b in zip (embeddings [0], embeddings [1]))
    print(f"similarity score : {similarity : .4f}")
    
    similarity_2= sum (a * b for a, b in zip (embeddings [0], embeddings [2]))
    print(f"similarity score : {similarity_2 : .4f}")