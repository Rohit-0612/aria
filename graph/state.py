from typing import TypedDict, List

class AriaState(TypedDict):
    query: str
    is_medical: str
    chunks: str 
    answer: str
    confidence: float
    retry_count: int

