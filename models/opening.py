from pydantic import BaseModel
from typing import List

class Opening(BaseModel):
    folder: str
    id: int
    title: str
    intro: str
    main_activities: str
    add_infos: str
    pre_requisites: str
    soft_skills: List[str]
    hard_skills: List[str]
    nivel: str
    local: str
    disponibilidade: str