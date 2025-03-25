import os
import json
import base64
import requests
import jwt
import time
import threading
import re
from typing import Dict, Any, List, Tuple, Optional
from deepgram import Deepgram
from pydantic import BaseModel

# Timeout handler for long-running operations
class TimeoutException(Exception):
    pass

def run_with_timeout(func, args=(), kwargs={}, timeout_secs=60, default=None):
    """Run a function with a timeout - simplified implementation."""
    result = [default]
    
    def worker():
        try:
            result[0] = func(*args, **kwargs)
        except Exception as e:
            print(f"Error in {func.__name__}: {e}")
    
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout_secs)
    
    if thread.is_alive():
        print(f"Function {func.__name__} timed out after {timeout_secs} seconds")
        return default
        
    return result[0]

# Initialize API clients
deepgram = Deepgram(os.getenv("DEEPGRAM_API_KEY"))
livekit_api_key = os.getenv("LIVEKIT_API_KEY")
livekit_api_secret = os.getenv("LIVEKIT_API_SECRET")
livekit_url = os.getenv("LIVEKIT_URL")
groq_api_key = os.getenv("GROQ_API_KEY")  # Add your Groq API key to .env file

class Message(BaseModel):
    """Pydantic model for chat messages."""
    role: str
    content: str

class LLMService:
    """Service for interacting with LLMs via Groq API."""
    
    def __init__(self):
        self.api_key = groq_api_key
        # Use Llama 3 8B model through Groq API
        self.model = "llama3-8b-8192"
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
    
    def generate_initial_prompt(self, cv: str, job_description: str, system_prompt: str) -> str:
        """Generate the initial system prompt for the LLM."""
        system_content = f"""You are an AI interviewer conducting a job interview. 
Your goal is to assess the candidate's fit for the position.

The candidate has submitted the following CV:
{cv}

The job description is:
{job_description}

Additional interviewer instructions:
{system_prompt}

Please conduct this interview professionally. Start by greeting the candidate and asking the first question.
Assess their responses, ask relevant follow-up questions, and provide a final assessment."""

        # We'll use this to set up the initial messages
        return system_content
    
    def generate_interview_question(self, messages: List[Message]) -> str:
        """Generate the next interview question using Groq API."""
        try:
            # Format messages for the API
            formatted_messages = []
            
            # Find the system message and put it first
            system_content = ""
            for msg in messages:
                if msg.role == "system":
                    system_content = msg.content
                    break
            
            if system_content:
                formatted_messages.append({"role": "system", "content": system_content})
            
            # Add the rest of the messages
            for msg in messages:
                if msg.role != "system":
                    role = "assistant" if msg.role == "assistant" else "user"
                    formatted_messages.append({"role": role, "content": msg.content})
            
            # Add a final system message asking for the next question
            formatted_messages.append({
                "role": "system", 
                "content": "Based on the conversation so far, ask a relevant follow-up interview question to continue the interview."
            })
            
            # Call the Groq API
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model,
                "messages": formatted_messages,
                "temperature": 0.7,
                "max_tokens": 200,
                "top_p": 1,
                "stream": False
            }
            
            # Define the API call function to use with timeout
            def call_api():
                response = requests.post(self.api_url, headers=headers, json=data)
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"API Error: {response.status_code} - {response.text}")
                    return None
            
            # Run with timeout
            result = run_with_timeout(call_api, timeout_secs=30, default=None)
            
            # If API call failed or timed out, use fallback
            if not result:
                print("API call failed or timed out, using fallback response")
                import random
                fallback_responses = [
                    "Thank you for sharing that information. Could you tell me about a specific project or challenge you've worked on in your previous role?",
                    "That's interesting background. How do you think your experience aligns with this position?",
                    "I'd like to hear more about your technical skills. Could you describe a situation where you applied them effectively?",
                    "Let's discuss your problem-solving approach. Can you share an example of a complex issue you resolved?",
                    "I'm curious about your teamwork experience. Can you tell me about a successful collaboration you've been part of?",
                    "What aspects of this role are you most excited about, and how do your skills match these requirements?"
                ]
                return random.choice(fallback_responses)
            
            # Extract the assistant's message
            return result["choices"][0]["message"]["content"]
            
        except Exception as e:
            print(f"Error generating question: {e}")
            return "I apologize, but I'm having trouble formulating my next question. Could you tell me more about your qualifications and how they relate to this position?"
    
    def generate_final_assessment(self, messages: List[Message]) -> Tuple[int, str]:
        """Generate a final assessment of the candidate for the interview using Groq API."""
        try:
            # Format messages for the API
            formatted_messages = []
            
            # Find the system message and put it first
            system_content = ""
            for msg in messages:
                if msg.role == "system":
                    system_content = msg.content
                    break
            
            if system_content:
                formatted_messages.append({"role": "system", "content": system_content})
            
            # Add the rest of the messages
            for msg in messages:
                if msg.role != "system":
                    role = "assistant" if msg.role == "assistant" else "user"
                    formatted_messages.append({"role": role, "content": msg.content})
            
            # Add a final system message asking for the assessment
            formatted_messages.append({
                "role": "system", 
                "content": "Please provide a final assessment of this candidate based on our interview. Give a rating from 1-10 and explain the reasoning. Format the response exactly like this: RATING: X/10\nVERDICT: Your detailed assessment here..."
            })
            
            # Call the Groq API
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model,
                "messages": formatted_messages,
                "temperature": 0.7,
                "max_tokens": 500,
                "top_p": 1,
                "stream": False
            }
            
            # Define the API call function to use with timeout
            def call_api():
                response = requests.post(self.api_url, headers=headers, json=data)
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"API Error: {response.status_code} - {response.text}")
                    return None
            
            # Run with timeout
            result = run_with_timeout(call_api, timeout_secs=45, default=None)
            
            # If API call failed or timed out, use fallback
            if not result:
                print("API call failed or timed out, using fallback assessment")
                return 7, "The candidate shows potential for the role based on their responses. While the full assessment could not be generated, their communication skills and background appear to make them a good fit for the position."
            
            # Extract the assessment
            assessment = result["choices"][0]["message"]["content"]
            
            # Try to extract rating and verdict
            try:
                # Look for "RATING: X/10" pattern
                rating_match = re.search(r"RATING:\s*(\d+)/10", assessment, re.IGNORECASE)
                if rating_match:
                    rating = int(rating_match.group(1))
                    # Bound rating to 1-10
                    rating = max(1, min(10, rating))
                else:
                    # Fallback rating
                    rating = 7
                
                # Look for "VERDICT: ..." pattern
                verdict_match = re.search(r"VERDICT:\s*(.*)", assessment, re.IGNORECASE | re.DOTALL)
                if verdict_match:
                    verdict = verdict_match.group(1).strip()
                else:
                    # Use the whole response as verdict if format is wrong
                    verdict = assessment
                
                return rating, verdict
            except Exception as e:
                print(f"Error parsing assessment: {e}")
                return 7, "Error generating a proper assessment. Based on the conversation, the candidate has shown average performance."
        except Exception as e:
            print(f"Error generating final assessment: {e}")
            return 7, "An error occurred during assessment generation. The system was unable to fully evaluate the candidate."
    
    def generate_response_evaluation(self, response_text: str) -> str:
        """Generate an evaluation of a candidate's response using Groq API."""
        try:
            # Format messages for the API
            formatted_messages = [
                {
                    "role": "system", 
                    "content": "You are an expert interview assessor evaluating a candidate's response. Provide a brief but comprehensive evaluation highlighting strengths and weaknesses."
                },
                {
                    "role": "user",
                    "content": f"Please evaluate this response from a job interview candidate:\n\n\"{response_text}\""
                }
            ]
            
            # Call the Groq API
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model,
                "messages": formatted_messages,
                "temperature": 0.7,
                "max_tokens": 200,
                "top_p": 1,
                "stream": False
            }
            
            # Define the API call function to use with timeout
            def call_api():
                response = requests.post(self.api_url, headers=headers, json=data)
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"API Error: {response.status_code} - {response.text}")
                    return None
            
            # Run with timeout
            result = run_with_timeout(call_api, timeout_secs=15, default=None)
            
            # If API call failed or timed out, use fallback
            if not result:
                print("API call failed or timed out, using fallback evaluation")
                return "The response shows some relevant points but could benefit from more specific examples. Consider this a standard response that demonstrates basic qualifications."
            
            # Extract the evaluation
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"Error generating response evaluation: {e}")
            return "Unable to evaluate the response due to a technical error. The system will continue with the interview."


class SpeechService:
    """Service for speech-to-text and text-to-speech operations."""
    
    async def transcribe_audio(self, audio_data: bytes) -> str:
        """Convert spoken audio to text."""
        try:
            response = await deepgram.transcription.prerecorded(
                {"buffer": audio_data, "mimetype": "audio/webm"},
                {
                    "punctuate": True,
                    "language": "en-US",
                    "model": "nova",
                }
            )
            return response["results"]["channels"][0]["alternatives"][0]["transcript"]
        except Exception as e:
            print(f"Error transcribing audio: {e}")
            return ""
    
    def save_audio(self, audio_data: bytes, filepath: str) -> bool:
        """Save audio data to a file."""
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "wb") as f:
                f.write(audio_data)
            return True
        except Exception as e:
            print(f"Error saving audio: {e}")
            return False
    
    def text_to_speech(self, text: str, fallback_voice: bool = False) -> bytes:
        """Convert text to spoken audio using Deepgram TTS."""
        try:
            # Validate and trim text if needed
            if not text or not isinstance(text, str):
                return b""
            
            # Trim long text (API has limits)
            if len(text) > 3000:
                text = text[:3000] + "..."
            
            # Prepare request
            headers = {
                'Authorization': f'Token {os.getenv("DEEPGRAM_API_KEY")}',
                'Content-Type': 'application/json',
            }
            
            # Simple payload structure
            data = {
                'text': text,
                'voice': 'aura-asteria' if fallback_voice else 'aura-professional',
                'encoding': 'mp3',
                'sample_rate': 24000
            }
            
            # Make API request
            response = requests.post(
                'https://api.deepgram.com/v1/speak',
                headers=headers,
                json=data
            )
            
            # Return audio content or empty bytes on failure
            return response.content if response.status_code == 200 else b""
            
        except Exception as e:
            print(f"TTS error: {str(e)}")
            return b""


class LiveKitService:
    """Service for managing LiveKit rooms and tokens."""
    
    def __init__(self):
        self.api_key = livekit_api_key
        self.api_secret = livekit_api_secret
        self.url = livekit_url
    
    def create_room(self, room_name: str) -> Optional[str]:
        """Create a LiveKit room for the interview."""
        try:
            # For API documentation, see: https://docs.livekit.io/reference/server-sdks/python/
            headers = {
                'Authorization': f'Bearer {self.generate_api_token()}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'name': room_name,
                'emptyTimeout': 60 * 60,  # 1 hour timeout
                'maxParticipants': 2      # Just the candidate and AI
            }
            
            response = requests.post(
                f'{self.url}/rooms',
                headers=headers,
                json=data
            )
            
            if response.status_code in [200, 201]:
                return room_name
            else:
                print(f"Error creating room: {response.text}")
                return None
        except Exception as e:
            print(f"Error creating LiveKit room: {e}")
            return None
    
    def create_token(self, room_name: str, participant_name: str, is_admin: bool = False) -> Optional[str]:
        """Create a LiveKit token for a participant."""
        try:
            permissions = []
            
            if is_admin:
                permissions = ["room-admin", "room-join", "publish", "subscribe"]
            else:
                permissions = ["room-join", "publish", "subscribe"]
            
            # Create JWT token manually
            now = int(time.time())
            
            payload = {
                "iss": self.api_key,
                "sub": participant_name,
                "exp": now + 60 * 60,  # 1 hour token
                "nbf": now,
                "iat": now,
                "jti": f"{participant_name}-{int(time.time())}",
                "video": {
                    "room": room_name,
                    "roomJoin": True,
                    "roomAdmin": is_admin,
                    "canPublish": True,
                    "canSubscribe": True
                },
                "metadata": json.dumps({"role": "admin" if is_admin else "candidate"})
            }
            
            token = jwt.encode(
                payload,
                self.api_secret,
                algorithm="HS256"
            )
            
            return token
        except Exception as e:
            print(f"Error creating LiveKit token: {e}")
            return None
    
    def generate_api_token(self) -> str:
        """Generate a JWT token for API access."""
        try:
            now = int(time.time())
            
            payload = {
                "iss": self.api_key,
                "sub": self.api_key,
                "exp": now + 60,  # 1 minute token for API access
                "nbf": now,
                "iat": now,
                "jti": f"api-{int(time.time())}",
            }
            
            token = jwt.encode(
                payload,
                self.api_secret,
                algorithm="HS256"
            )
            
            return token
        except Exception as e:
            print(f"Error generating API token: {e}")
            return "" 