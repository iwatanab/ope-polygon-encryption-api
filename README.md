# Encrypted GeoJSON API with FastAPI

This project provides an API built with FastAPI that processes GeoJSON polygons, encrypts the polygon coordinates using the Bolyreva Order-Preserving Encryption (OPE) scheme, and returns the encrypted data. The primary benefit of OPE is that it preserves the relative order of encrypted values without revealing actual distances, allowing for secure computations, such as overlap detection, without disclosing the exact locations of the polygons.

## Features

- **Order-Preserving Encryption**: Uses the Bolyreva OPE scheme to encrypt polygon coordinates while preserving their relative order.
- **GeoJSON Processing**: Handles GeoJSON data, ensuring correct polygon winding orders and performing polygon simplifications.
- **Geospatial Metadata**:
  - Calculates the area of the polygon in hectares.
  - Computes the centroid of the polygon.
  - Determines the H3 index for the centroid.
  - Retrieves the country where the centroid is located.
- **Polygon Shrinking**: Shrinks the polygon edges by 10 meters before simplification and encryption.
