import os
import json
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Any


class Interview:
    """Class representing an interview session with all related data."""
    
    def __init__(self, cv: str, job_description: str, system_prompt: str):
        self.id = str(uuid.uuid4())
        self.cv = cv
        self.job_description = job_description
        self.system_prompt = system_prompt
        self.created_at = datetime.now().isoformat()
        self.transcripts: List[Dict[str, Any]] = []
        self.evaluations: List[Dict[str, Any]] = []  # Store evaluations separately
        self.rating: Optional[int] = None
        self.verdict: Optional[str] = None
        self.completed = False
    
    def add_message(self, role: str, content: str):
        """Add a message to the transcript."""
        # If it's an evaluation, add to evaluations list instead
        if role == "evaluation":
            self.evaluations.append({
                "content": content,
                "timestamp": datetime.now().isoformat()
            })
        else:
            self.transcripts.append({
                "role": role,  # "ai" or "candidate"
                "content": content,
                "timestamp": datetime.now().isoformat()
            })
    
    def set_rating(self, rating: int, verdict: str):
        """Set the final rating and verdict for the interview."""
        self.rating = rating
        self.verdict = verdict
        self.completed = True
    
    def to_dict(self):
        """Convert instance to dictionary for storage."""
        return {
            "id": self.id,
            "cv": self.cv,
            "job_description": self.job_description,
            "system_prompt": self.system_prompt,
            "created_at": self.created_at,
            "transcripts": self.transcripts,
            "evaluations": self.evaluations,  # Include evaluations
            "rating": self.rating,
            "verdict": self.verdict,
            "completed": self.completed
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Create an instance from a dictionary."""
        interview = cls(
            cv=data["cv"],
            job_description=data["job_description"],
            system_prompt=data["system_prompt"]
        )
        interview.id = data["id"]
        interview.created_at = data["created_at"]
        interview.transcripts = data["transcripts"]
        # Handle evaluations field which might not exist in older files
        interview.evaluations = data.get("evaluations", [])
        interview.rating = data["rating"]
        interview.verdict = data["verdict"]
        interview.completed = data["completed"]
        return interview


class InterviewStorage:
    """Class for managing local storage of interviews."""
    
    def __init__(self, storage_dir: str = "interviews"):
        """Initialize storage with directory path."""
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
    
    def save_interview(self, interview: Interview):
        """Save interview to local storage."""
        filepath = os.path.join(self.storage_dir, f"{interview.id}.json")
        with open(filepath, "w") as f:
            json.dump(interview.to_dict(), f, indent=2)
        return filepath
    
    def load_interview(self, interview_id: str) -> Optional[Interview]:
        """Load interview from local storage."""
        filepath = os.path.join(self.storage_dir, f"{interview_id}.json")
        if not os.path.exists(filepath):
            return None
        
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            
            return Interview.from_dict(data)
        except json.JSONDecodeError as e:
            # Handle corrupted JSON file
            print(f"Error loading interview {interview_id}: {e}")
            
            # Attempt to repair the file by recreating it from backup or creating a new empty interview
            corrupted_path = os.path.join(self.storage_dir, f"{interview_id}_corrupted.json")
            
            # Backup the corrupted file
            try:
                with open(filepath, "r") as src, open(corrupted_path, "w") as dst:
                    dst.write(src.read())
                print(f"Backed up corrupted file to {corrupted_path}")
            except Exception as backup_error:
                print(f"Failed to backup corrupted file: {backup_error}")
            
            # Create a new empty interview as fallback
            new_interview = Interview(
                cv="[Recovered from corrupted file]",
                job_description="[Recovered from corrupted file]",
                system_prompt="Be a helpful interviewer"
            )
            new_interview.id = interview_id  # Preserve the ID
            
            # Save the recovered interview
            self.save_interview(new_interview)
            print(f"Created new interview with ID {interview_id} to replace corrupted file")
            
            return new_interview
        except Exception as e:
            print(f"Unexpected error loading interview {interview_id}: {e}")
            return None
    
    def list_interviews(self) -> List[Dict[str, Any]]:
        """List all saved interviews with basic info."""
        interviews = []
        if not os.path.exists(self.storage_dir):
            return interviews
        
        for filename in os.listdir(self.storage_dir):
            if filename.endswith(".json") and not filename.endswith("_corrupted.json"):
                filepath = os.path.join(self.storage_dir, filename)
                try:
                    with open(filepath, "r") as f:
                        data = json.load(f)
                    
                    # Return only summary info
                    interviews.append({
                        "id": data["id"],
                        "created_at": data["created_at"],
                        "completed": data["completed"],
                        "rating": data["rating"]
                    })
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON in file {filename}: {e}")
                    # Mark the file as corrupted
                    corrupted_path = os.path.join(self.storage_dir, f"{os.path.splitext(filename)[0]}_corrupted.json")
                    try:
                        # Backup the corrupted file
                        with open(filepath, "r") as src, open(corrupted_path, "w") as dst:
                            dst.write(src.read())
                        print(f"Backed up corrupted file to {corrupted_path}")
                    except Exception as backup_error:
                        print(f"Failed to backup corrupted file: {backup_error}")
                except Exception as e:
                    print(f"Unexpected error loading interview from {filename}: {e}")
        
        # Sort by creation date, newest first
        interviews.sort(key=lambda x: x["created_at"], reverse=True)
        return interviews 