from app import create_app, socketio
import os

# Create the Flask application
app = create_app()

# Enable maximum debugging
app.config['DEBUG'] = True
app.config['FLASK_ENV'] = 'development'
app.config['PROPAGATE_EXCEPTIONS'] = True

# Create necessary directories
os.makedirs(os.path.join(os.getcwd(), "app", "static", "temp"), exist_ok=True)
os.makedirs(os.path.join(os.getcwd(), "interviews"), exist_ok=True)

if __name__ == '__main__':
    try:
        print("Starting AI Interviewer application...")
        socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
    except Exception as e:
        print(f"Error starting application: {e}")
        raise 