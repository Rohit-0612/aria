from agents.guardrail_agent import check_guardrail
from agents.navigator_agent import navigator
from agents.judge_agent import judge_answer
from llm.generator import generate_answer


def guardrail_node(state):
    print("\n GUARDRAIL CHECKING...")
    query = state["query"]
    is_medical = check_guardrail(query)
    state["is_medical"] = is_medical
    return state


def navigator_node(state):
    print("\n NAVIGATOR CHECKING...")
    query = state["query"]
    chunks = navigator(query)                   
    state["chunks"] = chunks
    return state


def generator_node(state):
    print("\n GENERATOR CHECKING...")
    query = state["query"]
    chunks = state["chunks"]
    answer = generate_answer(query, chunks)
    state["answer"] = answer
    return state


def judge_node(state):
    print("\n JUDGE NODE")
    query = state["query"]
    answer = state["answer"]
    chunks = state["chunks"]
    judgment = judge_answer(query, answer, chunks)
    state["confidence"] = judgment["confidence"]
    state["retry_count"] = state["retry_count"] + 1
    return state


def reject_node(state):
    print("\n REJECT NODE")
    state["answer"] = "I'm ARIA, a medical assistant. I can only help with medical and pharmacology questions."
    return state