import json
import re

from llm.llm_setup import get_llm


def judge_answer(query: str, answer: str, chunks: list) -> dict:
    context = "\n\n".join(chunk.page_content for chunk in chunks)

    llm = get_llm(temperature=0)

    prompt = f"""You are a quality judge for a medical assistant's answers. Evaluate the ANSWER based on two criteria:
1. GROUNDEDNESS: Is the answer supported by the CONTEXT? (not made up)
2. RELEVANCE: Does the answer actually address the QUESTION?

CONTEXT:
{context}

QUESTION: {query}

ANSWER: {answer}

Respond ONLY in this exact JSON format:
{{"confidence": <number between 0 and 1>, "reason": "<short explanation>"}}"""

    response = llm.invoke(prompt)

    # The model occasionally wraps the JSON in prose or a ```json fence
    match = re.search(r"\{.*\}", response.content, re.DOTALL)
    try:
        result = json.loads(match.group(0))
        result["confidence"] = float(result["confidence"])
    except (AttributeError, ValueError, KeyError, json.JSONDecodeError):
        result = {"confidence": 0.5, "reason": "Failed to parse LLM response"}

    print(f"judge confidence: {result['confidence']} - {result['reason']}")

    return result


if __name__ == "__main__":
    from agents.navigator_agent import navigator
    from llm.generator import generate_answer

    query = "My mother is 50 and has had diabetes for seven years. She is on oral hypoglycaemics but her post-lunch sugar rises to 200. What lifestyle modifications can help?"

    print("── Step 1: Navigate ──")
    chunks = navigator(query)

    print("\n── Step 2: Generate ──")
    answer = generate_answer(query, chunks)
    print(f"\nAnswer: {answer[:1000]}...")

    print("\n── Step 3: Judge ──")
    judgment = judge_answer(query, answer, chunks)

    print("\n── Verdict ──")
    if judgment["confidence"] >= 0.7:
        print("Answer PASSED — send to user")
    else:
        print("Answer WEAK — retry")
