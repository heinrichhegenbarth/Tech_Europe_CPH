PROMPT = """
Analyze this image and return a JSON object with the following structure:

{
  "second": <integer>,
  "overall_action": "<one of: sport, sleep, food, work, leisure>",
  "sub_action": "<string>",
  "description": "<string>"
}

Rules:
- overall_action must be exactly one of: sport, sleep, food, work, leisure
- sub_action provides deeper explanation:
  * For "sport": specify the sport type (e.g., "running", "basketball", "swimming", "cycling")
  * For "sleep": use empty string ""
  * For "food": use empty string ""
  * For "work": specify "standing" or "sitting"
  * For "leisure": specify activity (e.g., "tv", "phone", "reading", "gaming", "socializing")
- description: REQUIRED FIELD - Provide a detailed description of what is happening. Be as specific as possible:
  * What is the person doing? Describe their actions in detail.
  * If eating, what exactly are they eating? (be very specific about the food, quantity, quality, size, type etc), but focus on items in the foreground.
  * Describe the scene, actions, and any notable details
  * Include context about the environment and activities
  * The description field MUST NOT be empty - always provide a meaningful description

IMPORTANT: The description field is REQUIRED and must contain a detailed description. Never leave it empty.

Return ONLY valid JSON, no additional text or explanation.
"""