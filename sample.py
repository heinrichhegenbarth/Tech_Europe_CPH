import cv2
import base64
import os
import sys
import time
import json
import re
from openai import OpenAI
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Dict, Optional
from prompt import PROMPT
import os
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Supported video formats
SUPPORTED_FORMATS = ['.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.m4v']

# Configuration
MAX_WORKERS = 5  # Number of parallel API calls

def extract_frames(video_path, fps=1, verbose=True):
    """
    Extract frames from video at specified frames per second.
    Returns a list of (frame_number, frame_image) tuples.
    """
    if verbose:
        print(f"[INFO] Opening video file: {video_path}")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Error opening video file: {video_path}")
    
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / video_fps if video_fps > 0 else 0
    frame_interval = int(video_fps / fps) if video_fps > 0 else 1  # Calculate frame interval
    
    if verbose:
        print(f"[INFO] Video properties:")
        print(f"  - FPS: {video_fps:.2f}")
        print(f"  - Total frames: {total_frames}")
        print(f"  - Duration: {duration:.2f} seconds")
        print(f"  - Frame extraction interval: {frame_interval} frames (1 frame per second)")
    
    frames = []
    frame_count = 0
    extracted_count = 0
    
    if verbose:
        print(f"[INFO] Extracting frames...")
        pbar = tqdm(total=total_frames, desc="Extracting frames", unit="frame")
    else:
        pbar = None
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Extract frame at 1 second intervals
            if frame_count % frame_interval == 0:
                frames.append((extracted_count, frame))
                extracted_count += 1
                if verbose and pbar:
                    pbar.set_postfix({"extracted": extracted_count})
            
            frame_count += 1
            if pbar:
                pbar.update(1)
    finally:
        if pbar:
            pbar.close()
    
    cap.release()
    if verbose:
        print(f"[INFO] Successfully extracted {len(frames)} frames")
    return frames, video_fps

def encode_frame_to_base64(frame):
    """
    Encode OpenCV frame (numpy array) to base64 string.
    """
    # Encode frame to JPEG
    _, buffer = cv2.imencode('.jpg', frame)
    
    # Convert to base64
    frame_base64 = base64.b64encode(buffer).decode('utf-8')
    size_kb = len(frame_base64) / 1024
    return frame_base64, size_kb

def parse_json_from_response(text: str) -> Optional[Dict]:
    """
    Extract and parse JSON from the API response.
    Handles cases where JSON might be wrapped in markdown code blocks or have extra text.
    """
    if not text:
        return None
    
    # Try to find JSON in markdown code blocks
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        text = json_match.group(1)
    else:
        # Try to find JSON object directly
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            text = json_match.group(0)
    
    try:
        parsed = json.loads(text)
        return parsed
    except json.JSONDecodeError:
        return None

def validate_json_structure(data: Dict, second: int) -> Dict:
    """
    Validate and ensure the JSON has the required structure.
    """
    valid_actions = ['sport', 'sleep', 'food', 'work', 'leisure']
    
    # Accept both "description" and "short_description" field names (for backward compatibility)
    description = data.get('description') or data.get('short_description') or ''
    
    result = {
        'second': second,
        'overall_action': data.get('overall_action', 'unknown'),
        'sub_action': data.get('sub_action', ''),
        'description': description  # Use "description" to match the prompt
    }
    
    # Validate overall_action
    if result['overall_action'] not in valid_actions:
        result['overall_action'] = 'unknown'
    
    # Ensure sub_action is a string
    if not isinstance(result['sub_action'], str):
        result['sub_action'] = str(result['sub_action']) if result['sub_action'] else ''
    
    # Ensure description is a string and not empty
    if not isinstance(result['description'], str):
        result['description'] = str(result['description']) if result['description'] else ''
    
    # If description is empty, this is an error - but we'll let it through and the prompt should handle it
    if not result['description'].strip():
        # Log a warning but don't fail - the prompt should enforce this
        pass
    
    return result

def analyze_frame_with_openai(args):
    """
    Call OpenAI Vision API to analyze a frame.
    Args: tuple of (client, frame_base64, prompt, second, frame_index)
    """
    client, frame_base64, prompt, second, frame_index = args
    start_time = time.time()
    
    # Inject the second number into the prompt
    prompt_with_second = prompt.replace("<integer>", str(second)) if "<integer>" in prompt else f"{prompt}\n\nNote: This frame is from second {second} of the video. Include this second number in your JSON response."
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt_with_second
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{frame_base64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000  # Increased for more detailed descriptions
        )
        elapsed = time.time() - start_time
        analysis_text = response.choices[0].message.content
        tokens_used = None
        if hasattr(response, 'usage') and response.usage:
            tokens_used = response.usage.total_tokens
        
        # Parse JSON from response
        parsed_json = parse_json_from_response(analysis_text)
        
        if parsed_json:
            validated_json = validate_json_structure(parsed_json, second)
            return {
                'second': second,
                'frame_index': frame_index,
                'analysis': analysis_text,
                'parsed_json': validated_json,
                'success': True,
                'elapsed_time': elapsed,
                'tokens_used': tokens_used
            }
        else:
            # If JSON parsing failed, return error
            return {
                'second': second,
                'frame_index': frame_index,
                'analysis': analysis_text,
                'parsed_json': None,
                'success': False,
                'elapsed_time': elapsed,
                'error': 'Failed to parse JSON from response',
                'tokens_used': tokens_used
            }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            'second': second,
            'frame_index': frame_index,
            'analysis': f"Error analyzing frame: {str(e)}",
            'parsed_json': None,
            'success': False,
            'elapsed_time': elapsed,
            'error': str(e)
        }

def is_supported_video_format(file_path):
    """
    Check if the video file format is supported.
    """
    _, ext = os.path.splitext(file_path.lower())
    return ext in SUPPORTED_FORMATS

def save_json_results(results: List[Dict], video_path: str, output_dir: str = "output"):
    """
    Save all results as a single JSON file.
    Creates output directory if it doesn't exist.
    """
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Get base name of video file (without extension)
    video_basename = os.path.splitext(os.path.basename(video_path))[0]
    
    # Collect all parsed JSON data
    json_data_list = []
    for result in results:
        if result.get('success') and result.get('parsed_json'):
            json_data_list.append(result['parsed_json'])
    
    # Create filename: video_name.json
    filename = f"{video_basename}.json"
    filepath = os.path.join(output_dir, filename)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(json_data_list, f, indent=2, ensure_ascii=False)
        return len(json_data_list), output_dir, filepath
    except Exception as e:
        print(f"[WARNING] Failed to save {filename}: {e}")
        return 0, output_dir, None

def process_video(video_path, prompt="What is happening in this image? Describe the scene, actions, and any notable details.", max_workers=MAX_WORKERS, verbose=True):
    """
    Main function to process video: extract frames and analyze with OpenAI.
    """
    start_time = time.time()
    
    if verbose:
        print("="*60)
        print("VIDEO ANALYSIS WITH OPENAI VISION API")
        print("="*60)
    
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")
    
    if verbose:
        file_size = os.path.getsize(video_path) / (1024 * 1024)  # Size in MB
        print(f"[INFO] Video file size: {file_size:.2f} MB")
    
    if not is_supported_video_format(video_path):
        if verbose:
            _, ext = os.path.splitext(video_path)
            print(f"[WARNING] {ext} is not in the list of commonly supported formats.")
            print(f"[INFO] Supported formats: {', '.join(SUPPORTED_FORMATS)}")
            print("[INFO] Attempting to process anyway...\n")
    
    if verbose:
        print(f"[INFO] Processing video: {video_path}")
        print(f"[INFO] Prompt: {prompt}")
        print(f"[INFO] Using {max_workers} parallel workers for API calls\n")
    
    # Extract frames
    frames, video_fps = extract_frames(video_path, fps=1, verbose=verbose)
    if verbose:
        print(f"\n[INFO] Extracted {len(frames)} frames from video (FPS: {video_fps:.2f})\n")
    
    # Initialize OpenAI client
    if verbose:
        print("[INFO] Initializing OpenAI client...")
    client = OpenAI(api_key=OPENAI_API_KEY)
    if verbose:
        print("[INFO] OpenAI client initialized\n")
    
    # Encode all frames to base64
    if verbose:
        print("[INFO] Encoding frames to base64...")
    encoded_frames = []
    total_size = 0
    pbar = tqdm(total=len(frames), desc="Encoding frames", unit="frame", disable=not verbose)
    for second, frame in frames:
        frame_base64, size_kb = encode_frame_to_base64(frame)
        encoded_frames.append((second, frame_base64, size_kb))
        total_size += size_kb
        pbar.update(1)
    pbar.close()
    
    if verbose:
        print(f"[INFO] Encoded {len(encoded_frames)} frames (Total size: {total_size:.2f} KB)\n")
    
    # Prepare arguments for parallel processing
    if verbose:
        print(f"[INFO] Preparing {len(encoded_frames)} API calls...")
    api_args = [
        (client, frame_base64, prompt, second, idx)
        for idx, (second, frame_base64, _) in enumerate(encoded_frames)
    ]
    
    # Process frames in parallel with progress bar
    if verbose:
        print(f"[INFO] Making parallel API calls with {max_workers} workers...")
    results = []
    successful_calls = 0
    failed_calls = 0
    total_tokens = 0
    total_api_time = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_frame = {
            executor.submit(analyze_frame_with_openai, args): args[3]  # args[3] is 'second'
            for args in api_args
        }
        
        # Process completed tasks with progress bar
        pbar = tqdm(total=len(future_to_frame), desc="Analyzing frames", unit="frame", disable=not verbose)
        try:
            for future in as_completed(future_to_frame):
                second = future_to_frame[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    if result['success']:
                        successful_calls += 1
                        if result.get('tokens_used'):
                            total_tokens += result['tokens_used']
                        total_api_time += result['elapsed_time']
                        if verbose:
                            pbar.set_postfix({
                                "success": successful_calls,
                                "failed": failed_calls,
                                "avg_time": f"{total_api_time/successful_calls:.2f}s" if successful_calls > 0 else "0s"
                            })
                    else:
                        failed_calls += 1
                        if verbose:
                            pbar.set_postfix({
                                "success": successful_calls,
                                "failed": failed_calls
                            })
                except Exception as e:
                    failed_calls += 1
                    if verbose:
                        print(f"\n[ERROR] Exception processing frame at {second}s: {e}")
                    results.append({
                        'second': second,
                        'analysis': f"Exception: {str(e)}",
                        'success': False,
                        'error': str(e)
                    })
                    if verbose:
                        pbar.set_postfix({
                            "success": successful_calls,
                            "failed": failed_calls
                        })
                
                pbar.update(1)
        finally:
            pbar.close()
    
    # Sort results by second
    results.sort(key=lambda x: x['second'])
    
    # Save JSON results locally
    if verbose:
        print(f"\n[INFO] Saving JSON results...")
    saved_count, output_dir, filepath = save_json_results(results, video_path)
    if verbose:
        if filepath:
            print(f"[INFO] Saved {saved_count} results to '{filepath}'")
        else:
            print(f"[WARNING] Failed to save JSON file")
    
    # Print summary
    if verbose:
        elapsed_total = time.time() - start_time
        print(f"\n[INFO] Processing complete!")
        print(f"  - Total time: {elapsed_total:.2f} seconds")
        print(f"  - Successful API calls: {successful_calls}/{len(results)}")
        print(f"  - Failed API calls: {failed_calls}/{len(results)}")
        print(f"  - Results saved to JSON: {saved_count}/{len(results)}")
        if successful_calls > 0:
            print(f"  - Average API call time: {total_api_time/successful_calls:.2f} seconds")
            print(f"  - Total tokens used: {total_tokens}")
            print(f"  - Estimated cost: ${total_tokens * 0.01 / 1000:.4f} (assuming $0.01 per 1K tokens)")
    # Silent mode: no output (for API usage)
    
    return results

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python sample.py <video_path> [prompt] [max_workers]")
        print("Example: python sample.py video.mp4")
        print("Example: python sample.py video.mov")
        print("Example: python sample.py video.mp4 'What is the person doing in this frame?'")
        print("Example: python sample.py video.mp4 'Describe the scene' 10")
        print(f"\nSupported formats: {', '.join(SUPPORTED_FORMATS)}")
        print(f"Default max_workers (parallel API calls): {MAX_WORKERS}")
        sys.exit(1)
    
    video_path = sys.argv[1]
    prompt = sys.argv[2] if len(sys.argv) > 2 else PROMPT
    
    try:
        # Parse max_workers if provided
        max_workers = MAX_WORKERS
        if len(sys.argv) > 3:
            try:
                max_workers = int(sys.argv[3])
                print(f"[INFO] Using {max_workers} parallel workers (from command line)")
            except ValueError:
                print(f"[WARNING] Invalid max_workers value, using default: {MAX_WORKERS}")
        
        results = process_video(video_path, prompt, max_workers=max_workers)
        
        print("\n" + "="*60)
        print("ANALYSIS SUMMARY")
        print("="*60)
        for result in results:
            status = "✓" if result.get('success', False) else "✗"
            print(f"\n[{status}] Second {result['second']}:")
            if result.get('elapsed_time'):
                print(f"  (API call took {result['elapsed_time']:.2f}s)")
            if result.get('tokens_used'):
                print(f"  (Tokens used: {result['tokens_used']})")
            
            # Display parsed JSON if available
            if result.get('parsed_json'):
                json_data = result['parsed_json']
                print(f"  Overall Action: {json_data['overall_action']}")
                if json_data['sub_action']:
                    print(f"  Sub Action: {json_data['sub_action']}")
                print(f"  Description: {json_data.get('description', json_data.get('short_description', ''))}")
            else:
                print(f"  Raw response: {result.get('analysis', 'N/A')}")
                if result.get('error'):
                    print(f"  Error: {result['error']}")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
