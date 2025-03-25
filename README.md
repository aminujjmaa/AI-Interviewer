# AI Interviewer Application

A full-stack application that simulates a voice-based AI interviewer. The AI interviewer uses Text-to-Speech (TTS) to ask questions and Speech-to-Text (STT) to transcribe candidate responses. An LLM (Llama 3) provides context-driven follow-up questions and ultimately rates the candidate.

## Features

- **Real-Time Video Meeting**: Integrated LiveKit for live video/audio sessions
- **Speech-to-Text & Text-to-Speech**: Uses Deepgram for transcription and voice generation
- **LLM Integration**: Uses Llama 3 (via Groq API) to generate interview questions and provide final ratings
- **Local-Only Storage**: Data is stored in local JSON files (no external database required)
- **Admin Interface**: Upload CV, job description, and customize system prompt
- **Candidate Interface**: Join interview session, speak, and hear AI responses via TTS
- **Quick Mode**: Option for faster responses on slower hardware
- **Browser TTS Fallback**: Ensures audio works even if API fails

## Model Choice

This application uses Llama 3 (8B parameter version) instead of GPT-4 because:

1. **Open Source**: Llama 3 is an open-source model, making it more accessible for academic and learning purposes
2. **Cost-Effective**: Using Llama 3 through Groq API is more cost-effective than OpenAI's GPT-4
3. **Sufficient Performance**: For interview question generation and evaluation, Llama 3 provides adequate performance

> Note: If you prefer to use GPT-4, you can easily modify the code in `app/services.py` to use OpenAI's API instead.

## Setup Instructions

### Prerequisites

- Python 3.8+
- API Keys for:
  - Groq (for Llama 3 access)
  - Deepgram
  - LiveKit

### Installation

1. Clone this repository:
   ```
   git clone <repository-url>
   cd ai-interviewer
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv .venv
   # On Windows
   .\.venv\Scripts\activate
   # On macOS/Linux
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the root directory:
   ```
   # API Keys
   GROQ_API_KEY=your_groq_api_key
   DEEPGRAM_API_KEY=your_deepgram_api_key

   # LiveKit Configuration
   LIVEKIT_API_KEY=your_livekit_api_key
   LIVEKIT_API_SECRET=your_livekit_api_secret
   LIVEKIT_URL=your_livekit_url

   # Flask Configuration
   FLASK_APP=app
   FLASK_ENV=development
   FLASK_DEBUG=1
   SECRET_KEY=your_secret_key
   ```

5. Create necessary directories:
   ```
   mkdir -p app/static/temp
   mkdir -p app/uploads
   mkdir -p interviews
   ```

6. Run the application:
   ```
   python -m flask run
   ```

7. Open your browser and navigate to:
   ```
   http://127.0.0.1:5000/
   ```

## Usage Guide

### Admin Side

1. Access the admin dashboard at `http://127.0.0.1:5000/`
2. Fill in the form with:
   - Candidate's CV (text format)
   - Job Description
   - System Prompt (optional, to customize the interviewer's behavior)
3. Click "Create Interview"
4. Share the generated link with the candidate

### Candidate Side

1. Click the link provided by the admin
2. Allow camera and microphone access when prompted
3. Wait for the AI interviewer to greet you and ask the first question
4. Use the "Hold to Speak" button while answering or type your response in the text box
5. If using a slow CPU, toggle the "Quick Mode" option for faster responses
6. The AI will respond with follow-up questions
7. After several questions, the AI will provide a final rating and verdict

## Project Structure

- `/app`: Main application code
  - `/models`: Data models for interview sessions
  - `/templates`: HTML templates for the frontend
  - `/static`: CSS, JavaScript files
  - `__init__.py`: Flask application initialization
  - `routes.py`: API endpoints and view routes
  - `services.py`: Service classes for Groq, Deepgram, and LiveKit

- `/interviews`: Directory where interview data is stored

## Getting API Keys

### Groq API Key
1. Sign up at https://console.groq.com/
2. Navigate to API Keys section
3. Create a new API key and copy it to your `.env` file

### Deepgram API Key
1. Sign up at https://console.deepgram.com/
2. Create a new project
3. Generate an API key with Speech-to-Text and Text-to-Speech permissions
4. Copy it to your `.env` file

### LiveKit Configuration
1. You can use their cloud service or set up your own server
2. For testing, use the development server details from LiveKit

## Troubleshooting

- If audio/video issues occur, check browser permissions
- Verify all API keys in the `.env` file are correct
- For slow responses, enable the "Quick Mode" toggle
- Check browser console for JavaScript errors
- If using a CPU instead of GPU, expect longer response times

## Notes and Limitations

- The application requires valid API keys for all services
- Audio is processed in chunks, which may cause slight delays
- The system is designed for one-on-one interviews
- For best experience, use Chrome or Firefox
- Default timeout is 100 seconds for Llama 3 responses on CPU

## License

This project is licensed under the MIT License - see the LICENSE file for details. 