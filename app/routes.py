import os
import json
import uuid
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, send_file, current_app
from app.models import Interview, InterviewStorage
from app.services import LLMService, SpeechService, LiveKitService, Message
from app import socketio
from flask_socketio import join_room, leave_room
from werkzeug.utils import secure_filename
import asyncio
import base64
from threading import Thread
import random

# Initialize services
llm_service = LLMService()
speech_service = SpeechService()
livekit_service = LiveKitService()
interview_storage = InterviewStorage(storage_dir=os.path.join(os.getcwd(), "interviews"))

# Define blueprint
main = Blueprint("main", __name__)

# Pre-defined fallback questions for quick mode
def get_fallback_question(interview, question_num):
    """Generate an interview question based on the job description and system prompt."""
    # Extract key information from the interview
    job_description = interview.job_description
    system_prompt = interview.system_prompt
    cv = interview.cv
    
    # Generate questions based on the job description and system prompt
    job_specific_questions = [
        f"Based on the job description that mentions {job_description[:50]}..., could you tell me about your background and why you're interested in this position?",
        f"The role requires skills in {job_description[50:100]}... Can you share a specific example of how you've demonstrated these skills?",
        f"How do your qualifications align with the requirements mentioned in the job description, particularly regarding {job_description[100:150]}...?",
        f"What aspects of this role involving {job_description[150:200]}... are you most excited about?",
        f"The job involves responsibilities related to {job_description[200:250]}... How has your previous experience prepared you for this?"
    ]
    
    # Add questions from system prompt if it exists
    if system_prompt and len(system_prompt) > 10:
        # Extract potential questions from system prompt by looking for question marks
        parts = system_prompt.split('?')
        extracted_questions = []
        for i in range(len(parts)-1):  # Exclude the last part which doesn't end with a question mark
            # Get the text before the question mark and add it back
            question = parts[i].strip()
            # Only include if it's reasonably long (likely a full question)
            if len(question) > 15:
                if not question.startswith("Could you") and not question.startswith("Can you"):
                    question = "Could you " + question.lower()
                extracted_questions.append(f"{question}?")
        
        # Add any extracted questions to our list
        job_specific_questions.extend(extracted_questions)
    
    # Ensure we have enough questions by adding generic follow-ups
    generic_followups = [
        "Could you elaborate more on your previous answer?",
        "That's interesting. How does that experience relate to the position you're applying for?",
        "Can you provide another example that demonstrates your skills in this area?",
        "What would you do differently if you encountered a similar situation in this role?",
        "How do you think your approach would benefit our team?",
        "What metrics or methods would you use to measure success in these efforts?"
    ]
    
    # Combine all questions
    all_questions = job_specific_questions + generic_followups
    
    # Return closing question if we've gone through all questions
    if question_num >= len(all_questions):
        return "Thank you for all your answers. Based on our conversation, is there anything else you'd like to add before we conclude the interview?"
    
    return all_questions[question_num]

# Helper to convert messages for LLM format
def format_messages_for_llm(interview):
    # Start with system prompt
    system_content = llm_service.generate_initial_prompt(
        interview.cv, interview.job_description, interview.system_prompt
    )
    messages = [Message(role="system", content=system_content)]
    
    # Add transcript messages
    for message in interview.transcripts:
        role = "assistant" if message["role"] == "ai" else "user"
        messages.append(Message(role=role, content=message["content"]))
    
    return messages


# Routes
@main.route("/")
def index():
    """Admin dashboard route."""
    interviews = interview_storage.list_interviews()
    return render_template("admin.html", interviews=interviews)


@main.route("/create_interview", methods=["POST"])
def create_interview():
    """Create a new interview."""
    cv = request.form.get("cv", "")
    job_description = request.form.get("job_description", "")
    system_prompt = request.form.get("system_prompt", "")
    
    if not cv or not job_description:
        return jsonify({"error": "CV and Job Description are required"}), 400
    
    # Create new interview
    interview = Interview(cv=cv, job_description=job_description, system_prompt=system_prompt)
    
    # Save interview
    interview_storage.save_interview(interview)
    
    # Create LiveKit room
    room_name = f"interview-{interview.id}"
    livekit_service.create_room(room_name)
    
    return jsonify({
        "interview_id": interview.id,
        "invite_link": url_for("main.join_interview", interview_id=interview.id, _external=True)
    })


@main.route("/interview/<interview_id>/join")
def join_interview(interview_id):
    """Join an interview as a candidate."""
    # Load the interview using the existing interview_storage
    interview = interview_storage.load_interview(interview_id)
    
    # Check if interview exists
    if not interview:
        return "Interview not found", 404
    
    # Create LiveKit token for candidate
    room_name = f"interview-{interview_id}"
    token = livekit_service.create_token(room_name, f"candidate-{uuid.uuid4()}", is_admin=False)
    
    # Pass the interview object to the template
    return render_template(
        "interview.html",
        interview=interview,
        interview_id=interview_id,
        room_name=room_name,
        token=token,
        livekit_url=os.getenv("LIVEKIT_URL"),
        is_admin=False
    )


@main.route("/admin/interview/<interview_id>")
def admin_view_interview(interview_id):
    """Admin view of an interview."""
    interview = interview_storage.load_interview(interview_id)
    if not interview:
        return "Interview not found", 404
    
    return render_template(
        "admin.html",
        interview=interview,
        transcripts=interview.transcripts
    )


@main.route("/api/interviews/<interview_id>", methods=["GET"])
def get_interview(interview_id):
    """Get interview data."""
    interview = interview_storage.load_interview(interview_id)
    if not interview:
        return jsonify({"error": "Interview not found"}), 404
    
    return jsonify(interview.to_dict())


@main.route("/api/tts", methods=["POST"])
def text_to_speech_api():
    """Convert text to speech."""
    text = request.json.get("text", "")
    if not text:
        return jsonify({"error": "Text is required"}), 400
    
    audio_data = speech_service.text_to_speech(text)
    if not audio_data:
        return jsonify({"error": "Failed to generate speech"}), 500
    
    # Save audio to temporary file
    filename = f"tts_{uuid.uuid4()}.mp3"
    filepath = os.path.join(os.getcwd(), "app", "static", "temp", filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    with open(filepath, "wb") as f:
        f.write(audio_data)
    
    return jsonify({
        "audio_url": url_for("static", filename=f"temp/{filename}")
    })


# WebSocket handlers
@socketio.on("connect")
def handle_connect():
    print(f"Client connected: {request.sid}")


@socketio.on("disconnect")
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")


@socketio.on("join_interview")
def handle_join_interview(data):
    interview_id = data.get("interview_id")
    if not interview_id:
        print("No interview_id provided in join_interview event")
        return
    
    # Join room for this interview
    join_room(f"interview_{interview_id}")
    print(f"Client {request.sid} joined interview {interview_id}")
    
    # Load interview
    interview = interview_storage.load_interview(interview_id)
    if not interview:
        print(f"Interview {interview_id} not found")
        socketio.emit("error", {"message": "Interview not found"}, to=request.sid)
        return
    
    # If no messages yet, generate initial greeting
    print(f"Interview has {len(interview.transcripts)} messages")
    
    # Always generate a greeting/first question when a user joins
    # Format messages for LLM
    messages = format_messages_for_llm(interview)
    
    # Generate greeting
    try:
        if not interview.transcripts:
            print("Generating initial greeting")
            ai_message = "Welcome to your interview! I'll be asking you some questions about your experience and skills. Let's start: Could you tell me about your background and why you're interested in this position?"
        else:
            print("Generating next question")
            ai_message = llm_service.generate_interview_question(messages)
        
        # Add to transcript if it's new
        if not interview.transcripts or interview.transcripts[-1]["role"] != "ai":
            interview.add_message("ai", ai_message)
            interview_storage.save_interview(interview)
        else:
            # Use the last AI message
            ai_message = interview.transcripts[-1]["content"]
        
        # Convert to speech
        print("Converting to speech")
        audio_data = speech_service.text_to_speech(ai_message)
        
        # If audio generation failed, try one more time with a fallback voice
        if not audio_data or len(audio_data) < 100:  # Check if audio data is too small/empty
            print("First audio generation attempt failed, retrying...")
            audio_data = speech_service.text_to_speech(ai_message, fallback_voice=True)
        
        # Save audio to temporary file
        filename = f"tts_{uuid.uuid4()}.mp3"
        filepath = os.path.join(os.getcwd(), "app", "static", "temp", filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, "wb") as f:
            f.write(audio_data)
        
        # Emit greeting
        print(f"Emitting AI message to room interview_{interview_id}")
        socketio.emit("ai_message", {
            "message": ai_message,
            "audio_url": url_for("static", filename=f"temp/{filename}", _external=True)
        }, to=f"interview_{interview_id}")
        
        # Also send directly to the user who just joined
        print(f"Emitting AI message directly to client {request.sid}")
        socketio.emit("ai_message", {
            "message": ai_message,
            "audio_url": url_for("static", filename=f"temp/{filename}", _external=True)
        }, to=request.sid)
    except Exception as e:
        print(f"Error generating greeting: {e}")
        socketio.emit("error", {"message": "Error starting interview"}, to=request.sid)


@socketio.on("candidate_speech")
def handle_candidate_speech(data):
    interview_id = data.get("interview_id")
    audio_data = data.get("audio")
    text = data.get("text")  # For direct text input (e.g., "end the interview")
    use_quick_mode = data.get("quick_mode", False)  # Optional flag to skip LLM for faster responses
    
    if not interview_id:
        return
    
    # Load interview
    interview = interview_storage.load_interview(interview_id)
    if not interview:
        return
    
    if text:
        # Direct text input provided (e.g., from end interview button)
        transcript = text
        evaluation = None  # Initialize evaluation variable
        
        # Add to transcript
        interview.add_message("candidate", transcript)
        interview_storage.save_interview(interview)
        
        # Emit back to the client to acknowledge and update UI
        socketio.emit("transcription_result", {
            "transcript": transcript
        }, to=f"interview_{interview_id}")
        
        # Process the text response unless it's an end command
        if "end the interview" not in transcript.lower():
            # Send a processing update for evaluation
            socketio.emit("processing_update", {
                "status": "evaluating",
                "message": "Evaluating your text response..."
            }, to=f"interview_{interview_id}")
            
            # Generate evaluation for the text response
            evaluation = llm_service.generate_response_evaluation(transcript)
            
            # Add evaluation to interview data but don't show to user
            interview.add_message("evaluation", evaluation)
            interview_storage.save_interview(interview)
            
            # Let the user know we're generating a response
            socketio.emit("processing_update", {
                "status": "thinking",
                "message": "AI is thinking about your text response..."
            }, to=f"interview_{interview_id}")
        
        # Continue with the original workflow for text
        # Format messages for LLM
        messages = format_messages_for_llm(interview)
        
        # Check if this is the end of the interview
        if len(interview.transcripts) >= 10 or "end the interview" in transcript.lower():
            try:
                # Generate final assessment
                rating, verdict = llm_service.generate_final_assessment(messages)
                interview.set_rating(rating, verdict)
                
                # Save interview
                interview_storage.save_interview(interview)
                
                # Generate thank you message
                ai_message = f"Thank you for participating in this interview. I have completed my assessment. You received a rating of {rating}/10. {verdict}"
                
                # Add to transcript
                interview.add_message("ai", ai_message)
                interview_storage.save_interview(interview)
                
                # Convert to speech
                audio_data = speech_service.text_to_speech(ai_message)
                
                # If audio generation failed, try one more time with a fallback voice
                if not audio_data or len(audio_data) < 100:  # Check if audio data is too small/empty
                    print("First audio generation attempt failed, retrying with fallback voice...")
                    audio_data = speech_service.text_to_speech(ai_message, fallback_voice=True)
                
                # Debug the audio data
                if not audio_data or len(audio_data) < 100:
                    print("WARNING: Both TTS attempts failed for final assessment. Sending response without audio.")
                    # Set empty audio URL - will trigger browser TTS fallback
                    audio_url = ""
                else:
                    print(f"Successfully generated final assessment audio, size: {len(audio_data)} bytes")
                    # Save audio to temporary file
                    filename = f"tts_{uuid.uuid4()}.mp3"
                    filepath = os.path.join(os.getcwd(), "app", "static", "temp", filename)
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    
                    with open(filepath, "wb") as f:
                        f.write(audio_data)
                    
                    # Set the audio URL
                    audio_url = url_for("static", filename=f"temp/{filename}", _external=True)
                
                # Emit final message
                socketio.emit("ai_message", {
                    "message": ai_message,
                    "audio_url": audio_url,
                    "is_final": True,
                    "rating": rating,
                    "verdict": verdict
                }, to=f"interview_{interview_id}")
            except Exception as e:
                print(f"Error generating final assessment: {e}")
                
                # Fallback response
                fallback_message = "Thank you for participating in this interview. I've enjoyed our conversation. Based on your responses, I'd rate you a 7 out of 10. You appear to be a good fit for the position."
                
                # Add to transcript
                interview.add_message("ai", fallback_message)
                interview_storage.save_interview(interview)
                interview.set_rating(7, "Good fit for the position.")
                interview_storage.save_interview(interview)
                
                # Try to generate speech with the fallback message
                audio_data = speech_service.text_to_speech(fallback_message)
                
                # If audio generation failed, try one more time with a fallback voice
                if not audio_data or len(audio_data) < 100:  # Check if audio data is too small/empty
                    print("First audio generation attempt failed, retrying with fallback voice...")
                    audio_data = speech_service.text_to_speech(fallback_message, fallback_voice=True)
                
                # Debug the audio data
                if not audio_data or len(audio_data) < 100:
                    print("WARNING: Both TTS attempts failed for fallback message. Sending response without audio.")
                    # Set empty audio URL - will trigger browser TTS fallback
                    audio_url = ""
                else:
                    print(f"Successfully generated fallback audio, size: {len(audio_data)} bytes")
                    # Save audio to temporary file
                    filename = f"tts_{uuid.uuid4()}.mp3"
                    filepath = os.path.join(os.getcwd(), "app", "static", "temp", filename)
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    
                    with open(filepath, "wb") as f:
                        f.write(audio_data)
                    
                    # Set the audio URL
                    audio_url = url_for("static", filename=f"temp/{filename}", _external=True)
                
                # Emit final message
                socketio.emit("ai_message", {
                    "message": fallback_message,
                    "audio_url": audio_url
                }, to=f"interview_{interview_id}")
        else:
            try:
                # If there was an evaluation, use it for a better response
                if evaluation:
                    # Create a new prompt that includes the evaluation
                    next_question_prompt = f"""
                    Based on the candidate's response and my evaluation, I need to ask a good follow-up question.
                    The candidate's response was: "{transcript}"
                    
                    My evaluation was: "{evaluation}"
                    
                    Now I will ask a relevant follow-up question that probes deeper or shifts to a new area as appropriate:
                    """
                    
                    next_question_message = Message(role="user", content=next_question_prompt)
                    messages.append(next_question_message)
                
                # Generate next question
                ai_message = llm_service.generate_interview_question(messages)
                
                # Add to transcript
                interview.add_message("ai", ai_message)
                interview_storage.save_interview(interview)
                
                # Send a processing update before attempting TTS
                socketio.emit("processing_update", {
                    "status": "speaking",
                    "message": "Converting AI response to speech..."
                }, to=f"interview_{interview_id}")
                
                # Convert to speech
                print(f"Converting response to speech: '{ai_message[:50]}...'")
                audio_data = speech_service.text_to_speech(ai_message)
                
                # If audio generation failed, try one more time with a fallback voice
                if not audio_data or len(audio_data) < 100:  # Check if audio data is too small/empty
                    print("First audio generation attempt failed, retrying with fallback voice...")
                    audio_data = speech_service.text_to_speech(ai_message, fallback_voice=True)
                
                # Debug the audio data
                if not audio_data or len(audio_data) < 100:
                    print("WARNING: Both TTS attempts failed for final assessment. Sending response without audio.")
                    # Set empty audio URL - will trigger browser TTS fallback
                    audio_url = ""
                else:
                    print(f"Successfully generated final assessment audio, size: {len(audio_data)} bytes")
                    # Save audio to temporary file
                    filename = f"tts_{uuid.uuid4()}.mp3"
                    filepath = os.path.join(os.getcwd(), "app", "static", "temp", filename)
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    
                    with open(filepath, "wb") as f:
                        f.write(audio_data)
                    
                    # Set the audio URL
                    audio_url = url_for("static", filename=f"temp/{filename}", _external=True)
                
                # Emit next question
                socketio.emit("ai_message", {
                    "message": ai_message,
                    "audio_url": audio_url
                }, to=f"interview_{interview_id}")
                
            except Exception as e:
                print(f"Error generating question: {e}")
                
                # Fallback question
                fallback_message = "I'm interested in learning more about your experience. Could you tell me about a challenging situation at work and how you handled it?"
                
                # Add to transcript
                interview.add_message("ai", fallback_message)
                interview_storage.save_interview(interview)
                
                # Try to generate speech with the fallback message
                audio_data = speech_service.text_to_speech(fallback_message)
                
                # If audio generation failed, try one more time with a fallback voice
                if not audio_data or len(audio_data) < 100:  # Check if audio data is too small/empty
                    print("First audio generation attempt failed, retrying with fallback voice...")
                    audio_data = speech_service.text_to_speech(fallback_message, fallback_voice=True)
                
                # Debug the audio data
                if not audio_data or len(audio_data) < 100:
                    print("WARNING: Both TTS attempts failed for fallback message. Sending response without audio.")
                    # Set empty audio URL - will trigger browser TTS fallback
                    audio_url = ""
                else:
                    print(f"Successfully generated fallback audio, size: {len(audio_data)} bytes")
                    # Save audio to temporary file
                    filename = f"tts_{uuid.uuid4()}.mp3"
                    filepath = os.path.join(os.getcwd(), "app", "static", "temp", filename)
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    
                    with open(filepath, "wb") as f:
                        f.write(audio_data)
                    
                    # Set the audio URL
                    audio_url = url_for("static", filename=f"temp/{filename}", _external=True)
                
                # Emit fallback question
                socketio.emit("ai_message", {
                    "message": fallback_message,
                    "audio_url": audio_url
                }, to=f"interview_{interview_id}")
    elif audio_data:
        try:
            # Convert base64 to bytes
            audio_bytes = base64.b64decode(audio_data.split(",")[1])
            
            # Save audio to file
            audio_filename = f"response_{uuid.uuid4()}.webm"
            audio_filepath = os.path.join(os.getcwd(), "app", "uploads", audio_filename)
            speech_service.save_audio(audio_bytes, audio_filepath)
            
            # Start processing in background
            print("Starting audio processing thread...")
            app = current_app._get_current_object()  # Get actual app object, not proxy
            Thread(target=process_audio, args=(app, audio_bytes, interview, interview_id, use_quick_mode)).start()
            
            # Return immediately to acknowledge receipt
            return
            
        except Exception as e:
            print(f"Error processing audio: {e}")
            socketio.emit("error", {"message": "Failed to process audio"}, to=request.sid)
            return
    else:
        socketio.emit("error", {"message": "No audio or text provided"}, to=request.sid)
        return 


# Process audio in a separate function outside the route handler
def process_audio(app, audio_bytes, interview, interview_id, use_quick_mode=False):
    """Process audio in a background thread with proper app context."""
    try:
        # Set up asyncio loop for transcription
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Get transcript
        transcript_result = loop.run_until_complete(
            speech_service.transcribe_audio(audio_bytes)
        )
        
        # Fall back to a message if transcription failed
        if not transcript_result or transcript_result.strip() == "":
            transcript_result = "I apologize, but I couldn't hear what you said. Could you please repeat?"
        
        # Save transcript and send back to client immediately
        interview.add_message("candidate", transcript_result)
        interview_storage.save_interview(interview)
        socketio.emit("transcription_result", {
            "transcript": transcript_result
        }, to=f"interview_{interview_id}")
        
        # Process with LLM - send progress updates
        socketio.emit("processing_update", {"status": "evaluating"}, to=f"interview_{interview_id}")
        
        # Get messages for LLM
        messages = format_messages_for_llm(interview)
        
        # Generate evaluation
        socketio.emit("processing_update", {"status": "thinking"}, to=f"interview_{interview_id}")
        evaluation = llm_service.generate_response_evaluation(transcript_result)
        interview.add_message("evaluation", evaluation)
        interview_storage.save_interview(interview)
        
        # Generate AI response - using quick mode or full LLM
        try:
            if use_quick_mode:
                # Use pre-defined question for faster response
                question_num = len([m for m in interview.transcripts if m["role"] == "candidate"])
                ai_message = get_fallback_question(interview, question_num)
            else:
                # Prepare evaluation-based prompt
                next_question_prompt = f"Based on the candidate's response: \"{transcript_result}\"\n\nMy evaluation: \"{evaluation}\"\n\nI will ask a relevant follow-up question:"
                next_question_message = Message(role="user", content=next_question_prompt)
                messages.append(next_question_message)
                
                ai_message = llm_service.generate_interview_question(messages)
                
            # Update status before TTS
            socketio.emit("processing_update", {"status": "speaking"}, to=f"interview_{interview_id}")
            
        except Exception as llm_error:
            # Use a simple fallback question if generation fails
            fallback_responses = [
                "Could you elaborate more on your experience and skills?",
                "Tell me about a challenging project you worked on.",
                "How do your skills align with this position?",
                "What's your approach to problem-solving?",
                "Can you share an example of teamwork?"
            ]
            ai_message = random.choice(fallback_responses)
        
        # Add AI message to transcript
        interview.add_message("ai", ai_message)
        interview_storage.save_interview(interview)
        
        # Generate speech and send response
        audio_data = speech_service.text_to_speech(ai_message)
        if not audio_data or len(audio_data) < 100:
            audio_data = speech_service.text_to_speech(ai_message, fallback_voice=True)
        
        # Create audio file if we have valid audio
        audio_url = ""
        if audio_data and len(audio_data) >= 100:
            # Save audio to temporary file
            filename = f"tts_{uuid.uuid4()}.mp3"
            filepath = os.path.join(os.getcwd(), "app", "static", "temp", filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, "wb") as f:
                f.write(audio_data)
            
            with app.app_context():
                audio_url = url_for("static", filename=f"temp/{filename}", _external=True)
        
        # Send response to client
        with app.app_context():
            socketio.emit("ai_message", {
                "message": ai_message,
                "audio_url": audio_url
            }, to=f"interview_{interview_id}")
            
    except Exception as e:
        # Simple error handling with a fallback response
        print(f"Error in process_audio: {e}")
        socketio.emit("error", {"message": "Error processing your response"}, to=f"interview_{interview_id}")
        
        with app.app_context():
            # Send a simple fallback
            fallback_message = "I'm sorry, I encountered a technical issue. Could you share more about your experience?"
            socketio.emit("ai_message", {
                "message": fallback_message,
                "audio_url": ""  # Empty URL will trigger browser TTS
            }, to=f"interview_{interview_id}") 