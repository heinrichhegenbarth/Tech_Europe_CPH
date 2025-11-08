from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import tempfile
import os
import sys
import base64
import json
import re
import requests
from typing import Optional, Dict, Any
import sample
from prompt import PROMPT
from dotenv import load_dotenv

app = FastAPI(title="Video Analysis API", description="Analyze video frames with OpenAI Vision API")
load_dotenv()

# Dust API configuration
DUST_API_BASE = os.getenv("DUST_API_BASE", "https://dust.tt")
API_KEY = os.getenv("API_KEY")
WORKSPACE_ID = os.getenv("WORKSPACE_ID")
HEALTH_AGENT_ID = os.getenv("HEALTH_AGENT_ID")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Stockholm")

def need(var: str) -> str:
    v = os.getenv(var)
    if not v:
        raise ValueError(f"Missing required env var: {var}")
    return v

# Validate required Dust env vars
if not all([API_KEY, WORKSPACE_ID, HEALTH_AGENT_ID]):
    print("Warning: Dust API configuration incomplete. Some endpoints may not work.")

class Base64VideoRequest(BaseModel):
    video_base64: str
    file_extension: str = ".mp4"  # e.g., ".mp4", ".mov", ".avi"
    max_workers: Optional[int] = 5

def strip_code_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` fences if present."""
    if not isinstance(text, str):
        return text
    fence = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
    if fence:
        return fence[0].strip()
    return text.strip()

def extract_assistant_content(json_response: Dict[str, Any]) -> Optional[str]:
    """Find the assistant message 'content' string in Dust conversation response."""
    conv = json_response.get("conversation", {})
    content_blocks = conv.get("content", [])
    for block in content_blocks:
        if isinstance(block, list):
            for item in block:
                if isinstance(item, dict) and item.get("type") in ("agent_message", "assistant_message", None):
                    if "content" in item and isinstance(item["content"], str):
                        if item.get("rank", 0) >= 1 or item.get("type") == "agent_message":
                            return item["content"]
    for block in content_blocks:
        for item in block if isinstance(block, list) else []:
            if isinstance(item, dict) and isinstance(item.get("content"), str):
                return item["content"]
    return None

async def send_to_dust(frames_data: Dict[str, Any]) -> Dict[str, Any]:
    """Send frames data to Dust API and return parsed JSON response."""
    if not all([API_KEY, WORKSPACE_ID, HEALTH_AGENT_ID]):
        raise HTTPException(
            status_code=500,
            detail="Dust API configuration incomplete. Please set API_KEY, WORKSPACE_ID, and HEALTH_AGENT_ID environment variables."
        )
    
    print(f"[DUST] Preparing request to Dust API...")
    print(f"[DUST] Workspace ID: {WORKSPACE_ID}")
    print(f"[DUST] Health Agent ID: {HEALTH_AGENT_ID}")
    print(f"[DUST] Timezone: {TIMEZONE}")
    
    url = f"{DUST_API_BASE}/api/v1/w/{WORKSPACE_ID}/assistant/conversations"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    
    content = "INPUT_JSON:\n" + json.dumps(frames_data, ensure_ascii=False)
    print(f"[DUST] Request payload size: {len(content)} characters")
    print(f"[DUST] Number of frames: {frames_data.get('total_frames', 0)}")
    
    payload = {
        "message": {
            "content": content,
            "context": {"timezone": TIMEZONE, "username": "me", "email": None},
            "mentions": [{"configurationId": HEALTH_AGENT_ID}],
        },
        "blocking": True,
        "visibility": "unlisted",
        "title": "Video Analysis Summary"
    }
    
    try:
        print(f"[DUST] Sending POST request to: {url}")
        print(f"[DUST] Waiting for response (timeout: 180s)...")
        resp = requests.post(url, headers=headers, json=payload, timeout=180)
        resp.raise_for_status()
        print(f"[DUST] Received response with status: {resp.status_code}")
        data = resp.json()
        
        print(f"[DUST] Extracting assistant content from response...")
        assistant_text = extract_assistant_content(data)
        if not assistant_text:
            print(f"[DUST] ERROR: Could not find assistant content in response")
            raise HTTPException(
                status_code=500,
                detail="Could not find assistant content in Dust response"
            )
        
        print(f"[DUST] Assistant content length: {len(assistant_text)} characters")
        print(f"[DUST] Stripping code fences and parsing JSON...")
        # Strip code fences and parse JSON
        inner = strip_code_fences(assistant_text)
        try:
            parsed = json.loads(inner)
            print(f"[DUST] Successfully parsed JSON response")
            print(f"[DUST] Response contains keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'N/A'}")
            return parsed
        except json.JSONDecodeError as e:
            print(f"[DUST] WARNING: Response was not valid JSON: {str(e)}")
            print(f"[DUST] Returning raw response")
            # If not valid JSON, return the raw text wrapped in a response
            return {
                "raw_response": assistant_text,
                "note": "Dust response was not valid JSON"
            }
    except requests.exceptions.RequestException as e:
        print(f"[DUST] ERROR: Request failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error calling Dust API: {str(e)}"
        )

@app.get("/")
async def root():
    return {
        "message": "Video Analysis API is running",
        "endpoints": {
            "/analyze": "Upload video file (multipart/form-data)",
            "/analyze/base64": "Send base64 encoded video (JSON)"
        }
    }

@app.post("/analyze")
async def analyze_video(
    file: UploadFile = File(...),
    max_workers: Optional[int] = 5
):
    """
    Analyze a video file frame by frame using OpenAI Vision API, then send results to Dust API.
    
    Args:
        file: Video file to analyze (mp4, mov, avi, etc.)
        max_workers: Number of parallel API calls (default: 5)
    
    Returns:
        JSON response from Dust API (health analysis, tips, etc.)
    """
    # Validate file type
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in sample.SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {file_ext}. Supported: {', '.join(sample.SUPPORTED_FORMATS)}"
        )
    
    # Save uploaded file to temporary location
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
        try:
            # Write uploaded file to temp file
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
            
            # Process video with verbose output
            print(f"\n[API] Starting video analysis for file: {file.filename}")
            print(f"[API] Using {max_workers} parallel workers")
            results = sample.process_video(
                tmp_file_path,
                prompt=PROMPT,
                max_workers=max_workers,
                verbose=True
            )
            
            # Extract only the parsed JSON data
            print(f"\n[API] Extracting parsed JSON data from results...")
            json_data_list = []
            for result in results:
                if result.get('success') and result.get('parsed_json'):
                    json_data_list.append(result['parsed_json'])
            
            # Check if all succeeded
            total_frames = len(results)
            successful = len(json_data_list)
            print(f"[API] Successfully parsed {successful}/{total_frames} frames")
            
            # Format data for Dust API
            print(f"\n[API] Formatting data for Dust API...")
            frames_object = {
                "status": "success" if successful == total_frames else "partial_success",
                "message": "All frames analyzed successfully" if successful == total_frames else f"Processed {successful}/{total_frames} frames successfully",
                "total_frames": total_frames,
                "data": json_data_list
            }
            
            # Send to Dust API and return its response
            print(f"[API] Sending {total_frames} frames to Dust API...")
            dust_response = await send_to_dust(frames_object)
            print(f"[API] Received response from Dust API")
            print(f"[API] Response keys: {list(dust_response.keys()) if isinstance(dust_response, dict) else 'N/A'}")
            return JSONResponse(content=dust_response)
                
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing video: {str(e)}")
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

@app.post("/analyze/base64")
async def analyze_video_base64(request: Base64VideoRequest):
    """
    Analyze a base64 encoded video file frame by frame using OpenAI Vision API, then send results to Dust API.
    
    Args:
        request: JSON body with:
            - video_base64: Base64 encoded video string
            - file_extension: File extension (e.g., ".mp4", ".mov", ".avi") - default: ".mp4"
            - max_workers: Number of parallel API calls (default: 5)
    
    Returns:
        JSON response from Dust API (health analysis, tips, etc.)
    """
    # Validate file extension
    file_ext = request.file_extension.lower()
    if not file_ext.startswith('.'):
        file_ext = '.' + file_ext
    
    if file_ext not in sample.SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {file_ext}. Supported: {', '.join(sample.SUPPORTED_FORMATS)}"
        )
    
    # Decode base64 video
    try:
        video_bytes = base64.b64decode(request.video_base64)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid base64 encoding: {str(e)}"
        )
    
    # Save decoded video to temporary location
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
        tmp_file_path = None
        try:
            tmp_file.write(video_bytes)
            tmp_file_path = tmp_file.name
            
            # Process video with verbose output
            print(f"\n[API] Starting video analysis for base64 encoded video")
            print(f"[API] File extension: {file_ext}")
            print(f"[API] Using {request.max_workers} parallel workers")
            results = sample.process_video(
                tmp_file_path,
                prompt=PROMPT,
                max_workers=request.max_workers,
                verbose=True
            )
            
            # Extract only the parsed JSON data
            print(f"\n[API] Extracting parsed JSON data from results...")
            json_data_list = []
            for result in results:
                if result.get('success') and result.get('parsed_json'):
                    json_data_list.append(result['parsed_json'])
            
            # Check if all succeeded
            total_frames = len(results)
            successful = len(json_data_list)
            print(f"[API] Successfully parsed {successful}/{total_frames} frames")
            
            # Format data for Dust API
            print(f"\n[API] Formatting data for Dust API...")
            frames_object = {
                "status": "success" if successful == total_frames else "partial_success",
                "message": "All frames analyzed successfully" if successful == total_frames else f"Processed {successful}/{total_frames} frames successfully",
                "total_frames": total_frames,
                "data": json_data_list
            }
            
            # Send to Dust API and return its response
            print(f"[API] Sending {total_frames} frames to Dust API...")
            dust_response = await send_to_dust(frames_object)
            print(f"[API] Received response from Dust API")
            print(f"[API] Response keys: {list(dust_response.keys()) if isinstance(dust_response, dict) else 'N/A'}")
            return JSONResponse(content=dust_response)
                
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing video: {str(e)}")
        finally:
            # Clean up temporary file
            if tmp_file_path and os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

