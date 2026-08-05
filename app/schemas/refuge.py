from pydantic import BaseModel


class Refuge(BaseModel):
    id: str
    name: str
    type: str
    distance_m: float
    latitude: float
    longitude: float
    address: str
