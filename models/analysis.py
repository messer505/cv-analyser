from pydantic import BaseModel
from typing import List

class Analysis(BaseModel):
    id: str
    opening_id: int
    opening_title: str
    opening_folder: str
    brief_id: str
    title: str
    soft_skills: List[str]
    hard_skills: List[str]
    local: str
    nivel: str
    disponibilidade: str
    score: float
    
