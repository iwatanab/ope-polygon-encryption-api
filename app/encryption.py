# app/encryption.py

import os
import base64
from pyope.ope import OPE, ValueRange
from typing import List, Tuple
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class EncryptedPoint:
    def __init__(self,  lon: int,lat: int):
        self.lon = lon
        self.lat = lat

class EncryptedPolygon:
    def __init__(self, points: List[EncryptedPoint]):
        if not 4 <= len(points) <= 50:
            raise ValueError("Polygon must have between 4 and 50 points")
        self.points = points

def setup_ope(key: str, in_range: ValueRange) -> OPE:
    """Set up the OPE cipher with a given key and input range."""
    if not key:
        raise ValueError("OPE key is not set or could not be retrieved from the environment variables.")
    key_bytes = base64.b64decode(key)
    out_range = ValueRange(0, 2**256 - 1)
    return OPE(key_bytes, in_range, out_range)

# Get keys from environment variables
key_lon = os.getenv("OPE_KEY_LON")
key_lat = os.getenv("OPE_KEY_LAT")

# Initialize the OPE ciphers for latitude and longitude using static keys
cipher_lon = setup_ope(key_lon, ValueRange(0, 360000000))
cipher_lat = setup_ope(key_lat, ValueRange(0, 180000000))


def encrypt_lon(value: float) -> int:
    """Encrypt longitude value."""
    transformed_lon = int((value + 180) * 1000000)
    print(f'Transformed Lon: {transformed_lon}')
    print(f"Encrypting longitude {value} -> {transformed_lon}")
    if not (0 <= transformed_lon <= 360000000):
        raise ValueError("Transformed longitude is out of the input range.")
    print(f'encrypted lon: {cipher_lat.encrypt(transformed_lon)}')
    return cipher_lon.encrypt(transformed_lon)

def encrypt_lat(value: float) -> int:
    """Encrypt latitude value."""
    transformed_lat = int((value + 90) * 1000000)
    print(f'Transformed Lat: {transformed_lat}')
    print(f"Encrypting latitude {value} -> {transformed_lat}")
    if not (0 <= transformed_lat <= 180000000):
        raise ValueError("Transformed latitude is out of the input range.")
    print(f'encrypted lat: {cipher_lat.encrypt(transformed_lat)}')
    return cipher_lat.encrypt(transformed_lat)

def create_encrypted_polygon(coordinates: List[Tuple[float, float]]) -> EncryptedPolygon:
    """Create an encrypted polygon from a list of coordinates."""
    # GeoJSON order: [longitude, latitude]
    print(coordinates)
    return EncryptedPolygon([EncryptedPoint(encrypt_lon(lon), encrypt_lat(lat)) for lon, lat in coordinates])
