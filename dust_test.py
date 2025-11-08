# pip install requests
import json
import re
import requests
import os
import sys
from typing import Any, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

def need(var: str) -> str:
    v = os.getenv(var)
    if not v:
        print(f"❌ Missing required env var: {var}", file=sys.stderr)
        sys.exit(1)
    return v

DUST_API_BASE   = os.getenv("DUST_API_BASE", "https://dust.tt")
API_KEY         = need("API_KEY")             # your Dust API key (bearer)
WORKSPACE_ID    = need("WORKSPACE_ID")
HEALTH_AGENT_ID = need("HEALTH_AGENT_ID")
TIMEZONE        = os.getenv("TIMEZONE", "Europe/Stockholm")

# --- Your frames JSON (exact structure you posted; shorten if you want) ---
frames_object = {
  "status": "success",
  "message": "All frames analyzed successfully",
  "total_frames": 19,
  "data": [
    {
      "second": 0,
      "overall_action": "leisure",
      "sub_action": "socializing",
      "short_description": "The image shows a modern cafe interior with natural lighting coming from skylights. People are sitting at tables, possibly engaged in conversations or socializing. The decor features wooden beams and stylish lighting fixtures, creating a cozy and inviting atmosphere. A large wooden block with dovetail joints is visible on the countertop."
    },
    {
      "second": 1,
      "overall_action": "food",
      "sub_action": "",
      "short_description": "The image shows a hand holding a croissant, suggesting someone is in the process of eating it. The setting is a modern, well-lit building with wooden beams and large windows, indicating it might be a café or a dining area. There are other people visible in the background, seated and engaged in conversation or dining activities."
    },
    {
      "second": 2,
      "overall_action": "leisure",
      "sub_action": "socializing",
      "short_description": "The image shows an indoor space with several people sitting at tables, likely a café or a restaurant. The setting features a high ceiling with wooden beams and modern lighting. From what is visible, individuals appear to be engaged in conversation and social interaction in a relaxed environment. There are decorative elements such as wooden boards on the tables and hanging lights, contributing to a cozy and casual ambiance."
    },
    {
      "second": 3,
      "overall_action": "leisure",
      "sub_action": "socializing",
      "short_description": "A person is wearing glasses and a dark hoodie, standing in what appears to be a cafe or restaurant with wooden and modern decor, including unique pendant lights. The environment is bright, with people sitting in the background, suggesting a social gathering or casual setting."
    },
    {
      "second": 4,
      "overall_action": "leisure",
      "sub_action": "socializing",
      "short_description": "The image shows the interior of a cafe or a modern wooden-structured building with high ceilings and wooden light fixtures. Several people can be seen sitting at tables in the background, likely engaged in conversation or enjoying refreshments. The environment appears relaxing and inviting, typical of a place where people gather for leisure activities such as socializing."
    },
    {
      "second": 5,
      "overall_action": "leisure",
      "sub_action": "socializing",
      "short_description": "The image shows the interior of a cafe with wooden ceilings and unique hanging lights. People are seated at tables, likely engaging in conversation and enjoying their beverages or meals. The atmosphere is relaxed and social, typical for a cafe setting."
    },
    {
      "second": 6,
      "overall_action": "work",
      "sub_action": "sitting",
      "short_description": "A person is sitting in an office environment, with laptops on the table suggesting a work setting. They appear to be in thought, resting their hand on their chin. On the table, there's a white disposable cup and a partially eaten apple core, indicating a recently had snack. The atmosphere is casual, as indicated by the beverage can and an open laptop case with what seems to be credit cards inside. The wall in the background has notes or writing, typical of a meeting or brainstorming space."
    },
    {
      "second": 7,
      "overall_action": "work",
      "sub_action": "sitting",
      "short_description": "A person is sitting at a desk in an office environment. The desk has a laptop, an apple core, a paper cup, and a soda can. Another person is visible in the background sitting with an open laptop. The wall is covered in notes and there is a window letting in natural light."
    },
    {
      "second": 8,
      "overall_action": "work",
      "sub_action": "sitting",
      "short_description": "A person is sitting at a desk with two laptops open in front of them. There is a white paper cup and a soda can on the table. The person appears to be in a casual work environment, possibly an office or a meeting room, with a whiteboard or notice board behind them. The room is lit by natural light coming through a window."
    },
    {
      "second": 9,
      "overall_action": "work",
      "sub_action": "sitting",
      "short_description": "The scene takes place in an office environment. A person is sitting at a desk with a laptop open in front of them, indicating they might be working or in a meeting. Another person, not clearly visible, is holding a partially eaten pastry in the foreground, possibly taking a snack break. A coffee cup and another laptop are also visible on the table, suggesting a casual workspace setting."
    },
    {
      "second": 10,
      "overall_action": "food",
      "sub_action": "",
      "short_description": "A person is about to eat a sandwich wrapped in brown paper. In the background, another person is sitting at a table with a laptop, and there are two cans of Coca-Cola nearby. Croissants are also visible on the table, suggesting a casual meal or snack in a meeting or office setting. The setting appears to be a workspace with whiteboard walls containing writing."
    },
    {
      "second": 11,
      "overall_action": "food",
      "sub_action": "",
      "short_description": "A person is holding a brown paper bag, possibly during lunchtime. The scene suggests that the person might be about to eat or has just purchased food. The background is somewhat blurred, but it appears to be indoors, with potential office or home setting elements visible, such as a computer monitor or windows."
    },
    {
      "second": 12,
      "overall_action": "food",
      "sub_action": "",
      "short_description": "A person is holding a wrapped sandwich or wrap, ready to eat. The wrap appears to be filled with ingredients like cheese and potentially meat, visible at the top. The environment suggests a casual setting, possibly a cafeteria or break room, as another person is visible in the background, likely seated and interacting with a device or another person. The atmosphere is relaxed and informal, indicating a break period or lunchtime."
    },
    {
      "second": 13,
      "overall_action": "food",
      "sub_action": "",
      "short_description": "A person is holding a can of Coca-Cola Zero Sugar. The background shows an office environment with a large computer monitor and ceiling lights. The time displayed is 12:39."
    },
    {
      "second": 14,
      "overall_action": "work",
      "sub_action": "standing",
      "short_description": "A person is standing in front of a large screen displaying information. They appear to be in an office or meeting room environment, possibly presenting or explaining information on the screen to an audience. The setting has a modern interior with visible lighting and ceiling design."
    },
    {
      "second": 15,
      "overall_action": "work",
      "sub_action": "standing",
      "short_description": "A person is standing in front of a large screen giving a presentation or talking to an audience. They are holding a red cup, possibly sipping a beverage. The environment appears to be an office or a meeting room with visible beams and a ceiling light that suggests an industrial or modern design."
    },
    {
      "second": 16,
      "overall_action": "leisure",
      "sub_action": "socializing",
      "short_description": "The image shows an outdoor setting near an entrance to a building. There are parked cars visible, and a person appears to be interacting with someone or gesturing with their hand, possibly during a walk or conversation. The setting includes a paved walkway and some greenery, suggesting a casual, social atmosphere outside an office or communal building."
    },
    {
      "second": 17,
      "overall_action": "leisure",
      "sub_action": "walking",
      "short_description": "The image shows an outdoor scene around mid-morning, possibly in a park or urban area with a pathway. Rocks are used for landscaping, and fallen leaves are visible, indicating autumn. A parked car and a bicycle rack can be seen in the background. The environment suggests someone might be leisurely walking or spending time outdoors."
    },
    {
      "second": 18,
      "overall_action": "work",
      "sub_action": "standing",
      "short_description": "Two people are standing near a parked car at what appears to be the entrance of a building. One of the individuals is holding a suitcase. The environment has a paved area with scattered leaves and rocks, suggesting an outdoor setting possibly during fall. The building has industrial features with a visible staircase."
    }
  ]
}

def strip_code_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` fences if present."""
    if not isinstance(text, str):
        return text
    # Match fenced blocks; keep first JSON block if present
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
                    # Dust uses agent_message objects with "content" str
                    if "content" in item and isinstance(item["content"], str):
                        # Heuristic: the assistant reply usually follows the user block
                        if item.get("rank", 0) >= 1 or item.get("type") == "agent_message":
                            return item["content"]
    # Fallback: scan all blocks for any content after user
    for block in content_blocks:
        for item in block if isinstance(block, list) else []:
            if isinstance(item, dict) and isinstance(item.get("content"), str):
                return item["content"]
    return None

def pretty_print_interesting(data: Dict[str, Any]) -> None:
    """Print the most interesting bits: score, components, risks, first 3 tips."""
    print("\n=== SUMMARY ===")
    hs = data.get("health_score", {})
    print(f"HealthScore ({hs.get('method','?')}): {hs.get('score', '?')}")

    comps = data.get("components", {})
    if comps:
        print("\nComponents:")
        for k, v in comps.items():
            print(f"  - {k}: {v}")

    risks = data.get("risk_percentages", {})
    if risks:
        print("\nRisks (%):")
        for k, v in risks.items():
            print(f"  - {k}: {v}")

    alerts = data.get("alerts", {})
    if alerts:
        print("\nAlerts:")
        print(f"  - clinician_followup: {alerts.get('clinician_followup')}")
        reasons = alerts.get("reasons", [])
        if reasons:
            for r in reasons:
                print(f"    * {r}")

    tips = data.get("tips", [])
    if tips:
        print("\nTop tips:")
        for t in tips[:3]:
            print(f"  - [{t.get('category')}] {t.get('action')}")
            how = t.get("how_to")
            if isinstance(how, list):
                for step in how[:3]:
                    print(f"      • {step}")
            elif isinstance(how, str):
                print(f"      • {how}")
            print(f"      impact={t.get('expected_impact')}, confidence={t.get('confidence')}")

def send_frames_and_print():
    url = f"{DUST_API_BASE}/api/v1/w/{WORKSPACE_ID}/assistant/conversations"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    content = "INPUT_JSON:\n" + json.dumps(frames_object, ensure_ascii=False)

    payload = {
        "message": {
            "content": content,
            "context": {"timezone": TIMEZONE, "username": "me", "email": None},
            "mentions": [{"configurationId": HEALTH_AGENT_ID}],
        },
        "blocking": True,
        "visibility": "unlisted",
        "title": "Image Analysis Summary"
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=180)
    resp.raise_for_status()
    data = resp.json()

    assistant_text = extract_assistant_content(data)
    if not assistant_text:
        print("❌ Could not find assistant 'content' in response.")
        print(json.dumps(data, indent=2))
        return

    # Strip code fences and parse JSON
    inner = strip_code_fences(assistant_text)
    try:
        parsed = json.loads(inner)
    except json.JSONDecodeError:
        print("⚠️ Assistant content is not valid JSON after stripping fences. Showing raw text:\n")
        print(assistant_text)
        return

    # Pretty-print the full JSON:
    print("=== FULL JSON (pretty) ===")
    print(json.dumps(parsed, indent=2, ensure_ascii=False))

    # Print interesting bits:
    pretty_print_interesting(parsed)

if __name__ == "__main__":
    send_frames_and_print()