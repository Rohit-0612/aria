import sys
import os

sys.path.append(os.path.dirname(__file__))
from nodes import (
    guardrail_node,
    navigator_node,
    generator_node,
    judge_node,
    reject_node
)

from typing import TypedDict
from langgraph.graph import StateGraph, START, END


class AriaState(TypedDict):
    query: str
    chunks: list
    answer: str
    is_medical: bool
    confidence: float
    retry_count: int


def guardrail_decision(state):
    if state["is_medical"]:
        return "navigator"
    else:
        return "reject"


def judge_decision(state):
    confidence = state["confidence"]
    retry_count = state["retry_count"]

    if confidence >= 0.7:
        return "end"
    elif retry_count >= 3:
        print("max retries reached - best available answer returned")
        return "end"
    else:
        print(f"Retry {retry_count} - Refine answer")
        return "retry"


def build_aria():
    graph = StateGraph(AriaState)

    graph.add_node("guardrail", guardrail_node)
    graph.add_node("navigator", navigator_node)
    graph.add_node("generator", generator_node)
    graph.add_node("judge", judge_node)
    graph.add_node("reject", reject_node)

    graph.add_edge(START, "guardrail")

    graph.add_conditional_edges(
        "guardrail",
        guardrail_decision,
        {
            "navigator": "navigator",
            "reject": "reject"
        }
    )

    graph.add_edge("navigator", "generator")
    graph.add_edge("generator", "judge")
    graph.add_edge("reject", END)

    graph.add_conditional_edges(
        "judge",
        judge_decision,
        {
            "retry": "generator",
            "end": END
        }
    )

    app = graph.compile()
    return app


def ask_aria(question: str):
    app = build_aria()

    initial_state = {
        "query": question,
        "is_medical": False,
        "chunks": [],
        "answer": "",
        "confidence": 0.0,
        "retry_count": 0
    }

    final_state = app.invoke(initial_state)
    return final_state["answer"]


if __name__ == "__main__":
    print("="*60)
    print("TEST 1: Medical Query")
    print("="*60)
    answer = ask_aria("What is the treatment for hypertension?")
    print("\n" + "="*60)
    print("FINAL ANSWER:")
    print("="*60)
    print(answer)

    print("\n\n" + "="*60)
    print("TEST 2: Non-Medical Query")
    print("="*60)
    answer = ask_aria("What is the price of Bitcoin?")
    print("\n" + "="*60)
    print("FINAL ANSWER:")
    print("="*60)
    print(answer)