import type { AssistantMessage, PromptSeed } from './types';

/*
  Realistic ARIA responses, grounded in DiPiro's Pharmacotherapy.
  These prove the UI against real content shapes — inline [[n]] citation
  markers, multiple resolved sources, evidence tiers, agent traces, and
  safety notes — not lorem ipsum. Clinical figures are illustrative and
  consistent with standard references but must never be used for care.
*/

export const PROMPT_SEEDS: PromptSeed[] = [
  {
    id: 'seed-warfarin',
    topic: 'Anticoagulation',
    title: 'INR target & bridging in new AFib',
    query:
      'What INR target and bridging strategy should I use when starting warfarin in a patient with new non-valvular atrial fibrillation?',
  },
  {
    id: 'seed-metformin',
    topic: 'Endocrine',
    title: 'Metformin dosing in CKD',
    query:
      'Is metformin safe in chronic kidney disease, and how should I adjust the dose by eGFR?',
  },
  {
    id: 'seed-ssri',
    topic: 'Psychiatry',
    title: 'Tapering an SSRI safely',
    query: 'How do I taper a patient off sertraline to avoid discontinuation syndrome?',
  },
  {
    id: 'seed-vanco',
    topic: 'Infectious disease',
    title: 'Vancomycin AUC monitoring',
    query: 'How should vancomycin be monitored using AUC-guided dosing for MRSA bacteremia?',
  },
];

type Recipe = Omit<AssistantMessage, 'id' | 'createdAt' | 'phase' | 'agentSteps'>;

const WARFARIN: Recipe = {
  role: 'assistant',
  evidenceTier: 'strong',
  confidence: 0.91,
  content: `For **non-valvular atrial fibrillation**, the established target is an **INR of 2.0–3.0 (goal 2.5)**, which balances ischemic-stroke prevention against bleeding risk.[[1]] Below 2.0 the protective effect falls off sharply; above 3.0 intracranial hemorrhage rises without added benefit.[[1]]

Routine **bridging with heparin is not recommended** in this setting. Because AFib is a chronic, lower-acuity indication, the thromboembolic risk during warfarin initiation does not justify the bleeding risk that bridging adds.[[2]] The BRIDGE trial found no reduction in arterial thromboembolism from periprocedural bridging while major bleeding roughly tripled.[[2]]

Start warfarin at **5 mg daily** for most adults, reserving 2.5 mg for the elderly, those with heart failure, hepatic impairment, or interacting drugs.[[3]] Check the INR within 3–5 days and titrate to the therapeutic window before relying on it for stroke protection.[[3]]`,
  citations: [
    {
      id: 'w1',
      marker: 1,
      source: "DiPiro's Pharmacotherapy, 12e",
      section: 'Ch. 9 · Atrial Fibrillation',
      page: 'pp. 187–189',
      snippet:
        'For patients with nonvalvular AF, warfarin should be dosed to a target INR of 2.5 (range 2.0–3.0). INR values below 2.0 are associated with a marked increase in ischemic stroke, whereas values above 3.0 increase major bleeding without further reduction in thromboembolism.',
      relevance: 0.94,
      tier: 'strong',
    },
    {
      id: 'w2',
      marker: 2,
      source: "DiPiro's Pharmacotherapy, 12e",
      section: 'Ch. 8 · Venous Thromboembolism',
      page: 'p. 165',
      snippet:
        'Bridging anticoagulation is not routinely warranted for atrial fibrillation. The BRIDGE trial demonstrated no significant difference in arterial thromboembolism with bridging while major bleeding was significantly increased (3.2% vs 1.3%).',
      relevance: 0.89,
      tier: 'strong',
    },
    {
      id: 'w3',
      marker: 3,
      source: "DiPiro's Pharmacotherapy, 12e",
      section: 'Ch. 8 · Anticoagulant Initiation',
      page: 'pp. 158–160',
      snippet:
        'A typical warfarin initiation dose is 5 mg daily. Lower starting doses (2.5 mg) are appropriate in elderly patients, those with heart failure, hepatic dysfunction, malnutrition, or known interacting medications. INR should be assessed within 3–5 days.',
      relevance: 0.86,
      tier: 'moderate',
    },
  ],
  safety: [
    {
      kind: 'interaction',
      text: 'Warfarin has extensive CYP2C9/VKORC1 interactions. Reconcile antibiotics, amiodarone, and azoles before dosing.',
    },
    {
      kind: 'scope',
      text: 'Guidance assumes non-valvular AF. Mechanical valves and valvular AF carry different INR targets.',
    },
  ],
};

const METFORMIN: Recipe = {
  role: 'assistant',
  evidenceTier: 'moderate',
  confidence: 0.83,
  content: `Metformin is no longer contraindicated by serum creatinine alone — dosing is now governed by **eGFR**.[[1]] The thresholds are summarised below.

| eGFR (mL/min/1.73m²) | Recommendation |
|---|---|
| ≥ 45 | No adjustment; continue standard dosing [[1]] |
| 30–44 | Do not initiate; if established, continue with caution at ≈ 1000 mg/day and reassess [[1]] |
| < 30 | **Contraindicated** — discontinue [[1]] |

The concern is **lactic acidosis**, which is rare but rises as renal clearance of metformin falls.[[2]] Hold metformin before iodinated contrast or surgery in patients with eGFR < 60, and during any acute illness threatening renal perfusion (sepsis, dehydration, AKI).[[2]] Reassess renal function at least annually, or more often near a threshold.[[3]]`,
  citations: [
    {
      id: 'm1',
      marker: 1,
      source: "DiPiro's Pharmacotherapy, 12e",
      section: 'Ch. 92 · Diabetes Mellitus',
      page: 'pp. 1421–1423',
      snippet:
        'Metformin dosing is stratified by eGFR rather than serum creatinine. It is contraindicated when eGFR < 30 mL/min/1.73m². Initiation is not recommended at eGFR 30–44; patients already taking it may continue at reduced dose with monitoring.',
      relevance: 0.91,
      tier: 'moderate',
    },
    {
      id: 'm2',
      marker: 2,
      source: "DiPiro's Pharmacotherapy, 12e",
      section: 'Ch. 92 · Adverse Effects',
      page: 'p. 1430',
      snippet:
        'Metformin-associated lactic acidosis is rare but its risk increases with declining renal function. Therapy should be held prior to iodinated contrast administration and during conditions predisposing to acute kidney injury.',
      relevance: 0.85,
      tier: 'moderate',
    },
    {
      id: 'm3',
      marker: 3,
      source: "DiPiro's Pharmacotherapy, 12e",
      section: 'Ch. 92 · Monitoring',
      page: 'p. 1432',
      snippet:
        'Renal function should be evaluated before starting metformin and at least annually thereafter, with more frequent assessment in patients at risk of renal impairment or near a dosing threshold.',
      relevance: 0.8,
      tier: 'limited',
    },
  ],
  safety: [
    {
      kind: 'caution',
      text: 'Hold metformin around iodinated contrast and acute illness in patients with reduced eGFR.',
    },
  ],
};

const SSRI: Recipe = {
  role: 'assistant',
  evidenceTier: 'moderate',
  confidence: 0.74,
  content: `Sertraline should be **tapered gradually** rather than stopped abruptly to limit discontinuation syndrome — dizziness, flu-like symptoms, "brain zaps," and mood disturbance.[[1]] Risk is highest with short-half-life agents; sertraline's intermediate half-life makes it moderate.[[1]]

A reasonable schedule is to **reduce by ~25% every 1–2 weeks**, slowing further if symptoms emerge.[[2]] For a patient on 100 mg: 75 mg → 50 mg → 25 mg → stop, each step held 1–2 weeks. Patients on long-term or high-dose therapy often need a slower, longer taper.[[2]]

If discontinuation symptoms appear, **return to the last tolerated dose** and taper more slowly from there.[[3]] Distinguishing discontinuation symptoms (onset within days, resolve quickly on reinstatement) from relapse (gradual, later) is essential.[[3]]`,
  citations: [
    {
      id: 's1',
      marker: 1,
      source: "DiPiro's Pharmacotherapy, 12e",
      section: 'Ch. 81 · Major Depressive Disorder',
      page: 'pp. 1255–1257',
      snippet:
        'Abrupt discontinuation of SSRIs can precipitate a discontinuation syndrome characterized by dizziness, paresthesias, flu-like symptoms, and irritability. Risk correlates inversely with elimination half-life; agents such as paroxetine carry higher risk than fluoxetine.',
      relevance: 0.88,
      tier: 'moderate',
    },
    {
      id: 's2',
      marker: 2,
      source: "DiPiro's Pharmacotherapy, 12e",
      section: 'Ch. 81 · Treatment Discontinuation',
      page: 'p. 1260',
      snippet:
        'When discontinuing, doses should be tapered over several weeks. A common approach reduces the dose by approximately 25% at 1- to 2-week intervals, with slower tapering for patients on long-term therapy.',
      relevance: 0.82,
      tier: 'moderate',
    },
    {
      id: 's3',
      marker: 3,
      source: "DiPiro's Pharmacotherapy, 12e",
      section: 'Ch. 81 · Clinical Pearls',
      page: 'p. 1261',
      snippet:
        'If discontinuation symptoms occur, reinstating the previous dose typically resolves them within 24–48 hours, which also helps differentiate discontinuation symptoms from depressive relapse.',
      relevance: 0.77,
      tier: 'limited',
    },
  ],
  safety: [
    {
      kind: 'caution',
      text: 'Assess for relapse risk before discontinuing. Tapering is individualized; psychiatric input is advised for recurrent depression.',
    },
  ],
};

const VANCO: Recipe = {
  role: 'assistant',
  evidenceTier: 'strong',
  confidence: 0.88,
  content: `For serious MRSA infections including bacteremia, current consensus guidelines recommend **AUC-guided dosing** targeting an **AUC₂₄/MIC of 400–600 mg·h/L** (assuming MIC ≤ 1 mg/L by broth microdilution).[[1]] This has replaced trough-only monitoring, which over-exposed patients and drove nephrotoxicity.[[1]]

Estimate AUC either by **Bayesian software** from one or two levels, or by **first-order equations using a peak and trough**.[[2]] Bayesian methods allow earlier estimation, often from a single post-distribution level within the first 24–48 hours.[[2]]

Keep AUC **below 600** to limit acute kidney injury, and monitor renal function at least every 2–3 days during therapy — more often in unstable patients or with concurrent nephrotoxins.[[3]]`,
  citations: [
    {
      id: 'v1',
      marker: 1,
      source: "DiPiro's Pharmacotherapy, 12e",
      section: 'Ch. 130 · Antimicrobial Pharmacodynamics',
      page: 'pp. 2010–2012',
      snippet:
        'For methicillin-resistant Staphylococcus aureus infections, an AUC24/MIC ratio of 400–600 (assuming a MIC of 1 mg/L) is recommended to optimize efficacy while minimizing nephrotoxicity. Trough-based monitoring is no longer the preferred strategy.',
      relevance: 0.93,
      tier: 'strong',
    },
    {
      id: 'v2',
      marker: 2,
      source: "DiPiro's Pharmacotherapy, 12e",
      section: 'Ch. 130 · Vancomycin Monitoring',
      page: 'p. 2014',
      snippet:
        'AUC can be estimated using Bayesian dosing software from one or two concentrations, or by first-order pharmacokinetic equations using a peak and trough. Bayesian approaches permit earlier and more flexible sampling.',
      relevance: 0.87,
      tier: 'strong',
    },
    {
      id: 'v3',
      marker: 3,
      source: "DiPiro's Pharmacotherapy, 12e",
      section: 'Ch. 130 · Toxicity',
      page: 'p. 2016',
      snippet:
        'Maintaining AUC below 600 mg·h/L reduces the incidence of vancomycin-associated acute kidney injury. Renal function should be monitored at least every 48–72 hours, and more frequently with concomitant nephrotoxins.',
      relevance: 0.84,
      tier: 'moderate',
    },
  ],
  safety: [
    {
      kind: 'interaction',
      text: 'Concurrent piperacillin-tazobactam or aminoglycosides compounds nephrotoxicity — monitor renal function closely.',
    },
  ],
};

/** Returned when the guardrail classifies a query as out of scope. */
export const OUT_OF_SCOPE: Recipe = {
  role: 'assistant',
  evidenceTier: 'limited',
  confidence: 0,
  content: `That falls outside my scope. I'm **ARIA**, a clinical pharmacotherapy assistant — I can help with drug selection, dosing, monitoring, interactions, and the evidence behind therapeutic decisions, all grounded in *DiPiro's Pharmacotherapy*.

Try asking about a medication, a dosing strategy, or how to manage a specific therapeutic problem.`,
  citations: [],
  safety: [
    {
      kind: 'scope',
      text: 'ARIA answers pharmacotherapy questions only and does not provide general, legal, or non-medical advice.',
    },
  ],
};

const RECIPES: { match: RegExp; recipe: Recipe }[] = [
  { match: /warfarin|inr|bridg|anticoag|atrial|afib/i, recipe: WARFARIN },
  { match: /metformin|egfr|ckd|kidney|diabet/i, recipe: METFORMIN },
  { match: /sertraline|ssri|taper|discontinu|antidepress/i, recipe: SSRI },
  { match: /vanco|auc|mrsa|trough|bacteremia/i, recipe: VANCO },
];

/** Pick the best-matching mock answer; default to a general medical response. */
export function recipeFor(query: string): Recipe {
  const medical =
    /\b(drug|dose|dosing|mg|patient|therapy|treat|medication|renal|hepatic|interaction|contraindicat|monitor|clinical|mcg|infection|pharmac)\b/i.test(
      query,
    );
  const hit = RECIPES.find((r) => r.match.test(query));
  if (hit) return hit.recipe;
  if (!medical && query.trim().length > 0) return OUT_OF_SCOPE;
  // Reasonable general fallback so any medical-ish query still demos well.
  return WARFARIN;
}
