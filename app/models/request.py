from pydantic import BaseModel, HttpUrl

class MenuRequest(BaseModel):
    url: HttpUrl
