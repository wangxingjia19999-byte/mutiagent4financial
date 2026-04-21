from pydantic import BaseModel


class AgentResult(BaseModel):
    success: bool = True
    message: str = ""
