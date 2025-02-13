import os
import re
import logging
from typing import Optional
from pathlib import Path
import aiohttp
import boto3
from botocore.exceptions import ClientError
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, JSONResponse
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO

# Load environment variables
load_dotenv()

# Validate required environment variables
required_env_vars = ['R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_BUCKET_NAME']
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="MLS Image Proxy",
    description="Proxy service for MLS images"
)

# Add middleware to handle favicon and apple-touch-icon requests
@app.middleware("http")
async def handle_favicon(request: Request, call_next):
    if request.url.path in ["/favicon.ico", "/apple-touch-icon.png", "/apple-touch-icon-precomposed.png"]:
        return Response(status_code=204)  # No content
    return await call_next(request)

# Configure R2 client
r2 = boto3.client(
    's3',
    endpoint_url=f"https://{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
    aws_access_key_id=os.getenv('R2_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('R2_SECRET_ACCESS_KEY'),
    region_name='auto'
)

BUCKET_NAME = os.getenv('R2_BUCKET_NAME')
MLS_BASE_URL = "http://images.realtyserver.com/photo_server.php"

# Validate image name
def normalize_image_name(image_name: str) -> str:
    """Remove .jpg extension if present."""
    if image_name.lower().endswith('.jpg'):
        return image_name[:-4]
    return image_name

def is_valid_image_name(image_name: str) -> bool:
    """Check if the image name is valid and safe."""
    # First normalize by removing .jpg if present
    base_name = normalize_image_name(image_name)
    return bool(re.match(r'^[0-9A-F]+\.L\d+$', base_name, re.IGNORECASE))

def get_storage_key(image_name: str) -> str:
    """Convert MLS image name to storage key with .jpg extension."""
    base_name = normalize_image_name(image_name)
    return f"{base_name}.jpg"

async def fetch_image_from_mls(image_name: str) -> Optional[bytes]:
    """Fetch image from MLS server."""
    base_name = normalize_image_name(image_name)
    params = {
        'btnSubmit': 'GetPhoto',
        'board': 'panama',
        'name': base_name
    }
    
    logger.info(f"Fetching image from MLS: {base_name}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(MLS_BASE_URL, params=params) as response:
                if response.status != 200:
                    logger.error(f"MLS server returned status {response.status} for image {base_name}")
                    return None
                content_type = response.headers.get('content-type', '')
                if not content_type.startswith('image/'):
                    logger.error(f"MLS server returned non-image content type: {content_type}")
                    return None
                return await response.read()
    except Exception as e:
        logger.error(f"Error fetching image from MLS: {str(e)}")
        return None

@app.get("/mls-images/{image_name}")
async def get_image(image_name: str):
    """Main endpoint to serve images."""
    
    logger.info(f"Received request for image: {image_name}")
    
    # Validate image name
    if not is_valid_image_name(image_name):
        logger.warning(f"Invalid image name format: {image_name}")
        raise HTTPException(status_code=400, detail="Invalid image name format")
    
    try:
        storage_key = get_storage_key(image_name)
        logger.debug(f"Storage key: {storage_key}")
        
        # Try to get image from R2
        try:
            logger.info(f"Attempting to fetch from R2: {storage_key}")
            r2_response = r2.get_object(Bucket=BUCKET_NAME, Key=storage_key)
            image_data = r2_response['Body'].read()
            logger.info(f"Successfully retrieved image from R2: {storage_key}")
            content_type = 'image/jpeg'
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.info(f"Image not found in R2, fetching from MLS: {image_name}")
                # Image not in R2, fetch from MLS
                image_data = await fetch_image_from_mls(image_name)
                
                if not image_data:
                    logger.error(f"Failed to fetch image from MLS: {image_name}")
                    raise HTTPException(status_code=404, detail="Image not found or invalid response from MLS")
                
                # Validate image data
                try:
                    img = Image.open(BytesIO(image_data))
                    if img.format.lower() != 'jpeg':
                        logger.warning(f"Non-JPEG image received: {img.format}")
                    content_type = 'image/jpeg'
                except Exception as e:
                    logger.error(f"Invalid image data received: {str(e)}")
                    raise HTTPException(status_code=400, detail="Invalid image data received from MLS")
                
                # Store in R2 with .jpg extension
                try:
                    logger.info(f"Storing image in R2: {storage_key}")
                    r2.put_object(
                        Bucket=BUCKET_NAME,
                        Key=storage_key,
                        Body=image_data,
                        ContentType=content_type
                    )
                    logger.info(f"Successfully stored image in R2: {storage_key}")
                except Exception as e:
                    logger.error(f"Failed to store image in R2: {str(e)}")
                    # Continue serving the image even if caching fails
            else:
                logger.error(f"R2 error: {str(e)}")
                raise HTTPException(status_code=500, detail="Storage error")
        
        # Serve the image
        headers = {
            'Cache-Control': 'public, max-age=31536000',  # Cache for 1 year
            'Content-Type': content_type
        }
        return Response(content=image_data, headers=headers)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)  # Add full traceback
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return JSONResponse({"status": "healthy"})
