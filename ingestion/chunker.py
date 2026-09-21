from pdf_loader import load_and_clean_pdf 

from langchain_text_splitters import RecursiveCharacterTextSplitter   # ✅

def chunk_documents(pages:list, chunk_size=1000, chunk_overlap=200):

    splitter = RecursiveCharacterTextSplitter(
        separators = ["\n\n", "\n", ". ", " ", ""],
        chunk_size = chunk_size,
        chunk_overlap = chunk_overlap,
        length_function = len,
        add_start_index = True
    )

    chunks = splitter.split_documents(pages)  

    print (f"-------------chunking summary------------")
    print(f"Total chunks created: {len(chunks)}")
    print(f"input pages: {len(pages)}")
    print(f"average characters per chunk: {sum(len(c.page_content) for c in chunks) // len(chunks)}") 
    print (f"-------------END OF SUMMARY------------")

    return chunks

if __name__=="__main__":
    pages = load_and_clean_pdf ("data/dipiro_raw.pdf")
    chunks = chunk_documents(pages)

    print("── Sample Chunk ──────────────────────")
    print("Content:", chunks[10].page_content[:300])
    print("Metadata:", chunks[10].metadata)