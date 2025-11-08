from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import tempfile
import os
import sys
from typing import Optional
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import sample
from prompt import PROMPT

app = FastAPI(title="Video Analysis API", description="Analyze video frames with OpenAI Vision API")

@app.get("/")
async def root():
    return {"message": "Video Analysis API is running", "endpoint": "/analyze"}

@app.post("/analyze")
async def analyze_video(
    file: UploadFile = File(...),
    max_workers: Optional[int] = 5
):
    """
    Analyze a video file frame by frame using OpenAI Vision API.
    
    Args:
        file: Video file to analyze (mp4, mov, avi, etc.)
        max_workers: Number of parallel API calls (default: 5)
    
    Returns:
        JSON array with analysis results for each second
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
            
            # Process video (completely silent - suppress all output)
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                results = sample.process_video(
                    tmp_file_path,
                    prompt=PROMPT,
                    max_workers=max_workers,
                    verbose=False
                )
            
            # Extract only the parsed JSON data
            json_data_list = []
            for result in results:
                if result.get('success') and result.get('parsed_json'):
                    json_data_list.append(result['parsed_json'])
            
            # Check if all succeeded
            total_frames = len(results)
            successful = len(json_data_list)
            
            if successful == total_frames and total_frames > 0:
                return JSONResponse(
                    content={
                        "status": "success",
                        "message": "All frames analyzed successfully",
                        "total_frames": total_frames,
                        "data": json_data_list
                    }
                )
            else:
                return JSONResponse(
                    content={
                        "status": "partial_success",
                        "message": f"Processed {successful}/{total_frames} frames successfully",
                        "total_frames": total_frames,
                        "successful": successful,
                        "data": json_data_list
                    },
                    status_code=206
                )
                
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing video: {str(e)}")
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

