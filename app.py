from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import json

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")  # This allows any origin

# Helper functions to read and write JSON data


def read_data():
    """Reads game data from the JSON file."""
    with open('game_data.json', 'r') as file:
        return json.load(file)


def write_data(data):
    """Writes updated game data to the JSON file."""
    with open('game_data.json', 'w') as file:
        json.dump(data, file, indent=4)


@app.route('/')
def home():
    return render_template('game.html')


@app.route('/admin')
def admin_page():
    return render_template('admin.html')


@app.route('/get_game_state')
def get_game_state():
    """Retrieves the current game state, including answers and votes."""
    data = read_data()
    # Prepend the path and extension to the avatar field
    for answer in data['answers']:
        # Check if the avatar doesn't already have a .png extension
        if not answer['avatar'].endswith('.png'):
            answer['avatar'] = answer['avatar'] + ".png"

    return jsonify(data)


@app.route('/toggle_answer_visibility', methods=['POST'])
def toggle_answer_visibility():
    """Toggles the visibility of a specific answer."""
    data = read_data()
    answer_id = request.json.get('answer_id')

    # Find the answer by ID and toggle the 'visible' flag
    for answer in data['answers']:
        if answer['id'] == answer_id:
            answer['visible'] = not answer['visible']  # Toggle visibility
            break

    write_data(data)

    # Emit the updated visibility state to clients
    socketio.emit('answer_visibility_changed', {
                  'answer_id': answer_id, 'visible': not answer['visible']})

    return jsonify({'success': True, 'answer_id': answer_id, 'visible': not answer['visible']})


@app.route('/mark_correct', methods=['POST'])
def mark_correct():
    data = request.get_json()
    answer_id = data.get('answer_id')
    answers = data.get('answers')

    # Find the answer by ID and toggle the 'is_correct' flag
    for answer in answers:
        if answer['id'] == answer_id:
            if 'is_correct' not in answer:
                # Initialize 'is_correct' if it doesn't exist
                answer['is_correct'] = False
            # Toggle the 'is_correct' flag
            answer['is_correct'] = not answer['is_correct']
            break

    # Update the game data without altering 'reveal'
    full_data = read_data()
    full_data['answers'] = answers  # Update answers only
    write_data(full_data)

    # Emit the updated answers to clients
    socketio.emit('updated_answers', {'answers': answers})

    return jsonify({'success': True, 'answers': answers})


@app.route('/get_questions')
def get_questions():
    """Fetches all questions for the admin to choose the next question."""
    data = read_data()
    questions = data.get("questions", [])
    return jsonify({"questions": questions})


@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    """Handles the submission of answers along with user information and avatar."""
    answer_text = request.json['answer']
    user_id = request.json['user_id']
    question_id = request.json['question_id']
    avatar = request.json['avatar']

    data = read_data()
    answer_id = len(data['answers']) + 1
    data['answers'].append({
        "id": answer_id,
        "question_id": question_id,
        "text": answer_text,
        "user_id": user_id,
        "avatar": avatar,
        "votes": [],  # Initialize empty vote list for each answer
        "visible": False
    })

    write_data(data)
    return jsonify(success=True)


@app.route('/vote', methods=['POST'])
def vote():
    """Handles voting for an answer, ensuring unique votes by each user."""
    data = request.get_json()
    answer_id = data.get('answer_id')
    user_id = data.get('user_id')
    avatar = data.get('avatar')  # Include avatar in the request data

    # Load the latest game data
    game_data = read_data()
    for answer in game_data['answers']:
        if answer['id'] == int(answer_id):
            # Ensure each user votes only once
            if not any(vote['user_id'] == user_id for vote in answer['votes']):
                # Add the user_id and avatar to the votes list
                answer['votes'].append({"user_id": user_id, "avatar": avatar})
                write_data(game_data)  # Save updated data
                return jsonify({"success": True}), 200

    return jsonify({"success": False, "message": "Failed to vote"}), 400


@app.route('/add_question', methods=['POST'])
def add_question():
    """Adds a new question."""
    data = read_data()
    new_question_text = request.json.get('text')

    if new_question_text:
        new_question_id = max(
            q['id'] for q in data['questions']) + 1 if data['questions'] else 1
        data['questions'].append(
            {"id": new_question_id, "text": new_question_text})
        write_data(data)
        return jsonify(success=True)
    return jsonify(success=False)


@app.route('/remove_question', methods=['POST'])
def remove_question():
    """Removes a question by ID."""
    data = read_data()
    question_id = request.json.get('id')

    data['questions'] = [q for q in data['questions'] if q['id'] != question_id]
    write_data(data)

    return jsonify(success=True)


@app.route('/clear_data', methods=['POST'])
def clear_data():
    """Resets the game data to an initial empty state."""
    # Read the current data
    data = read_data()

    # Check if there are no questions in the current data
    if not data.get('questions'):
        # If no questions, set the initial data with default questions
        initial_data = {
            "questions": [
                {"id": 1, "text": "What is your favorite color?"},
                {"id": 2, "text": "What is your favorite animal?"}
            ],
            "answers": [],
            "votes": [],
            "reveal": False
        }
        write_data(initial_data)
    else:
        # If there are existing questions, reorder their IDs
        reordered_questions = [
            {"id": i + 1, "text": question['text']}
            for i, question in enumerate(data['questions'])
        ]

        # Write the reordered data
        initial_data = {
            "questions": reordered_questions,  # Reordered questions
            "answers": [],
            "votes": [],
            "reveal": False
        }
        write_data(initial_data)

    # Emit the reset event to the clients
    socketio.emit(
        'game_reset', {'message': 'Game has been reset and all data cleared.'})

    return jsonify(success=True)


@app.route('/clear_votes', methods=['POST'])
def clear_votes():
    """Clears all votes from each answer."""
    data = read_data()
    for answer in data['answers']:
        answer['votes'] = []  # Clear votes
    write_data(data)
    return jsonify(success=True)


@app.route('/set_next_question', methods=['POST'])
def set_next_question():
    """Allows admin to set the next question."""
    question_id = int(request.json['question_id']
                      )  # Convert question_id to integer

    # Load data and update the current question
    data = read_data()
    selected_question = next(
        (q for q in data['questions'] if q['id'] == question_id), None)

    if selected_question:
        data['current_question'] = selected_question
        write_data(data)

        # Clear votes for the new question
        clear_votes()  # Call the clear_votes function here

        # Emit event to update clients
        socketio.emit('next_question', {'question': selected_question})
        return jsonify(success=True, question=selected_question)

    return jsonify(success=False, message="Question not found"), 404


@app.route('/reveal_votes_admin', methods=['POST'])
def reveal_votes_admin():
    """Admin endpoint to reveal all votes for each answer."""
    data = read_data()
    data['reveal'] = True  # Set reveal flag

    write_data(data)

    # Prepare data to broadcast to clients, include 'is_correct' flag
    revealed_answers = [
        {
            "text": answer['text'],
            "votedBy": ", ".join(answer['votes']),
            # Add 'is_correct' field
            "is_correct": answer.get('is_correct', False)
        }
        for answer in data['answers'] if 'votes' in answer
    ]

    socketio.emit('reveal_votes', {
                  'reveal': True, 'answers': revealed_answers})
    return jsonify(success=True)


# Socket events for client connection handling


@socketio.on('connect')
def handle_connect():
    print("Client connected")


@socketio.on('disconnect')
def handle_disconnect():
    print("Client disconnected")


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
