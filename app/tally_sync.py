import os
import uuid
import requests
import copy
import sys
from dotenv import dotenv_values

# Explicitly load .env file from the project root (one level up from app/)
basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
env_path = os.path.join(basedir, '.env')

# Load config from .env file directly
config = {}
print(f"DEBUG: Looking for .env at {env_path}", file=sys.stderr)
if os.path.exists(env_path):
    print("DEBUG: .env file found.", file=sys.stderr)
    config = dotenv_values(env_path)
    print(f"DEBUG: Loaded keys: {list(config.keys())}", file=sys.stderr)
else:
    print("DEBUG: .env file NOT found.", file=sys.stderr)

BASE_URL = "https://api.tally.so"

# Mapping from Excel 'Group' to Form 'TITLE' block text (partial match)
CATEGORY_MAPPING = {
    "Prepared Speakers": "Best Prepared Speaker",
    "Individual Evaluators": "Best Evaluator",
    "Table Topics Speakers": "Best Table Topics Speaker",
    "Role Takers": "Best Role Taker"
}

def get_api_key():
    # Try getting from .env file first, then os.environ
    return config.get("TALLY_API_KEY") or os.environ.get("TALLY_API_KEY")

def get_form_id():
    return config.get("TALLY_FORM_ID") or os.environ.get("TALLY_FORM_ID")

def get_form_schema(api_key, form_id):
    url = f"{BASE_URL}/forms/{form_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def update_form_schema(api_key, form_id, new_blocks):
    url = f"{BASE_URL}/forms/{form_id}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {"blocks": new_blocks}
    
    response = requests.patch(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()

def generate_option_block(name, template_block, index, is_last):
    # Clone structure from an existing option block to preserve layout
    new_block = {
        "uuid": str(uuid.uuid4()),
        "type": "MULTIPLE_CHOICE_OPTION",
        "groupUuid": template_block["groupUuid"],
        "groupType": template_block["groupType"],
        "payload": copy.deepcopy(template_block["payload"])
    }
    
    # Update payload
    new_block["payload"]["text"] = name
    new_block["payload"]["index"] = index
    new_block["payload"]["isFirst"] = (index == 0)
    new_block["payload"]["isLast"] = is_last
    
    return new_block

def sync_participants_to_tally(participants_data):
    """
    participants_data: dict returned by _get_participants_dict
    Structure:
    {
        "Prepared Speakers": ["Name1", "Name2"],
        "Role Takers": [("Role1", "Name1"), ...],
        ...
    }
    """
    api_key = get_api_key()
    form_id = get_form_id()
    
    if not api_key or not form_id:
        raise ValueError(f"Missing TALLY_API_KEY or TALLY_FORM_ID. Checked .env at: {env_path}")

    # Pre-process Role Takers to be strings "Role: Name"
    flat_participants = {}
    for key, val in participants_data.items():
        if key == "Role Takers":
            # val is list of tuples (Role, Name)
            flat_participants[key] = [f"{r}: {n}" for r, n in val]
        else:
            flat_participants[key] = val

    schema = get_form_schema(api_key, form_id)
    blocks = schema["blocks"]
    
    new_blocks = []
    i = 0
    while i < len(blocks):
        block = blocks[i]
        
        # Check if this block is a TITLE that matches one of our categories
        is_target_section = False
        mapped_key = None
        
        if block["type"] == "TITLE":
            # Extract text safely
            title_text = ""
            payload = block.get("payload", {})
            if "safeHTMLSchema" in payload:
                try:
                    # extract text from nested structure if possible, or just raw text?
                    # Tally schema structure for text usually involves safeHTMLSchema
                    # But simpler check might be sufficient if we dump it?
                    # The example used safeHTMLSchema[0][0]
                    title_text = payload["safeHTMLSchema"][0][0]
                except:
                    pass
            
            # If safeHTMLSchema access failed or didn't yield text, check 'text' if it exists?
            # Or assume the example script was correct for the current form version.
            
            # Check mapping
            if title_text:
                for key, form_title in CATEGORY_MAPPING.items():
                    if form_title.lower() in title_text.lower():
                        is_target_section = True
                        mapped_key = key
                        break
        
        # Add the current title block
        new_blocks.append(block)
        i += 1
        
        if is_target_section and mapped_key:
            names_to_add = flat_participants.get(mapped_key, [])
            
            # We must sort names if they aren't already (Role Takers might be mixed otherwise)
            # But they are sorted incoming from _get_participants_dict usually.
            # Role Takers via tuples were sorted by Role.
            
            template_block = None
            
            # Skip existing options/images
            while i < len(blocks):
                next_block = blocks[i]
                b_type = next_block["type"]
                
                if b_type in ["MULTIPLE_CHOICE_OPTION", "IMAGE"]:
                    if b_type == "MULTIPLE_CHOICE_OPTION" and template_block is None:
                        template_block = next_block
                    i += 1
                else:
                    break
            
            if template_block and names_to_add:
                # Generate new blocks
                for idx, name in enumerate(names_to_add):
                    is_last = (idx == len(names_to_add) - 1)
                    new_option = generate_option_block(name, template_block, idx, is_last)
                    new_blocks.append(new_option)
                    
            elif not template_block and names_to_add:
                # Warning: No template found, cannot add options safely without structure
                # We could log this or error.
                pass
            
                # If names_to_add is empty, we effectively cleared the options, which is correct.

    update_form_schema(api_key, form_id, new_blocks)
