import os
from flask import Flask
from flask_socketio import SocketIO
from dotenv import load_dotenv
from app.utils import validate_all_interview_files

# Load environment variables from .env file
load_dotenv()

# Initialize Flask-SocketIO
socketio = SocketIO()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key')
    
    # Configure app settings
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB limit
    
    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Define a function to validate interview files
    def validate_interviews():
        interviews_dir = os.path.join(os.getcwd(), "interviews")
        if os.path.exists(interviews_dir):
            total, repaired, failed = validate_all_interview_files(interviews_dir)
            print(f"Validated interview files: {total} total, {repaired} valid/repaired, {failed} failed")
    
    # Validate files immediately (no need to wait for the first request)
    validate_interviews()
    
    # Import and register routes
    from app.routes import main as main_blueprint
    app.register_blueprint(main_blueprint)
    
    # Initialize Socket.IO with the app
    socketio.init_app(app, cors_allowed_origins="*")
    
    return app 