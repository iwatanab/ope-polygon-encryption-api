from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from shapely.geometry import Polygon
from shapely.geometry import shape
from shapely.ops import unary_union,transform
from shapely.affinity import scale
from .schemas import GeoJSONFeatureCollection
from .encryption import create_encrypted_polygon
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
from dotenv import load_dotenv
import os
import geojson_rewind
import h3
import reverse_geocode
from pyproj import Proj, Transformer, CRS

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# CORS middleware to allow your frontend to communicate with the backend
origins = [
    "http://127.0.0.1:8000",  # Replace with your frontend URL without a trailing slash
    "https://your-frontend-domain.com",  # Replace with your actual frontend domain
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HTTPBearer will look for the "Authorization" header in incoming requests
auth_scheme = HTTPBearer()

# Retrieve the actual JWT secret from environment variables
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

# Function to verify the JWT token
def verify_jwt(credentials: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    token = credentials.credentials
    try:
        # Decode and verify the token with the expected audience
        payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"], audience="authenticated")
        return payload
    except JWTError as e:
        print(f"JWT Error: {e}")
        raise HTTPException(
            status_code=401,
            detail="Invalid token. Please ensure your token is correct and has not expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

def calculate_area_in_hectares(polygon: Polygon):
    """Calculate the area of the polygon in hectares with accurate projection handling."""
    try:
        # Define a projection to use for the transformation (WGS 84 to UTM)
        centroid = polygon.centroid
        crs_wgs84 = CRS.from_epsg(4326)  # WGS84 Latitude/Longitude
        utm_crs = CRS.from_proj4(Proj(proj='utm', zone=int((centroid.x + 180) // 6) + 1, ellps='WGS84').definition)  # UTM zone based on longitude

        # Create a transformer to convert from WGS84 to UTM
        transformer_to_utm = Transformer.from_crs(crs_wgs84, utm_crs, always_xy=True)

        # Project the polygon to UTM to get the area in square meters
        polygon_utm = transform(transformer_to_utm.transform, polygon)
        area_sqm = polygon_utm.area  # area in square meters

        # Convert the area to hectares (1 hectare = 10,000 square meters)
        area_hectares = area_sqm / 10000

        # Round the area to avoid scientific notation
        return round(area_hectares, 6)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error calculating area in hectares: {str(e)}. Ensure the polygon is valid."
        )

def get_country_from_centroid(lat: float, lng: float):
    """Get the country for the centroid using reverse geocoding."""
    location = reverse_geocode.search([(lat, lng)])
    return location[0]['country']

def shrink_polygon(polygon: Polygon, distance: float = 10):
    """
    Shrink the polygon so the new edges are 'distance' meters from the original edge.
    This function correctly handles the conversion between degrees and meters.
    """
    try:
        # Define a projection to use for the transformation (WGS 84 to UTM)
        centroid = polygon.centroid
        crs_wgs84 = CRS.from_epsg(4326)  # WGS84 Latitude/Longitude
        utm_crs = CRS.from_proj4(Proj(proj='utm', zone=int((centroid.x + 180) // 6) + 1, ellps='WGS84').definition)  # UTM zone based on longitude

        # Create a transformer to convert from WGS84 to UTM
        transformer_to_utm = Transformer.from_crs(crs_wgs84, utm_crs, always_xy=True)
        transformer_to_wgs84 = Transformer.from_crs(utm_crs, crs_wgs84, always_xy=True)

        # Project the polygon to UTM
        polygon_utm = transform(transformer_to_utm.transform, polygon)

        # Shrink the polygon by the specified distance in meters
        shrunk_polygon_utm = polygon_utm.buffer(-distance)

        # Project the shrunk polygon back to WGS84
        shrunk_polygon = transform(transformer_to_wgs84.transform, shrunk_polygon_utm)

        return shrunk_polygon
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error shrinking polygon: {str(e)}. Ensure the polygon is valid and the distance is appropriate."
        )

def simplify_polygon(coordinates, max_points=100):
    """Simplify the polygon to a maximum number of points."""
    poly = Polygon(coordinates)
    simplified_poly = poly.simplify(tolerance=0.01, preserve_topology=True)

    # Check if the simplified polygon still has more points than allowed
    while len(simplified_poly.exterior.coords) > max_points:
        tolerance = tolerance * 1.5  # Increase tolerance to simplify further
        simplified_poly = poly.simplify(tolerance, preserve_topology=True)
    
    return list(simplified_poly.exterior.coords)

def ensure_correct_winding_order(geojson):
    """Ensure the winding order of the GeoJSON polygons is correct."""
    try:
        return geojson_rewind.rewind(geojson, rfc7946=True)  # rfc7946=True ensures right-hand rule
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error ensuring correct winding order: {str(e)}. Ensure the GeoJSON data is correctly formatted."
        )

@app.post("/encrypt-polygons/")
async def encrypt_polygons(
    feature_collection: GeoJSONFeatureCollection,
    payload: dict = Depends(verify_jwt)  # Verify JWT separately
):
    try:
        # Ensure the winding order is correct
        corrected_feature_collection = ensure_correct_winding_order(feature_collection.model_dump())

        encrypted_feature_collection = {
            "type": "EncryptedFeatureCollection",
            "features": []
        }
        
        for feature in corrected_feature_collection['features']:
            if feature['geometry']['type'] != 'Polygon':
                continue
            
            coordinates = feature['geometry']['coordinates'][0]  # Assuming the first ring (outer boundary)
            poly = Polygon(coordinates)
            print(poly)
            # Step 1: Calculate the area in hectares
            area_hectares = calculate_area_in_hectares(poly)
            
            # Step 2: Calculate the centroid
            centroid = poly.centroid
            
            # Step 3: Find the H3 index at resolution 1
            h3_index = h3.geo_to_h3(centroid.y, centroid.x, 1)
            
            # Step 4: Get the country for the centroid
            country = get_country_from_centroid(centroid.y, centroid.x)
            
            # Step 5: Shrink the polygon by 10 meters
            shrunk_poly = shrink_polygon(poly, distance=10)
            print(shrunk_poly)
            # Simplify the polygon if it has more than 20 points
            if len(shrunk_poly.exterior.coords) > 20:
                coordinates = simplify_polygon(shrunk_poly.exterior.coords, max_points=20)
            else:
                coordinates = list(shrunk_poly.exterior.coords)
                print(len(coordinates))

            encrypted_feature = {
                "type": "EncryptedFeature",
                "id": "",
                "properties": {
                    "area_hectares": area_hectares,
                    "h3_index": h3_index,
                    "country": country,
                    "start_at": feature['properties']['start_at'],
                    "end_at": feature['properties']['end_at'],
                },
                "geometry": {
                    "coordinates": [
                        []
                    ],
                    "type": "Polygon"
                }
            }
            
            # Correctly pass coordinates to encryption function
            try:
                encrypted_polygon = create_encrypted_polygon(coordinates)
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error encrypting polygon: {str(e)}. Ensure the coordinates are valid."
                )

            encrypted_coords = [[point.lon, point.lat] for point in encrypted_polygon.points]
            
            # Assign values using dictionary key notation
            try:
                encrypted_feature['id'] = feature['id']
                encrypted_feature['geometry']['coordinates'][0] = [[str(coord[0]), str(coord[1])] for coord in encrypted_coords]
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error assigning encrypted coordinates: {str(e)}."
                )
            
            encrypted_feature_collection['features'].append(encrypted_feature)

        return encrypted_feature_collection
    except HTTPException as e:
        raise e  # Re-raise known HTTPExceptions
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}."
        )
