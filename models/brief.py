from pydantic import BaseModel

class Brief(BaseModel):
    id: str
    opening_id: int
    opening_title: str
    content: str
    conclusion: str
    file: str
