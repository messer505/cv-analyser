from pydantic import BaseModel

class File(BaseModel):
    file_id: str
    opening_id: int
    opening_title: str
