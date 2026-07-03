from langchain_community.document_loaders import PyPDFLoader
import os
import re

import warnings 
warnings.filterwarnings('ignore')

def load_pdf(pdf_path: str) -> list:
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF NOT FOUND: {pdf_path}")

    print(f"Loading PDF: {pdf_path}")
    print(f"This may take some time depending on the PDF size!")

    loader = PyPDFLoader(pdf_path)
    pages = loader.load()

    print(f"PDF Loaded Successfully!")
    print(f"Total pages loaded: {len(pages)}")
    print(f"sample of random page :\n{pages[64].page_content[:300]}")
    print(f"Metadata: \n {pages[64].metadata}")

    return pages

def clean_text(text: str)-> str:
    text =  re.sub(r'dipiro.*?\d+\s*\n', '', text, flags=re.IGNORECASE)
    text =  re.sub (r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)
    text = re.sub(r'\s+' , ' ' , text)
    text = text.strip()
    text = re.sub (r'[^\x00-\x7F]+', ' ', text)
    
    return text

def is_useful_page(text: str) -> bool:
    if len(text) < 100:
        return False

    only_numbers = re.sub(r'[\d\s\.\,]+', '', text)
    if len(only_numbers) < 20:
        return False

    return True

def load_and_clean_pdf (pdf_path: str) ->list:

    pages = load_pdf(pdf_path)
    cleaned_pages =[]
    skipped = 0

    for page in pages:
        cleaned_text = clean_text(page.page_content)
        
        if not is_useful_page(cleaned_text):
            skipped+=1
            continue

        page.page_content = cleaned_text
        cleaned_pages.append(page)

    print(f"\n------------CLEANING SUMARY------------")
    print(f"Total cleaned pages : {len(pages)}")
    print(f"pages skipped : {skipped}")
    print(f"useful_pages : {len(cleaned_pages)}")
    print(f"------------END OF SUMMARY------------")

    return cleaned_pages
        


if __name__ == "__main__":
   pages = load_and_clean_pdf("data/dipiro_raw.pdf")


   print("── Sample Page (index 5) ─────────────")
   print("Text:", pages[5].page_content[:400])
   print("Metadata:", pages[5].metadata)

    