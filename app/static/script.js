/**
 * Common JavaScript functions for the AI Interviewer application
 */

// Format date for display
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString();
}

// Handle API errors
function handleApiError(error) {
    console.error('API Error:', error);
    alert('An error occurred while communicating with the server. Please try again.');
}

// Copy text to clipboard
function copyToClipboard(text) {
    const tempInput = document.createElement('input');
    tempInput.value = text;
    document.body.appendChild(tempInput);
    tempInput.select();
    document.execCommand('copy');
    document.body.removeChild(tempInput);
}

// Show loading indicator
function showLoading(element, message = 'Loading...') {
    if (!element) return;
    
    // Save original content
    element.dataset.originalContent = element.innerHTML;
    
    // Create spinner
    const spinner = document.createElement('span');
    spinner.className = 'spinner-border spinner-border-sm me-2';
    spinner.setAttribute('role', 'status');
    spinner.setAttribute('aria-hidden', 'true');
    
    // Set loading content
    element.innerHTML = '';
    element.appendChild(spinner);
    element.appendChild(document.createTextNode(' ' + message));
    
    // Disable the element if it's a button
    if (element.tagName === 'BUTTON') {
        element.disabled = true;
    }
}

// Hide loading indicator
function hideLoading(element) {
    if (!element || !element.dataset.originalContent) return;
    
    // Restore original content
    element.innerHTML = element.dataset.originalContent;
    
    // Re-enable the element if it's a button
    if (element.tagName === 'BUTTON') {
        element.disabled = false;
    }
    
    // Clean up
    delete element.dataset.originalContent;
}

// Format transcript message for display
function formatTranscriptMessage(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${message.role}`;
    
    const headerDiv = document.createElement('div');
    headerDiv.className = 'message-header';
    headerDiv.textContent = `${message.role.toUpperCase()} - ${formatDate(message.timestamp)}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = message.content;
    
    messageDiv.appendChild(headerDiv);
    messageDiv.appendChild(contentDiv);
    
    return messageDiv;
}

// Export functions for use in other scripts
window.aiInterviewer = {
    formatDate,
    handleApiError,
    copyToClipboard,
    showLoading,
    hideLoading,
    formatTranscriptMessage
}; 