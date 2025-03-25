/**
 * JavaScript for the interview page
 */

// Global debug flag - set to true for detailed console logs
const DEBUG = true;

// Initialize variables
console.log("Initializing Socket.IO connection");
const socket = io();
let mediaRecorder;
let audioChunks = [];
let localStream;
let recordingInterval;
let isInterviewActive = false;
let isSpeaking = false;

// Global variables for timeout handling
let aiResponseTimeout = null;
const AI_RESPONSE_TIMEOUT_MS = 10000; // 10 seconds

// Quick mode flag for faster responses (skips LLM generation)
let quickModeEnabled = false;

// Global variables for timing and UI feedback
let recordingStartTime = 0;
let recordingEndTime = 0;
let transcriptionReceived = false;
let responseStartTime = 0;

// DOM Elements - defined globally
let startButton;
let endButton;
let toggleMicButton;
let toggleVideoButton;
let holdToSpeakButton;
let statusArea;
let conversationLog;
let localVideo;
let remoteVideo;
let responseText;
let sendTextButton;
let quickModeToggle;  // Quick mode toggle checkbox

// Setup event listeners once the DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM loaded, getting elements");
    
    // Get DOM elements
    startButton = document.getElementById('start-interview');
    endButton = document.getElementById('end-interview');
    toggleMicButton = document.getElementById('toggle-mic');
    toggleVideoButton = document.getElementById('toggle-video');
    holdToSpeakButton = document.getElementById('hold-to-speak');
    statusArea = document.getElementById('status-area');
    conversationLog = document.getElementById('conversation-log');
    localVideo = document.getElementById('local-video');
    remoteVideo = document.getElementById('remote-video');
    responseText = document.getElementById('response-text');
    sendTextButton = document.getElementById('send-text');
    quickModeToggle = document.getElementById('quick-mode-toggle');

    if (!startButton) {
        console.error("Could not find start-interview button");
        return;
    }

    // Setup event listeners
    console.log("Setting up event listeners");
    
    // Button click handlers
    startButton.addEventListener('click', function() {
        console.log("Start interview button clicked");
        startInterview();
    });
    
    endButton.addEventListener('click', function() {
        console.log("End interview button clicked");
        endInterview();
    });
    
    toggleMicButton.addEventListener('click', function() {
        console.log("Toggle mic button clicked");
        toggleMicrophone();
    });
    
    toggleVideoButton.addEventListener('click', function() {
        console.log("Toggle video button clicked");
        toggleVideo();
    });

    // Hold to Speak functionality
    if (holdToSpeakButton) {
        holdToSpeakButton.addEventListener('mousedown', function() {
            console.log("Hold to speak button pressed");
            startRecording();
        });
        
        holdToSpeakButton.addEventListener('mouseup', function() {
            console.log("Hold to speak button released");
            stopRecording();
        });
        
        holdToSpeakButton.addEventListener('mouseleave', function() {
            console.log("Hold to speak button left");
            if (mediaRecorder && mediaRecorder.state === 'recording') {
                stopRecording();
            }
        });
        
        // Touch events for mobile
        holdToSpeakButton.addEventListener('touchstart', function(e) {
            e.preventDefault();
            console.log("Hold to speak button touched");
            startRecording();
        });
        
        holdToSpeakButton.addEventListener('touchend', function() {
            console.log("Hold to speak button touch ended");
            stopRecording();
        });
    }

    // Text input handling
    sendTextButton.addEventListener('click', function() {
        sendTextResponse();
    });
    
    // Also allow Enter key to send
    responseText.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendTextResponse();
        }
    });
    
    // Quick mode toggle
    if (quickModeToggle) {
        quickModeToggle.addEventListener('change', function() {
            quickModeEnabled = this.checked;
            console.log("Quick mode " + (quickModeEnabled ? "enabled" : "disabled"));
            updateStatus("Quick mode " + (quickModeEnabled ? "enabled" : "disabled") + 
                " - " + (quickModeEnabled ? "Using job-specific questions for faster responses" : "Using AI to generate personalized questions"));
        });
    }
    
    // Connect to LiveKit if LiveKit is available
    if (typeof room_name !== 'undefined' && typeof token !== 'undefined') {
        console.log("LiveKit credentials found, connecting");
        connectToLiveKit();
    } else {
        console.log("No LiveKit credentials found");
    }
    
    // Initialize Socket.IO
    console.log("Initializing Socket.IO events");
    initializeSocket();
});

// Initialize Socket.IO event handlers
function initializeSocket() {
    socket.on('connect', function() {
        console.log('Socket connected');
        
        // Join the interview room
        socket.emit('join_interview', {
            interview_id: interviewId
        });
        
        // Handle reconnection, if controls were disabled
        if (isInterviewActive) {
            updateStatus('Connection restored. You can continue the interview.');
            holdToSpeakButton.disabled = false;
            responseText.disabled = false;
            sendTextButton.disabled = false;
        }
    });
    
    socket.on('disconnect', function() {
        console.log('Socket disconnected');
        updateStatus('Connection lost. Please wait while we reconnect...');
        
        // Disable controls during disconnection
        if (isInterviewActive) {
            holdToSpeakButton.disabled = true;
            responseText.disabled = true;
            sendTextButton.disabled = true;
        }
    });
    
    socket.on('connect_error', function(error) {
        console.error('Socket.IO connection error:', error);
        updateStatus('Error connecting to server. Please refresh the page and try again.');
    });
    
    socket.on('error', function(error) {
        console.error('Socket.IO error:', error);
        updateStatus('Server error occurred. Please refresh the page and try again.');
    });
    
    socket.on('transcription_result', function(data) {
        if (DEBUG) console.log('Received transcription result:', data);
        
        // Remove the placeholder message
        const placeholders = document.querySelectorAll('.message-candidate');
        if (placeholders.length > 0) {
            const lastPlaceholder = placeholders[placeholders.length - 1];
            if (lastPlaceholder.querySelector('.message-content').textContent === '...') {
                // Update the placeholder with the actual transcription
                lastPlaceholder.querySelector('.message-content').textContent = data.transcript;
                
                // Log the time it took to get the transcription
                console.log('Transcription received in: ' + 
                    ((new Date().getTime() - recordingEndTime) / 1000).toFixed(2) + 's');
                
                // Update status to show we're waiting for AI response
                updateStatus('Transcription received. AI is processing your response...');
            } else {
                // If no placeholder found, add a new message
                addMessageToConversation('You', data.transcript, 'candidate');
            }
        } else {
            // If no placeholder found, add a new message
            addMessageToConversation('You', data.transcript, 'candidate');
        }
    });
    
    socket.on('processing_update', function(data) {
        if (DEBUG) console.log('Processing update:', data);
        
        // Update the typing indicator and status based on the processing stage
        if (data.status === 'evaluating') {
            showTypingIndicator('Evaluating your response...');
            updateStatus('AI is evaluating your response quality...');
        } else if (data.status === 'thinking') {
            // Show a thinking/processing indicator with dots that increase over time
            let dots = '.';
            showTypingIndicator('Thinking about your response' + dots);
            
            // Create an animation effect for the thinking dots
            let dotCount = 1;
            const thinkingAnimation = setInterval(() => {
                dotCount = (dotCount % 6) + 1; // Cycle between 1-6 dots
                dots = '.'.repeat(dotCount);
                
                const indicatorElem = document.getElementById('ai-typing-indicator');
                if (indicatorElem) {
                    const contentElem = indicatorElem.querySelector('.message-content');
                    if (contentElem) {
                        const statusElem = contentElem.querySelector('.status-text');
                        if (statusElem) {
                            statusElem.textContent = 'Thinking about your response' + dots;
                        }
                    }
                } else {
                    // If indicator was removed, stop the animation
                    clearInterval(thinkingAnimation);
                }
            }, 500);
            
            // Store the interval ID so we can clear it when we get a response
            window.thinkingAnimation = thinkingAnimation;
            
            updateStatus('AI is thinking about what to ask next based on your response...');
        } else if (data.status === 'speaking') {
            // Clear any thinking animation
            if (window.thinkingAnimation) {
                clearInterval(window.thinkingAnimation);
                window.thinkingAnimation = null;
            }
            
            showTypingIndicator('Preparing to speak...');
            updateStatus('AI is preparing the audio response...');
        } else if (data.status === 'generating') {
            showTypingIndicator('Generating response...');
            updateStatus('AI is generating a response to your answer...');
        }
    });
    
    socket.on('ai_message', function(data) {
        if (DEBUG) console.log('Received AI message:', data);
        
        // Clear any thinking animation
        if (window.thinkingAnimation) {
            clearInterval(window.thinkingAnimation);
            window.thinkingAnimation = null;
        }
        
        // Clear any response timeout
        clearResponseTimeout();
        
        // Clear the typing indicator
        const typingIndicator = document.getElementById('ai-typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
        
        // Add AI message to the conversation
        addMessageToConversation('AI Interviewer', data.message, 'ai');
        
        // Play audio if available
        if (data.audio_url) {
            playAudioWithMessage(data.audio_url, data.message);
        } else {
            // Use browser TTS as fallback
            useBrowserTTS(data.message);
        }
        
        // If this is the final message, handle it specially
        if (data.is_final) {
            handleFinalAssessment(data);
            return;
        }
        
        // Re-enable controls after AI is done speaking
        holdToSpeakButton.disabled = false;
        responseText.disabled = false;
        sendTextButton.disabled = false;
        
        // Update status
        updateStatus('Your turn to speak. Hold the microphone button or type your response.');
        
        // Clear any pending timeout
        clearAiResponseTimeout();
    });
}

// Send text response from text input
function sendTextResponse() {
    // Check if interview is active and we have text to send
    if (!isInterviewActive || !responseText.value.trim()) {
        return;
    }

    const text = responseText.value.trim();
    
    // Add to conversation and clear input
    addMessageToConversation('You', text, 'candidate');
    responseText.value = '';
    
    // Disable controls during processing
    holdToSpeakButton.disabled = true;
    responseText.disabled = true;
    sendTextButton.disabled = true;
    
    // Show processing indicator
    clearThinkingAnimation();
    showTypingIndicator('Processing your response...');
    startThinkingAnimation();
    
    // Update status
    updateStatus('Processing your response. Please wait for AI to respond...');
    
    // Set timeout for slow responses - increased for Llama 3 model
    setResponseTimeout(100000); // 100 seconds timeout
    
    // Send to server
    socket.emit('candidate_speech', {
        interview_id: interviewId,
        text: text,
        quick_mode: quickModeEnabled
    });
}

// Start thinking animation with dots
function startThinkingAnimation() {
    // Clear existing animation if any
    clearThinkingAnimation();
    
    // Set up animation
    dotCount = 0;
    window.thinkingAnimation = setInterval(() => {
        dotCount = (dotCount % 6) + 1;
        dots = '.'.repeat(dotCount);
        
        const typingIndicator = document.getElementById('ai-typing-indicator');
        if (typingIndicator) {
            const contentElem = typingIndicator.querySelector('.message-content');
            if (contentElem) {
                const statusElem = contentElem.querySelector('.status-text');
                if (statusElem) {
                    statusElem.textContent = 'Processing your response' + dots;
                }
            }
        } else {
            clearThinkingAnimation();
        }
    }, 500);
}

// Clear thinking animation
function clearThinkingAnimation() {
    if (window.thinkingAnimation) {
        clearInterval(window.thinkingAnimation);
        window.thinkingAnimation = null;
    }
}

// Set timeout for response and show error if needed
function setResponseTimeout(ms) {
    clearResponseTimeout();
    
    window.responseTimeout = setTimeout(() => {
        clearThinkingAnimation();
        
        // Remove typing indicator
        const typingIndicator = document.getElementById('ai-typing-indicator');
        if (typingIndicator) typingIndicator.remove();
        
        // Show error message
        addMessageToConversation('AI Interviewer', 
            'I apologize for the delay. There seems to be a technical issue. Please try again.',
            'ai error');
            
        // Re-enable controls
        holdToSpeakButton.disabled = false;
        responseText.disabled = false;
        sendTextButton.disabled = false;
        
        updateStatus('Ready for your response.');
    }, ms);
}

// Start the interview
function startInterview() {
    if (isInterviewActive) {
        console.log("Interview already active, ignoring start request");
        return;
    }
    
    console.log("Starting interview:", interviewId);
    
    // Join the interview room
    socket.emit('join_interview', {
        interview_id: interviewId
    });
    
    console.log("Emitted join_interview event");
    
    // Set a timeout to detect if the AI doesn't respond
    setAiResponseTimeout();
    
    // Start capturing audio/video
    console.log("Requesting media permissions");
    navigator.mediaDevices.getUserMedia({ audio: true, video: true })
        .then(function(stream) {
            console.log("Media access granted");
            localStream = stream;
            localVideo.srcObject = stream;
            
            // Setup media recorder for audio
            setupMediaRecorder(stream);
            
            // Update UI
            isInterviewActive = true;
            startButton.disabled = true;
            endButton.disabled = false;
            toggleMicButton.disabled = false;
            toggleVideoButton.disabled = false;
            holdToSpeakButton.disabled = false;
            responseText.disabled = false;
            sendTextButton.disabled = false;
            
            updateStatus('Interview started. The AI interviewer will ask questions shortly.');
        })
        .catch(function(err) {
            console.error('Error accessing media devices:', err);
            
            // If media access fails, still allow text-based interview
            isInterviewActive = true;
            startButton.disabled = true;
            endButton.disabled = false;
            responseText.disabled = false;
            sendTextButton.disabled = false;
            
            updateStatus('Error accessing your camera and microphone. You can still participate using text responses.');
        });
}

// Setup media recorder for audio capture
function setupMediaRecorder(stream) {
    const audioStream = new MediaStream(stream.getAudioTracks());
    mediaRecorder = new MediaRecorder(audioStream);
    
    mediaRecorder.ondataavailable = function(event) {
        audioChunks.push(event.data);
    };
    
    mediaRecorder.onstop = function() {
        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
        sendAudioToServer(audioBlob);
        audioChunks = [];
    };
}

// Start recording when user holds the button
function startRecording() {
    if (!mediaRecorder || !isInterviewActive || isSpeaking) return;
    
    // Clear any existing audio chunks
    audioChunks = [];
    
    // Record start time
    recordingStartTime = new Date().getTime();
    transcriptionReceived = false;
    
    // Start recording
    mediaRecorder.start();
    
    // Update UI
    holdToSpeakButton.classList.add('recording');
    updateStatus('Recording... (Keep holding to speak)');
}

// Stop recording when user releases the button
function stopRecording() {
    if (!mediaRecorder || mediaRecorder.state !== 'recording') return;
    
    // Stop recording
    mediaRecorder.stop();
    
    // Record end time
    recordingEndTime = new Date().getTime();
    
    // Calculate duration
    const recordingDuration = (recordingEndTime - recordingStartTime) / 1000;
    console.log(`Recording duration: ${recordingDuration.toFixed(2)}s`);
    
    // Update UI immediately to acknowledge user's response
    holdToSpeakButton.classList.remove('recording');
    
    // Add a temporary placeholder for the user's response
    addMessageToConversation('You', '...', 'candidate');
    
    // Update status to show the AI is preparing a response
    updateStatus('Your response has been recorded and is being processed...');
    
    // Show a typing indicator for the AI
    showTypingIndicator('Recording saved, now transcribing your audio. AI will respond with audio shortly...');
    
    // Disable the button temporarily to prevent multiple submissions
    holdToSpeakButton.disabled = true;
    responseText.disabled = true;
    sendTextButton.disabled = true;
}

// Show a typing indicator to indicate the AI is processing
function showTypingIndicator(statusMessage) {
    // Remove any existing typing indicator
    const existingIndicator = document.getElementById('ai-typing-indicator');
    if (existingIndicator) {
        existingIndicator.remove();
    }
    
    const indicatorElement = document.createElement('div');
    indicatorElement.className = 'message message-ai typing-indicator';
    indicatorElement.id = 'ai-typing-indicator';
    
    const headerElement = document.createElement('div');
    headerElement.className = 'message-header';
    headerElement.textContent = 'AI Interviewer';
    
    const contentElement = document.createElement('div');
    contentElement.className = 'message-content';
    contentElement.innerHTML = '<span class="dot"></span><span class="dot"></span><span class="dot"></span>';
    
    // Add status message if provided
    if (statusMessage) {
        const statusText = document.createElement('div');
        statusText.className = 'status-text';
        statusText.textContent = statusMessage;
        contentElement.appendChild(statusText);
    }
    
    indicatorElement.appendChild(headerElement);
    indicatorElement.appendChild(contentElement);
    
    conversationLog.appendChild(indicatorElement);
    
    // Scroll to bottom
    conversationLog.scrollTop = conversationLog.scrollHeight;
}

// Start recording in intervals (old method, now unused)
function startRecordingInterval() {
    // This method is no longer used, as we now use the Hold to Speak button
    // But we'll keep it for backward compatibility
}

// Send audio to the server
function sendAudioToServer(audioBlob) {
    // Convert blob to base64
    const reader = new FileReader();
    reader.readAsDataURL(audioBlob);
    reader.onloadend = function() {
        const base64Audio = reader.result;
        
        // Send to server via Socket.IO
        socket.emit('candidate_speech', {
            interview_id: interviewId,
            audio: base64Audio,
            quick_mode: quickModeEnabled  // Include quick mode flag
        });
    };
}

// End the interview
function endInterview() {
    if (!isInterviewActive) return;
    
    // Stop recording
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
    }
    
    if (recordingInterval) {
        clearInterval(recordingInterval);
    }
    
    // Stop media streams
    if (localStream) {
        localStream.getTracks().forEach(track => track.stop());
    }
    
    // Update UI
    isInterviewActive = false;
    startButton.disabled = false;
    endButton.disabled = true;
    toggleMicButton.disabled = true;
    toggleVideoButton.disabled = true;
    responseText.disabled = true;
    sendTextButton.disabled = true;
    
    updateStatus('Interview ended. Thank you for participating.');
    
    // Send "end interview" message by simulating the user saying it
    socket.emit('candidate_speech', {
        interview_id: interviewId,
        text: "end the interview"
    });
}

// Toggle microphone
function toggleMicrophone() {
    if (!localStream) return;
    
    const audioTracks = localStream.getAudioTracks();
    if (audioTracks.length === 0) return;
    
    const isEnabled = audioTracks[0].enabled;
    audioTracks[0].enabled = !isEnabled;
    
    // Update button text
    toggleMicButton.innerHTML = isEnabled ? 
        '<i class="bi bi-mic-mute-fill"></i> Unmute' : 
        '<i class="bi bi-mic-fill"></i> Mute';
}

// Toggle video
function toggleVideo() {
    if (!localStream) return;
    
    const videoTracks = localStream.getVideoTracks();
    if (videoTracks.length === 0) return;
    
    const isEnabled = videoTracks[0].enabled;
    videoTracks[0].enabled = !isEnabled;
    
    // Update button text
    toggleVideoButton.innerHTML = isEnabled ? 
        '<i class="bi bi-camera-video-off-fill"></i> Turn On Camera' : 
        '<i class="bi bi-camera-video-fill"></i> Turn Off Camera';
}

// Connect to LiveKit
function connectToLiveKit() {
    // Initialize LiveKit client if available
    if (typeof LivekitClient !== 'undefined') {
        // ... LiveKit integration code
    }
}

// Add message to conversation
function addMessageToConversation(sender, message, role) {
    const messageElement = document.createElement('div');
    messageElement.className = `message message-${role}`;
    
    const headerElement = document.createElement('div');
    headerElement.className = 'message-header';
    headerElement.textContent = sender;
    
    const contentElement = document.createElement('div');
    contentElement.className = 'message-content';
    contentElement.textContent = message;
    
    messageElement.appendChild(headerElement);
    messageElement.appendChild(contentElement);
    
    conversationLog.appendChild(messageElement);
    
    // Scroll to bottom
    conversationLog.scrollTop = conversationLog.scrollHeight;
}

// Play audio with message as fallback
function playAudioWithMessage(url, message) {
    const audio = new Audio(url);
    
    // Store the message for fallback
    audio.dataset.message = message;
    
    // Find or create status indicator for audio playback
    let audioStatusDiv = document.getElementById('audio-status');
    if (!audioStatusDiv) {
        audioStatusDiv = document.createElement('div');
        audioStatusDiv.id = 'audio-status';
        audioStatusDiv.className = 'audio-status';
        audioStatusDiv.innerHTML = '<i class="bi bi-volume-up"></i> <span>Audio response playing...</span>';
        statusArea.appendChild(audioStatusDiv);
    } else {
        audioStatusDiv.style.display = 'block';
    }
    
    // Add loadeddata event to know when audio is ready
    audio.addEventListener('loadeddata', function() {
        console.log('Server audio loaded successfully');
        audioStatusDiv.querySelector('span').textContent = 'Audio response playing...';
    });
    
    // Error handling with fallback to browser TTS
    audio.addEventListener('error', function(e) {
        console.error('Error loading audio from server:', e);
        audioStatusDiv.querySelector('span').textContent = 'Audio failed, using browser speech...';
        useBrowserTTS(message || "I couldn't play the audio for this message");
    });
    
    // When audio ends, update status and re-enable input
    audio.addEventListener('ended', function() {
        console.log('Server audio playback complete');
        audioStatusDiv.style.display = 'none';
        if (isInterviewActive) {
            updateStatus('Your turn to respond...');
            responseText.disabled = false;
            sendTextButton.disabled = false;
            holdToSpeakButton.disabled = false;
            isSpeaking = false;
        }
    });
    
    // Try to play the audio
    audio.play().catch(err => {
        console.error('Error playing audio:', err);
        audioStatusDiv.querySelector('span').textContent = 'Audio playback failed, using text-to-speech...';
        // Try browser TTS as fallback
        useBrowserTTS(message || "I couldn't play the audio for this message");
    });
}

// Use browser's text-to-speech as a fallback
function useBrowserTTS(message) {
    console.log('Using browser TTS for:', message);
    
    // Find or create status indicator for audio playback
    let audioStatusDiv = document.getElementById('audio-status');
    if (!audioStatusDiv) {
        audioStatusDiv = document.createElement('div');
        audioStatusDiv.id = 'audio-status';
        audioStatusDiv.className = 'audio-status';
        audioStatusDiv.innerHTML = '<i class="bi bi-volume-up"></i> <span>Browser speech playing...</span>';
        statusArea.appendChild(audioStatusDiv);
    } else {
        audioStatusDiv.style.display = 'block';
        audioStatusDiv.querySelector('span').textContent = 'Browser speech playing...';
    }
    
    // Check if the browser supports speech synthesis
    if ('speechSynthesis' in window) {
        // Cancel any ongoing speech first to prevent repetition
        window.speechSynthesis.cancel();
        
        // Create a new speech synthesis utterance
        const utterance = new SpeechSynthesisUtterance(message);
        
        // Optional: Set voice properties
        utterance.rate = 1.0; // Speed - normal
        utterance.pitch = 1.0; // Pitch - normal
        utterance.volume = 1.0; // Volume - max
        
        // Handle voice selection - getVoices may return empty initially
        const setVoice = () => {
            const voices = window.speechSynthesis.getVoices();
            if (voices.length > 0) {
                const englishVoices = voices.filter(voice => voice.lang.startsWith('en-'));
                if (englishVoices.length > 0) {
                    // Prefer voices with "Google" or "Microsoft" in the name (usually higher quality)
                    const preferredVoice = englishVoices.find(voice => 
                        voice.name.includes('Google') || voice.name.includes('Microsoft'));
                    
                    utterance.voice = preferredVoice || englishVoices[0];
                    console.log('Using voice:', utterance.voice?.name || 'Default voice');
                }
            }
        };
        
        // Try to set voice immediately
        setVoice();
        
        // If voices aren't loaded yet, listen for the voiceschanged event
        if (window.speechSynthesis.onvoiceschanged !== undefined) {
            window.speechSynthesis.onvoiceschanged = setVoice;
        }
        
        // Prevent speech synthesis from getting stuck
        utterance.onend = () => {
            console.log('Browser TTS finished');
            // Some browsers have a bug where they don't resume properly
            window.speechSynthesis.cancel();
            
            // Hide audio status
            audioStatusDiv.style.display = 'none';
            
            // Update status and re-enable text input when speech ends
            if (isInterviewActive) {
                updateStatus('Your turn to respond...');
                responseText.disabled = false;
                sendTextButton.disabled = false;
                holdToSpeakButton.disabled = false;
                isSpeaking = false;
            }
        };
        
        utterance.onstart = () => {
            console.log('Browser TTS started');
            // Update audio status
            audioStatusDiv.querySelector('span').textContent = 'Browser speech playing...';
            
            // Some browsers pause TTS after ~15 seconds, this keeps it going
            const checkAndResume = setInterval(() => {
                if (window.speechSynthesis.paused) {
                    window.speechSynthesis.resume();
                }
                
                // Clear interval when speech is done
                if (!window.speechSynthesis.speaking) {
                    clearInterval(checkAndResume);
                }
            }, 1000);
        };
        
        utterance.onerror = (e) => {
            console.error('Browser TTS error:', e);
            // Hide audio status
            audioStatusDiv.style.display = 'none';
            
            // Re-enable input on error
            if (isInterviewActive) {
                updateStatus('Your turn to respond...');
                responseText.disabled = false;
                sendTextButton.disabled = false;
                holdToSpeakButton.disabled = false;
                isSpeaking = false;
            }
        };
        
        // Speak the text
        window.speechSynthesis.speak(utterance);
    } else {
        console.warn('Browser does not support speech synthesis');
        // Hide audio status
        audioStatusDiv.style.display = 'none';
        
        alert('Your browser does not support text-to-speech. Please read the AI messages in the conversation log.');
        
        // Re-enable input if no TTS support
        if (isInterviewActive) {
            updateStatus('Your turn to respond...');
            responseText.disabled = false;
            sendTextButton.disabled = false;
            isSpeaking = false;
        }
    }
}

// Handle final assessment
function handleFinalAssessment(data) {
    updateStatus(`Interview completed. You received a rating of ${data.rating}/10.`);
    
    // If on the results page, reload to show final results
    if (typeof interviewCompleted !== 'undefined' && !interviewCompleted) {
        setTimeout(() => {
            window.location.reload();
        }, 5000);
    }
}

// Update status area
function updateStatus(message) {
    console.log("Status update:", message);
    if (statusArea) {
        statusArea.textContent = message;
    } else {
        console.error("Status area element not found");
    }
}

// Check if the AI is responding
function setAiResponseTimeout() {
    clearAiResponseTimeout(); // Clear any existing timeout
    
    if (DEBUG) console.log('Setting AI response timeout');
    
    // If we don't get a response in 10 seconds, use a fallback
    aiResponseTimeout = setTimeout(() => {
        console.warn('AI response timeout - using fallback');
        updateStatus('Waiting for AI response...');
        
        // Use browser TTS to ask a starting question
        const fallbackMessage = "Welcome to your interview! I'll be asking you some questions about your experience and skills. Let's start: Could you tell me about your background and why you're interested in this position?";
        
        // Add the fallback message to the conversation
        addMessageToConversation('AI Interviewer', fallbackMessage, 'ai');
        
        // Use browser TTS
        useBrowserTTS(fallbackMessage);
        
        // Enable UI elements to allow the user to respond
        if (!isInterviewActive) {
            isInterviewActive = true;
            startButton.disabled = true;
            endButton.disabled = false;
            responseText.disabled = false;
            sendTextButton.disabled = false;
            
            updateStatus('Interview started. You can now respond to the question.');
        }
    }, AI_RESPONSE_TIMEOUT_MS);
}

// Clear the AI response timeout
function clearAiResponseTimeout() {
    if (aiResponseTimeout) {
        clearTimeout(aiResponseTimeout);
        aiResponseTimeout = null;
    }
}

// Helper function to clear any pending response timeout
function clearResponseTimeout() {
    if (window.responseTimeout) {
        clearTimeout(window.responseTimeout);
        window.responseTimeout = null;
    }
} 