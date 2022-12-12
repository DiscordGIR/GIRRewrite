from pydantic import BaseModel

class FilterWord(BaseModel):
    notify: bool
    bypass: int
    word: str
    false_positive: bool = False
    piracy: bool = False