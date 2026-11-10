"""
Planner — turns a question into the outline of what a learner needs.

A single search for "how do localized and metastatic prostate cancer differ,
and how is each treated?" returns five passages about treatment and nothing
about staging, why androgen deprivation works, or what it does to bone: those
sit in other sections of the chapter, and one query never reaches them. The
teaching-coverage eval measured exactly that gap (monitoring, mechanism and
safety were the facets most often missing).

So the question is first broken into the facets a complete teaching answer
covers, each with its own search query in textbook terms. The navigator
searches every facet and keeps the best passages for each, and the generator
is handed the same outline to organise the answer around.

The planner never supplies clinical content. It names topics to look up;
everything the answer says still has to come from retrieved passages. If the
planning model is unavailable or replies with nothing usable, it degrades to
the single optimised query the navigator used before — a narrower search,
never a failed consultation.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from llm.config import Role
from llm.errors import AriaLLMError
from llm.llm_setup import invoke_role

logger = logging.getLogger(__name__)

__all__ = ["MAX_FACETS", "Facet", "plan_facets"]

#: Enough to cover definition, mechanism, treatment and safety; more spreads
#: the passage budget too thin to say anything properly about each.
MAX_FACETS = 5

PLAN_PROMPT = """You plan the research behind a teaching answer in clinical pharmacotherapy.
A pharmacy student asked the QUESTION below. List the facets a complete answer must teach so the student understands the topic, not just the bottom line — for example: definition or classification, pathophysiology or mechanism of the drugs, how it is diagnosed or staged, treatment options and why each is chosen, dosing and monitoring, adverse effects and safety, interactions, special populations.

Choose only the facets this question actually needs (between 3 and {max_facets}), most important first. The first facet is always the question's own core.
When the question asks how something is treated, one facet must be the treatment approach itself: first-line choices, how therapy is escalated, and the goals or targets of treatment. Whenever the answer involves drug therapy, two more facets are required, because students most often miss them: how the main drugs work (mechanism), and their adverse effects and monitoring.
For each facet write a short search query in textbook language (drug classes, condition names, clinical terms), without personal details.

Respond ONLY with JSON:
{{"facets": [{{"name": "<2-5 word facet>", "query": "<search query>"}}]}}

QUESTION: {question}"""


@dataclass(frozen=True)
class Facet:
    """One part of the outline: what to teach, and how to search for it."""

    name: str
    query: str


def _parse(raw: str) -> list[Facet]:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match is None:
        return []
    try:
        data: Any = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    facets: list[Facet] = []
    seen: set[str] = set()
    for item in data.get("facets", []) if isinstance(data, dict) else []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        query = str(item.get("query", "")).strip()
        if not name or not query or query.lower() in seen:
            continue
        seen.add(query.lower())
        facets.append(Facet(name=name[:60], query=query[:200]))
    return facets[:MAX_FACETS]


def plan_facets(question: str) -> list[Facet]:
    """The outline for `question`, or [] when no usable plan was produced.

    An empty list is the caller's cue to fall back to a single search; it is
    never an error, because planning only shapes retrieval.
    """
    prompt = PLAN_PROMPT.format(question=question, max_facets=MAX_FACETS)
    try:
        facets = _parse(invoke_role(Role.NAVIGATOR, prompt, json_mode=True))
    except AriaLLMError as exc:
        logger.warning(
            "Planner unavailable (%s) — falling back to one search", exc.code or "provider error"
        )
        return []
    if len(facets) < 2:
        logger.warning("Planner returned %d facet(s) — falling back to one search", len(facets))
        return []
    logger.info("plan: %s", " | ".join(f"{f.name} -> {f.query}" for f in facets))
    return facets
