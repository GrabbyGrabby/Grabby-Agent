// State Management
let sessions = JSON.parse(localStorage.getItem('grabby_sessions')) || [];
let currentSessionId = localStorage.getItem('grabby_current_session') || null;

const messagesContainer = document.getElementById('messages-container');
const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const sessionList = document.getElementById('session-list');
const newChatBtn = document.getElementById('new-chat-btn');
const syncDnsBtn = document.getElementById('sync-dns-btn');
const currentSessionTitle = document.getElementById('current-session-title');
const systemStatus = document.getElementById('system-status');

// Initialize Application
function init() {
    if (sessions.length === 0) {
        createNewSession('default-session');
    } else if (!currentSessionId) {
        currentSessionId = sessions[0].id;
    }
    
    renderSessions();
    switchSession(currentSessionId);
    
    // Set up form submission
    chatForm.addEventListener('submit', handleSendMessage);
    newChatBtn.addEventListener('click', () => {
        const id = 'session-' + Date.now();
        createNewSession(id);
    });
    syncDnsBtn.addEventListener('click', triggerDnsSync);
}

// Session Functions
function createNewSession(id) {
    const newSession = {
        id: id,
        name: `Session ${sessions.length + 1}`,
        messages: []
    };
    sessions.push(newSession);
    saveSessions();
    renderSessions();
    switchSession(id);
}

function saveSessions() {
    localStorage.setItem('grabby_sessions', JSON.stringify(sessions));
    localStorage.setItem('grabby_current_session', currentSessionId);
}

function renderSessions() {
    sessionList.innerHTML = '';
    sessions.forEach(session => {
        const li = document.createElement('li');
        li.className = `session-item ${session.id === currentSessionId ? 'active' : ''}`;
        li.innerHTML = `
            <span>${session.name}</span>
            <span class="delete-session" data-id="${session.id}">&times;</span>
        `;
        
        li.addEventListener('click', (e) => {
            if (e.target.classList.contains('delete-session')) {
                e.stopPropagation();
                deleteSession(session.id);
            } else {
                switchSession(session.id);
            }
        });
        sessionList.appendChild(li);
    });
}

function switchSession(id) {
    currentSessionId = id;
    localStorage.setItem('grabby_current_session', currentSessionId);
    
    const activeSession = sessions.find(s => s.id === id);
    if (activeSession) {
        currentSessionTitle.textContent = `Session: ${activeSession.name}`;
        renderMessages(activeSession.messages);
    }
    
    renderSessions();
}

function deleteSession(id) {
    sessions = sessions.filter(s => s.id !== id);
    if (sessions.length === 0) {
        createNewSession('default-session');
    } else {
        if (currentSessionId === id) {
            currentSessionId = sessions[0].id;
        }
        saveSessions();
        renderSessions();
        switchSession(currentSessionId);
    }
}

// Chat rendering functions
function renderMessages(messages) {
    messagesContainer.innerHTML = '';
    
    if (messages.length === 0) {
        messagesContainer.innerHTML = `
            <div class="message system-message">
                <div class="msg-bubble">
                    This is a fresh session. Send a message to start reasoning!
                </div>
            </div>
        `;
        return;
    }
    
    messages.forEach(msg => {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${msg.role}-message`;
        msgDiv.innerHTML = `
            <div class="msg-bubble">${msg.content}</div>
        `;
        messagesContainer.appendChild(msgDiv);
    });
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Handle sending message
async function handleSendMessage(e) {
    e.preventDefault();
    const text = userInput.value.trim();
    if (!text) return;
    
    // Add user message to state
    const currentSession = sessions.find(s => s.id === currentSessionId);
    if (!currentSession) return;
    
    currentSession.messages.push({ role: 'user', content: text });
    renderMessages(currentSession.messages);
    saveSessions();
    
    userInput.value = '';
    setLoadingState(true);
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                thread_id: currentSessionId
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Add agent response
        currentSession.messages.push({ role: 'agent', content: data.reply });
        renderMessages(currentSession.messages);
        saveSessions();
        
    } catch (err) {
        console.error('Error fetching chat response:', err);
        currentSession.messages.push({ 
            role: 'system', 
            content: `Error: Unable to get a reply. Fallback chain failed. details: ${err.message}` 
        });
        renderMessages(currentSession.messages);
    } finally {
        setLoadingState(false);
    }
}

function setLoadingState(isLoading) {
    if (isLoading) {
        sendBtn.disabled = true;
        sendBtn.innerHTML = '<span>Reasoning...</span>';
        systemStatus.innerHTML = '<span class="status-indicator pulsing"></span> Agent is thinking...';
    } else {
        sendBtn.disabled = false;
        sendBtn.innerHTML = '<span>Send</span>';
        systemStatus.innerHTML = '<span class="status-indicator online"></span> Fallback Agent Engine: Active';
    }
}

// Trigger DNS record sync
async function triggerDnsSync() {
    syncDnsBtn.disabled = true;
    syncDnsBtn.textContent = 'Syncing...';
    try {
        const response = await fetch('/api/dns-sync', { method: 'POST' });
        const data = await response.json();
        if (data.status === 'success') {
            alert('DNS record synced successfully!');
        } else {
            alert('DNS sync completed, but it might have been skipped. Check backend logs.');
        }
    } catch (err) {
        alert(`Error syncing DNS: ${err.message}`);
    } finally {
        syncDnsBtn.disabled = false;
        syncDnsBtn.textContent = 'Sync DNS';
    }
}

// Start
init();
