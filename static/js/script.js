// static/script.js

// Connect to the server using Socket.IO
const socket = io();

// Submit an answer
function submitAnswer() {
    const answer = document.getElementById('answer-input').value;
    const userId = 'user123';  // Example user ID, you may want to dynamically assign this
    const questionId = 1;      // Example question ID
    const avatar = 'avatar1';  // Example avatar, you can replace this dynamically with selected avatar

    fetch('/submit_answer', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ answer, user_id: userId, question_id: questionId, avatar })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Answer is successfully submitted; no need to reload, as it's handled in real-time
        }
    });
}

// Vote for an answer
function voteAnswer(answerId) {
    const userId = 'user456';  // Example user ID, you may want to dynamically assign this

    fetch('/vote', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ answer_id: answerId, user_id: userId })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert("Vote submitted successfully!");
        }
    });
}

// Listen for new answers submitted in real-time
socket.on('new_answer', (answers) => {
    loadAnswers(answers);
});

// Listen for new votes submitted in real-time
socket.on('new_vote', (voteData) => {
    updateVotes(voteData.answer_id, voteData.votes);
});

// Listen for game reset
socket.on('game_reset', (data) => {
    alert(data.message);
    loadAnswers([]);  // Clear answers from the UI
});

// Listen for votes cleared
socket.on('clear_votes', (data) => {
    alert(data.message);
    resetVotes();  // Reset votes in the UI
});

// Listen for revealed answers
socket.on('reveal_votes', (data) => {
    if (data.reveal) {
        displayRevealedAnswers(data.answers);
    }
});

// Load answers when the page loads
function loadAnswers(answers) {
    const answersList = document.getElementById('answers-list');
    answersList.innerHTML = '';
    
    answers.forEach(answer => {
        const answerItem = document.createElement('div');
        answerItem.textContent = `${answer.user_id}: ${answer.text} (Votes: ${answer.votes.length})`;
        
        // Add voting button if not already voted
        const voteButton = document.createElement('button');
        voteButton.textContent = "Vote";
        voteButton.onclick = () => voteAnswer(answer.id);
        answerItem.appendChild(voteButton);

        answersList.appendChild(answerItem);
    });
}

// Update the votes for an answer
function updateVotes(answerId, votes) {
    const answersList = document.getElementById('answers-list');
    const answerDiv = Array.from(answersList.children).find(child => child.textContent.includes(answerId));

    if (answerDiv) {
        answerDiv.textContent = `${answerDiv.textContent.split('(')[0]} (Votes: ${votes.length})`;
    }
}

// Reset votes in the UI
function resetVotes() {
    const answersList = document.getElementById('answers-list');
    Array.from(answersList.children).forEach(child => {
        child.textContent = child.textContent.split('(')[0] + ' (Votes: 0)';
    });
}

// Display revealed answers in real-time (admin view)
function displayRevealedAnswers(answers) {
    const revealSection = document.getElementById('reveal-section');
    revealSection.innerHTML = '';

    answers.forEach(answer => {
        const answerDiv = document.createElement('div');
        answerDiv.textContent = `${answer.text} (Voted By: ${answer.votedBy})`;
        revealSection.appendChild(answerDiv);
    });    
}

// Load answers on page load
window.onload = function() {
    fetch('/get_game_state')
        .then(response => response.json())
        .then(data => {
            loadAnswers(data.answers);
        });
};
