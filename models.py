from pydantic import BaseModel
from typing import Optional


class Channel(BaseModel):
    name: str
    tvg_id: Optional[str] = None
    tvg_name: Optional[str] = None
    tvg_logo: Optional[str] = None
    group_title: Optional[str] = None
    url: str
    tvg_url: Optional[str] = None