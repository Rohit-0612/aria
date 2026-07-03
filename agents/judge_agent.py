import sys
import os
import json

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'llm'))
from llm_setup import get_llm

def judge_answer (query: str, answer: str, chunks: list) -> dict:
    context = "\n.\n.join ([chunk.page_content for chunk in chunks])"

    llm = get_llm (temperature=0)

    prompt = f"""You are a quality judge for a medical assistant's answers. Evaluate the ANSWER based on two criteria:
1. GROUNDEDNESS: Is the answer supported by the CONTEXT? (not made up)
2. RELEVANCE: Does the answer actually address the QUESTION?

CONTEXT:
{context}

QUESTION: {query}

ANSWER: {answer}

Respond ONLY in this exact JSON format:
{{"confidence": <number between 0 and 1>, "reason": "<short explanation>"}}"""

    response = llm.invoke (prompt)

    try: 
        result = json.loads (response.content.strip())

    except:
        result = {"confidence": 0.5, "reason": "Failed to parse LLM response"}

    print (f"judge confidence: {result['confidence']} - {result['reason']}")

    return result

if __name__ == "__main__":
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'agents'))
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'llm'))
    
    from navigator_agent import navigator
    from generator import generate_answer
    
    query = "my mother is a 50 year old woman, and she is having diabetes since last seven years  she is on oral hypoglycaemic drugs, but after her lunch, the Sugar level of an increase up to 200 what I can do to fix this, can you suggest me some lifestyle modifications, or other tricks that I can use?"
    
    print("── Step 1: Navigate ──")

    chunks = navigator(query)
    
    print("\n── Step 2: Generate ──")

    answer = generate_answer(query, chunks)

    print(f"\nAnswer: {answer[:1000]}...")
    
    print("\n── Step 3: Judge ──")
    judgment = judge_answer(query, answer, chunks)
    
    print(f"\n── Verdict ──")

    if judgment["confidence"] >= 0.7:
        print("Answer PASSED — send to user")
    else:
        print("Answer WEAK — retry ")

    



    

    