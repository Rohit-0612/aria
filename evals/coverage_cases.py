"""
Teaching-coverage cases: questions a pharmacy student asks to *learn* a
topic, each with the facets a complete teaching answer covers.

The existing answer eval asks "is everything it says supported?" and is
saturated: an answer that covers half the topic still scores 0.95, because
what it leaves out is never graded. These cases grade the other side —
"did it teach the topic?" — so the change from five stitched passages to a
planned, multi-facet answer can be measured instead of asserted.

A facet is what a student must come away understanding, not a string the
answer must contain, and not a number: the grader checks that the idea is
explained, in any words. Facets are deliberately the standard teaching
outline for the topic (definition, mechanism, diagnosis, treatment and why,
monitoring, pitfalls), not a transcript of what DiPiro happens to say —
coverage is graded against what a learner needs, groundedness separately
against the sources.

The questions span the shapes people actually ask: a comparison ("X vs Y,
and how is each treated"), a treatment plan, a drug, a monitoring protocol
and a toxicology case (in scope: overdose management is core pharmacy
education).
"""

from __future__ import annotations

from typing import TypedDict


class CoverageCase(TypedDict):
    id: str
    question: str
    shape: str
    facets: list[str]


COVERAGE_CASES: list[CoverageCase] = [
    {
        "id": "prostate-local-vs-advanced",
        "shape": "comparison + treatment",
        "question": (
            "What is the difference between localized and non-localized (advanced or "
            "metastatic) prostate cancer, and how is each treated?"
        ),
        "facets": [
            "Defines localized disease (confined to the prostate) versus locally advanced and metastatic disease",
            "Explains how the stage/extent is established (e.g. PSA, Gleason/grade, imaging) or risk-stratified",
            "States the goal of therapy in each: curative intent for localized, control/survival/palliation for metastatic",
            "Covers options for localized disease: active surveillance, radical prostatectomy, radiation",
            "Explains androgen deprivation therapy (ADT) and why it works (prostate cancer growth depends on androgens)",
            "Explains castration-resistant disease and how treatment escalates (e.g. abiraterone, enzalutamide/apalutamide, docetaxel)",
            "Covers adverse effects of ADT and what to monitor (e.g. bone loss, hot flashes, metabolic/cardiovascular effects, testosterone/PSA)",
        ],
    },
    {
        "id": "diabetes-t1-vs-t2",
        "shape": "comparison + treatment",
        "question": "How do type 1 and type 2 diabetes differ, and how is each treated?",
        "facets": [
            "Explains the pathophysiology difference: autoimmune beta-cell destruction (absolute insulin deficiency) vs insulin resistance with relative deficiency",
            "Contrasts typical presentation/onset and risk of DKA",
            "States that type 1 requires insulin and describes the basal-bolus (or pump) approach",
            "Describes type 2 first-line therapy (lifestyle plus metformin) and how therapy is intensified",
            "Explains when SGLT2 inhibitors or GLP-1 receptor agonists are preferred (cardiovascular or kidney disease)",
            "Gives glycemic targets/monitoring (A1C goal, glucose monitoring)",
            "Covers hypoglycemia: which drugs cause it, recognition and treatment",
        ],
    },
    {
        "id": "seizures-focal-vs-generalized",
        "shape": "comparison + treatment",
        "question": (
            "What is the difference between focal and generalized seizures, and how does "
            "that change the choice of antiseizure medication?"
        ),
        "facets": [
            "Defines focal seizures (onset in one hemisphere/network) versus generalized (both hemispheres from onset)",
            "Names generalized seizure types (e.g. tonic-clonic, absence, myoclonic)",
            "Explains that seizure type drives drug choice",
            "Gives first-line options for focal seizures (e.g. lamotrigine, levetiracetam, carbamazepine/oxcarbazepine)",
            "Gives options for generalized seizures, including broad-spectrum agents (e.g. valproate, lamotrigine, levetiracetam) and ethosuximide for absence",
            "Explains drugs that can worsen certain generalized seizures (e.g. carbamazepine/phenytoin in absence or myoclonic)",
            "Covers key safety issues: teratogenicity (valproate), rash/SJS (lamotrigine), monitoring, drug interactions",
        ],
    },
    {
        "id": "hfref-gdmt",
        "shape": "treatment plan",
        "question": "How is heart failure with reduced ejection fraction treated, and why does each drug class help?",
        "facets": [
            "Defines HFrEF (reduced ejection fraction) and the neurohormonal activation behind it",
            "Names the guideline-directed pillars: ARNI/ACE inhibitor/ARB, evidence-based beta-blocker, MRA, SGLT2 inhibitor",
            "Explains why each pillar helps (blocks RAAS / sympathetic / aldosterone effects, mortality benefit)",
            "Explains loop diuretics are for congestion/symptoms, not mortality",
            "Describes initiation and titration (start low, titrate to target doses)",
            "Covers monitoring: potassium, renal function, blood pressure, heart rate",
            "Mentions key cautions (e.g. hyperkalemia with MRA, ACE inhibitor + ARNI washout, avoiding harmful drugs like NSAIDs)",
        ],
    },
    {
        "id": "warfarin-vs-doac-af",
        "shape": "drug comparison",
        "question": "For stroke prevention in atrial fibrillation, how do warfarin and the DOACs compare?",
        "facets": [
            "Explains why anticoagulation is needed in AF (stroke risk) and how risk is assessed (e.g. CHA2DS2-VASc)",
            "Explains the mechanism difference: vitamin K antagonist vs direct thrombin or factor Xa inhibition",
            "Covers monitoring: INR target for warfarin versus no routine INR for DOACs",
            "Covers dose adjustment for renal function for DOACs",
            "Covers interactions: many drug/food interactions with warfarin, fewer with DOACs",
            "Covers bleeding risk and reversal agents (vitamin K, idarucizumab, andexanet alfa)",
            "States situations where warfarin is still preferred (e.g. mechanical heart valves, moderate-severe mitral stenosis)",
        ],
    },
    {
        "id": "htn-first-line",
        "shape": "treatment plan",
        "question": "How should hypertension be treated initially, and what blood pressure targets are used?",
        "facets": [
            "Gives the definition/staging of hypertension and the BP target",
            "Covers lifestyle modification as part of treatment",
            "Names first-line drug classes: thiazide diuretic, ACE inhibitor, ARB, calcium channel blocker",
            "Explains how compelling indications change choice (e.g. ACEI/ARB in CKD with albuminuria or diabetes)",
            "Explains when to start with two drugs (BP well above goal)",
            "Covers monitoring and adverse effects (electrolytes, renal function, cough, edema)",
            "Mentions combinations to avoid (e.g. ACE inhibitor plus ARB)",
        ],
    },
    {
        "id": "asthma-vs-copd",
        "shape": "comparison + treatment",
        "question": "What is the difference between asthma and COPD, and how are their inhaler treatments different?",
        "facets": [
            "Contrasts pathophysiology: variable, largely reversible airway inflammation (asthma) vs progressive, largely irreversible airflow limitation (COPD)",
            "Contrasts typical patient/onset and triggers (e.g. allergy/atopy vs smoking history)",
            "Explains the role of inhaled corticosteroids as the cornerstone in asthma",
            "Explains the role of long-acting bronchodilators (LAMA/LABA) as the cornerstone in COPD",
            "Explains why LABA monotherapy is avoided in asthma",
            "Covers reliever/rescue therapy and step-up/step-down approach",
            "Covers inhaler technique/adherence and adverse effects (e.g. oral thrush with ICS)",
        ],
    },
    {
        "id": "levothyroxine",
        "shape": "drug",
        "question": "How is hypothyroidism treated with levothyroxine, and how is the dose monitored?",
        "facets": [
            "Explains hypothyroidism (low thyroid hormone, raised TSH in primary disease) and why levothyroxine replaces it",
            "Covers starting dose and the lower start in elderly or cardiac patients",
            "Explains administration: empty stomach, separate from calcium/iron/PPIs and other binders",
            "Explains monitoring with TSH and the timing (about 6-8 weeks after a change, because of the long half-life)",
            "Covers signs of over-replacement (hyperthyroid symptoms, atrial fibrillation, bone loss)",
            "Mentions special situations (e.g. dose increase in pregnancy)",
        ],
    },
    {
        "id": "acetaminophen-overdose",
        "shape": "toxicology",
        "question": "How is acetaminophen (paracetamol) overdose managed?",
        "facets": [
            "Explains the mechanism of toxicity (NAPQI accumulation when glutathione is depleted, causing hepatotoxicity)",
            "Describes the clinical course/phases (often few early symptoms, liver injury after 24-72 h)",
            "Explains risk assessment with a timed serum level and the treatment nomogram",
            "States that N-acetylcysteine is the antidote and explains how it works (replenishes glutathione)",
            "Explains timing matters (most effective within about 8-10 hours) and that it is still given late",
            "Covers decontamination (activated charcoal when early) and monitoring of liver function/INR",
            "Mentions factors that increase risk (e.g. chronic alcohol use, malnutrition)",
        ],
    },
    {
        "id": "ssri-depression",
        "shape": "drug",
        "question": "How do SSRIs treat depression, and what should a patient starting one be told?",
        "facets": [
            "Explains the mechanism (serotonin reuptake inhibition) at a basic level",
            "Explains the delayed onset of benefit (several weeks) and need for an adequate trial",
            "Covers common adverse effects (GI upset, sexual dysfunction, sleep changes)",
            "Covers serious risks: serotonin syndrome, suicidality warning in young people, bleeding risk, hyponatremia",
            "Explains continuation after response and not stopping abruptly (discontinuation syndrome, tapering)",
            "Covers key interactions (e.g. MAOIs, other serotonergic drugs, NSAIDs/anticoagulants)",
            "Explains what to do if there is no response (dose optimisation, switching or augmenting)",
        ],
    },
]
