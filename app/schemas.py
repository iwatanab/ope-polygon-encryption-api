# app/schemas.py

from pydantic import BaseModel
from typing import List, Dict, Any

class GeoJSONFeature(BaseModel):
    type: str
    id: str
    geometry: Dict[str, Any]
    properties: Dict[str, Any] = {}

class GeoJSONFeatureCollection(BaseModel):
    type: str
    features: List[GeoJSONFeature]
