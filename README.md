# Video Analysis API

A FastAPI service that analyzes video frames using OpenAI Vision API.

## Installation

```bash
pip install -r requirements.txt
```

## Running the API

### Start the server:

```bash
python api.py
```

Or using uvicorn directly:

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Endpoints

### GET `/`
Health check endpoint. Returns API status.

### POST `/analyze`
Analyze a video file.

**Parameters:**
- `file` (required): Video file to upload (mp4, mov, avi, etc.)
- `max_workers` (optional): Number of parallel API calls (default: 5)

**Response:**
```json
{
  "status": "success",
  "message": "All frames analyzed successfully",
  "total_frames": 10,
  "data": [
    {
      "second": 0,
      "overall_action": "work",
      "sub_action": "sitting",
      "short_description": "..."
    },
    ...
  ]
}
```

## Usage Examples

### Using curl:

```bash
curl -X POST "http://localhost:8000/analyze?max_workers=5" \
  -F "file=@video.mp4"
```

### Using Python:

```python
import requests

url = "http://localhost:8000/analyze"
files = {"file": open("video.mp4", "rb")}
params = {"max_workers": 5}

response = requests.post(url, files=files, params=params)
result = response.json()
print(result)
```

### Using JavaScript/Fetch:

```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);

fetch('http://localhost:8000/analyze?max_workers=5', {
  method: 'POST',
  body: formData
})
.then(response => response.json())
.then(data => console.log(data));
```

## API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Supported Video Formats

- .mp4
- .mov
- .avi
- .mkv
- .flv
- .wmv
- .m4v

# Tech_Europe_CPH
