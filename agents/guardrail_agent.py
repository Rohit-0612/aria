from llm.llm_setup import get_llm


def check_guardrail(query: str) -> bool:
    llm = get_llm (temperature = 0)

    prompt = f"""You are a guardrail for a medical chatbot based on a pharmacology textbook.

Your job: Decide if the user's question is related to medicine, pharmacology, diseases, drugs, treatments, or health.

Respond with ONLY one word:
- "YES" if it is medical/health related
- "NO" if it is not

User question: {query}

Answer (YES or NO):"""

    response = llm.invoke(prompt)
    decision = response.content.strip().upper()

    print (f"Guardrail check : '{query}'->{decision}")

    return "YES" in decision


if __name__ == "__main__":
    test_queries = [
        "what is hypertension?",
        "Tell me about metformin",
        "How to treat diabetes?",
        "What is the capital of France?",
        "Why is the sky blue?",
        "How to cure a cold?",
        "What is the weather today?"
    ]

    print (f"\nTesting guardrail:")
    for q in test_queries:
        is_medical = check_guardrail(q)
        status = "ALLOWED" if is_medical else "REJECTED"
        print(f"{status}: {q}\n")

        
    