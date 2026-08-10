from pydantic import BaseModel


class NearbyRefuge(BaseModel):
    id: str
    name: str
    type: str
    latitude: float
    longitude: float
    distance_m: float


class RefugeAddress(BaseModel):
    address: str
    latitude: float
    longitude: float
    match_distance_m: float
    source: str
