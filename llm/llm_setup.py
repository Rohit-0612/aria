import os
from dotenv import load_dotenv 
from langchain_groq import ChatGroq

load_dotenv()

def get_llm (temperature: float = 0):

    llm = ChatGroq(
        model = "llama-3.3-70b-versatile",
        temperature = temperature,
        max_tokens = 4096,  # generous headroom so answers are never length-capped
        api_key=os.getenv("GROQ_API_KEY")    )

    return llm


if __name__ == "__main__":
    llm = get_llm()
    response = llm.invoke("what is diabetes mellitus")

    print("\n"+response.content)
    


