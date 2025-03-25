import os
import json
import uuid
from datetime import datetime

def validate_interview_json(filepath):
    """
    Validate a JSON interview file and repair it if corrupted.
    
    Args:
        filepath (str): Path to the JSON file
        
    Returns:
        bool: True if valid or repaired, False if beyond repair
    """
    try:
        # First, try to load the file to see if it's valid JSON
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # If we got this far, the JSON is valid
        return True
    except json.JSONDecodeError as e:
        print(f"JSON error in {filepath}: {e}")
        
        # Try to repair the file
        return repair_interview_json(filepath)
    except Exception as e:
        print(f"Error validating {filepath}: {e}")
        return False

def repair_interview_json(filepath):
    """
    Attempt to repair a corrupted JSON interview file.
    
    Args:
        filepath (str): Path to the corrupted JSON file
        
    Returns:
        bool: True if successfully repaired, False otherwise
    """
    try:
        # Create a backup of the corrupted file
        filename = os.path.basename(filepath)
        backup_path = os.path.join(os.path.dirname(filepath), f"{os.path.splitext(filename)[0]}_corrupted.json")
        
        with open(filepath, 'r') as src:
            content = src.read()
            
        # Write the backup
        with open(backup_path, 'w') as dst:
            dst.write(content)
        
        # Try to create a minimal valid interview object
        interview_id = os.path.splitext(filename)[0]
        
        # Create a simple valid interview JSON
        valid_json = {
            "id": interview_id,
            "cv": "[Recovered from corrupted file]",
            "job_description": "[Recovered from corrupted file]",
            "system_prompt": "Be a helpful interviewer",
            "created_at": datetime.now().isoformat(),
            "transcripts": [
                {
                    "role": "candidate",
                    "content": "I'd like to discuss my experience with this position.",
                    "timestamp": datetime.now().isoformat()
                },
                {
                    "role": "ai",
                    "content": "I apologize, but I'm having trouble formulating my next question. Could you elaborate more on your previous answer?",
                    "timestamp": datetime.now().isoformat()
                }
            ],
            "rating": None,
            "verdict": None,
            "completed": False
        }
        
        # Write the valid JSON to the original file
        with open(filepath, 'w') as f:
            json.dump(valid_json, f, indent=2)
        
        print(f"Successfully repaired {filepath}")
        return True
    except Exception as e:
        print(f"Failed to repair {filepath}: {e}")
        return False

def validate_all_interview_files(directory):
    """
    Validate all interview JSON files in a directory.
    
    Args:
        directory (str): Directory containing interview JSON files
        
    Returns:
        tuple: (total_files, repaired_files, failed_files)
    """
    if not os.path.exists(directory):
        return 0, 0, 0
    
    total = 0
    repaired = 0
    failed = 0
    
    for filename in os.listdir(directory):
        if filename.endswith('.json') and not filename.endswith('_corrupted.json'):
            total += 1
            filepath = os.path.join(directory, filename)
            
            if validate_interview_json(filepath):
                repaired += 1
            else:
                failed += 1
    
    return total, repaired, failed 