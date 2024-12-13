from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from flask_socketio import SocketIO, emit
import random
import json
import os
from datetime import timedelta
from functools import wraps
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
# Load configuration from environment variables
app.config.update(
    SECRET_KEY=os.getenv('SECRET_KEY', 'fallback_secret_key_for_development'),
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)

# Constants with environment variables
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
USER_PASSWORD = os.getenv('USER_PASSWORD')

# Validate that critical environment variables are set
if not ADMIN_PASSWORD or not USER_PASSWORD:
    raise ValueError("Critical environment variables are not set. Check your .env file.")

# Configure CORS properly for production
socketio = SocketIO(app, 
    cors_allowed_origins="*",  # Allow all origins in development
    ping_timeout=60,
    ping_interval=25,
    async_mode='threading'
)

# Custom decorator for requiring authentication
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Helper function for safe file operations
def safe_file_operation(operation, *args, **kwargs):
    try:
        return operation(*args, **kwargs)
    except (IOError, json.JSONDecodeError) as e:
        app.logger.error(f"File operation error: {str(e)}")
        return None

@app.route('/')
@login_required
def home():
    if not session.get('username'):
        return redirect(url_for('userlogin'))
    
    avatar = session.get('avatar')
    return render_template('game.html', username=session['username'], avatar=avatar)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        
        if not password:
            return jsonify({"success": False, "error": "Password is required"}), 400
            
        if password == USER_PASSWORD:
            session.permanent = True  # Make session permanent
            session['authenticated'] = True
            return jsonify({"success": True, "next": url_for('userlogin')})
        else:
            app.logger.warning(f"Failed login attempt from IP: {request.remote_addr}")
            return jsonify({"success": False, "error": "Invalid password"}), 401

    return render_template('login.html')

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('username', None)  # Remove the 'username' from the session
    session.pop('avatar', None)    # Remove the 'avatar' from the session
    # Redirect to the login page or home page
    return redirect(url_for('login'))

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')

        # Validate the admin password
        if password == ADMIN_PASSWORD:
            session['admin_authenticated'] = True
            return jsonify({"success": True, "next": url_for('admin_page')})
        else:
            return jsonify({"success": False, "error": "Invalid Admin Password."})

    return render_template('admin_login.html')  # Admin login form

@app.route('/userlogin', methods=['GET', 'POST'])
def userlogin():
    if not session.get('authenticated'):  # Ensure the user is authenticated
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form.get('username')
        avatar = request.form.get('avatar')  # Get the selected avatar

        # Validate the username
        if not username.strip():
            return jsonify({"success": False, "error": "Username cannot be empty."})

        # Store username and avatar in session
        session['username'] = username.strip()
        session['avatar'] = avatar

        # Read the current game_data.json
        data = load_data()

        # Check if the user already exists in the users list
        user_exists = any(user['username'] == username.strip()
                          for user in data['users'])

        if not user_exists:
            # Append the new user to the users array
            new_user = {
                "username": username.strip(),
                "avatar": avatar,
                "score": 0
            }
            data['users'].append(new_user)

            # Write the updated data back to the JSON file
            save_data(data)

        return jsonify({"success": True, "next": url_for('home')})

    return render_template('userlogin.html')

@app.route('/admin')
def admin_page():
    if not session.get('admin_authenticated', False):  # Check admin login
        return redirect(url_for('admin_login'))

    data = load_data()  # Get the current data
    return render_template('admin.html', users=data['users'])

@app.route('/admin_logout', methods=['POST'])
def admin_logout():
    session.pop('admin_authenticated', None)  # Clear admin session
    return redirect(url_for('admin_login'))

@app.route('/get_users', methods=['GET'])
def get_users():
    data = load_data()
    return jsonify({'users': data['users']})

# Load data from the JSON file
def load_data():
    return safe_file_operation(
        lambda: json.load(open('game_data.json', 'r', encoding='utf-8'))
    ) or {"questions": [], "answers": [], "votes": [], "users": []}

# Save data to the JSON file
def save_data(data):
    try:
        # Create a backup before saving
        if os.path.exists('game_data.json'):
            os.replace('game_data.json', 'game_data.backup.json')
        
        with open('game_data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        app.logger.error(f"Error saving data: {str(e)}")
        return False

@app.route('/change_score', methods=['POST'])
def change_score():
    data = request.get_json()
    username = data.get('username')
    increment = data.get('increment')

    # Load data from the JSON file
    game_data = load_data()

    # Find the user by username
    user = next(
        (user for user in game_data['users'] if user['username'] == username), None)

    if user is None:
        return jsonify({'success': False, 'message': 'User not found'})

    # Update the user's score
    user['score'] += increment

    # Save the updated data back to the JSON file
    save_data(game_data)

    return jsonify({'success': True})

@app.route('/get_game_state')
def get_game_state():
    """Retrieves the current game state, including answers and votes."""
    data = load_data()
    # Prepend the path and extension to the avatar field
    for answer in data['answers']:
        # Check if the avatar doesn't already have a .webp extension
        if not answer['avatar'].endswith('.webp'):
            answer['avatar'] = answer['avatar'] + ".webp"

    return jsonify(data)

@app.route('/toggle_answer_visibility', methods=['POST'])
def toggle_answer_visibility():
    """Toggles the visibility of a specific answer."""
    data = load_data()
    answer_id = request.json.get('answer_id')

    # Find the answer by ID and toggle the 'visible' flag
    for answer in data['answers']:
        if answer['id'] == answer_id:
            answer['visible'] = not answer['visible']  # Toggle visibility
            break

    save_data(data)

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
    full_data = load_data()
    full_data['answers'] = answers  # Update answers only
    save_data(full_data)

    # Emit the updated answers to clients
    socketio.emit('updated_answers', {'answers': answers})

    return jsonify({'success': True, 'answers': answers})

@app.route('/get_questions')
def get_questions():
    """Fetches all questions for the admin to choose the next question."""
    data = load_data()
    questions = data.get("questions", [])
    return jsonify({"questions": questions})

@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    """Handles the submission of answers along with user information and avatar."""
    answer_text = request.json['answer']
    question_id = request.json['question_id']
    avatar = request.json['avatar']

    # Retrieve username from session
    username = session.get('username')

    data = load_data()
    answer_id = len(data['answers']) + 1
    data['answers'].append({
        "id": answer_id,
        "question_id": question_id,
        "text": answer_text,
        "username": username,  # Store username with the answer
        "avatar": avatar,
        "votes": [],  # Initialize empty vote list for each answer
        "random_num": random.randint(1, 1000),
        "visible": False
    })

    save_data(data)
    return jsonify(success=True)

@app.route('/vote', methods=['POST'])
def vote():
    """Handles voting for an answer, ensuring unique votes by each user."""
    # Get the request data
    data = request.get_json()
    answer_id = data.get('answer_id')
    avatar = data.get('avatar')

    # Validate that required fields are present
    if not answer_id or not avatar:
        return jsonify({"success": False, "message": "Missing required fields"}), 400

    # Validate username from session
    username = session.get('username')
    if not username:
        return jsonify({"success": False, "message": "User not authenticated"}), 401

    # Attempt to convert answer_id to an integer
    try:
        answer_id = int(answer_id)
    except ValueError:
        return jsonify({"success": False, "message": "Invalid answer ID"}), 400

    # Load the latest game data
    game_data = load_data()

    # Ensure the game data has the correct structure
    if 'answers' not in game_data:
        return jsonify({"success": False, "message": "Invalid game data structure"}), 500

    # Find the answer and handle voting
    for answer in game_data['answers']:
        if answer.get('id') == answer_id:
            if 'votes' not in answer:
                answer['votes'] = []  # Initialize votes if not already present

            # Ensure each user votes only once
            if not any(vote['username'] == username for vote in answer['votes']):
                # Add the username and avatar to the votes list
                answer['votes'].append(
                    {"username": username, "avatar": avatar})
                save_data(game_data)  # Save updated data
                return jsonify({"success": True, "message": "Vote recorded successfully"}), 200

    return jsonify({"success": False, "message": "Failed to vote"}), 400

@app.route('/add_question', methods=['POST'])
def add_question():
    """Adds a new question."""
    data = load_data()
    new_question_text = request.json.get('text')

    if new_question_text:
        new_question_id = max(
            q['id'] for q in data['questions']) + 1 if data['questions'] else 1
        data['questions'].append(
            {"id": new_question_id, "text": new_question_text})
        save_data(data)
        return jsonify(success=True)
    return jsonify(success=False)

@app.route('/remove_question', methods=['POST'])
def remove_question():
    """Removes a question by ID."""
    data = load_data()
    question_id = request.json.get('id')

    data['questions'] = [q for q in data['questions'] if q['id'] != question_id]
    save_data(data)

    return jsonify(success=True)

@app.route('/clear_data', methods=['POST'])
def clear_data():
    """Resets the game data while preserving user scores."""
    # Read the current data
    data = load_data()
    
    # Save the current users array
    current_users = data.get('users', [])

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
            "reveal": False,
            "users": current_users  # Preserve users array
        }
        save_data(initial_data)
    else:
        # If there are existing questions, reorder their IDs
        reordered_questions = [
            {"id": i + 1, "text": question['text']}
            for i, question in enumerate(data['questions'])
        ]

        # Write the reordered data while preserving users
        initial_data = {
            "questions": reordered_questions,
            "answers": [],
            "votes": [],
            "reveal": False,
            "users": current_users  # Preserve users array
        }
        save_data(initial_data)

    # Emit the reset event to the clients
    socketio.emit('game_reset', {'message': 'Game has been reset while preserving user scores.'})

    return jsonify(success=True)

@app.route('/clear_votes', methods=['POST'])
def clear_votes():
    """Clears all votes from each answer."""
    data = load_data()
    for answer in data['answers']:
        answer['votes'] = []  # Clear votes
    save_data(data)
    return jsonify(success=True)

@app.route('/set_next_question', methods=['POST'])
def set_next_question():
    """Allows admin to set the next question."""
    question_id = int(request.json['question_id']
                      )  # Convert question_id to integer

    # Load data and update the current question
    data = load_data()
    selected_question = next(
        (q for q in data['questions'] if q['id'] == question_id), None)

    if selected_question:
        data['current_question'] = selected_question
        save_data(data)

        # Clear votes for the new question
        clear_votes()  # Call the clear_votes function here

        # Emit event to update clients
        socketio.emit('next_question', {'question': selected_question})
        return jsonify(success=True, question=selected_question)

    return jsonify(success=False, message="Question not found"), 404

@app.route('/reveal_votes_admin', methods=['POST'])
def reveal_votes_admin():
    """Admin endpoint to reveal all votes and calculate points."""
    data = load_data()
    data['reveal'] = True

    def update_user_points(username, points):
        """Update a user's points in the game data."""
        for user in data['users']:
            if user['username'] == username:
                user['score'] += points
                break
        save_data(data)

    # Calculate points based on votes
    for answer in data['answers']:
        is_correct = answer.get('is_correct', False)
        answer_username = answer['username']

        # Process votes for this answer
        for vote in answer.get('votes', []):
            voter_username = vote['username']

            if is_correct:
                # Award 1 point to users who voted for the correct answer
                update_user_points(voter_username, 1)
            else:
                # Award 2 points to the answer creator for each vote on their wrong answer
                update_user_points(answer_username, 2)

    save_data(data)
    socketio.emit('votes_revealed')
    return jsonify({'success': True})

@app.route('/get_game_data', methods=['GET'])
def get_game_data():
    try:
        data = load_data()
        print(data)  # Log data to verify it's being loaded
        return jsonify(data), 200
    except Exception as e:
        print(f"Error: {str(e)}")  # Log error to check for file issues
        return jsonify({'error': str(e)}), 500

@app.route('/update_game_data', methods=['POST'])
def update_game_data():
    data = request.json

    # Update the game data on the server (assuming you have a game_data object)
    game_data = load_data()
    game_data['users'] = data['users']  # Update the users array
    game_data['answers'] = data['answers']  # Update the answers array
    game_data['questions'] = data['questions']  # Update the questions array

    # Save the updated game data (for example, to a file or a database)
    save_data(game_data)

    return jsonify({'success': True})

@app.route('/increment_score', methods=['POST'])
def increment_score():
    """Increments the score of a user."""
    username = request.json.get('username')
    increment_value = request.json.get(
        'increment_value', 1)  # Default increment value is 1

    # Read data from the JSON file
    data = load_data()

    # Find the user and increment their score
    user = next((user for user in data['users']
                if user['username'] == username), None)
    if user:
        if user.get('score') is None:
            user['score'] = 0  # Initialize score if it doesn't exist
        user['score'] += increment_value

        # Write updated data back to the JSON file
        save_data(data)
        return jsonify({"success": True, "new_score": user['score']})

    return jsonify({"success": False, "message": "User not found"}), 404

@app.route('/decrement_score', methods=['POST'])
def decrement_score():
    """Decrements the score of a user."""
    username = request.json.get('username')
    decrement_value = request.json.get(
        'decrement_value', 1)  # Default decrement value is 1

    # Read data from the JSON file
    data = load_data()

    # Find the user and decrement their score
    user = next((user for user in data['users']
                if user['username'] == username), None)
    if user:
        if user.get('score') is None:
            user['score'] = 0  # Initialize score if it doesn't exist
        user['score'] -= decrement_value

        # Write updated data back to the JSON file
        save_data(data)
        return jsonify({"success": True, "new_score": user['score']})

    return jsonify({"success": False, "message": "User not found"}), 404

@app.route('/delete_user', methods=['POST'])
def delete_user():
    data = request.get_json()
    username = data.get('username')

    # Load data from the JSON file
    game_data = load_data()

    # Find the user by username
    user = next(
        (user for user in game_data['users'] if user['username'] == username), None)

    if user is None:
        return jsonify({'success': False, 'message': 'User not found'})

    # Remove the user from the list
    game_data['users'] = [user for user in game_data['users']
                          if user['username'] != username]

    # Save the updated data back to the JSON file
    save_data(game_data)

    return jsonify({'success': True})

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static/fav', 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/robots.txt')
def robots():
    return send_from_directory('static', 'robots.txt')

@app.route('/sitemap.xml')
def sitemap():
    """Generate sitemap.xml"""
    pages = []
    # Add your website pages here
    pages.append(['https:/you-website-link/', 'daily'])
    pages.append(['https:/you-website-link/login', 'weekly'])

    sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    for page in pages:
        sitemap_xml += '  <url>\n'
        sitemap_xml += f'    <loc>{page[0]}</loc>\n'
        sitemap_xml += f'    <changefreq>{page[1]}</changefreq>\n'
        sitemap_xml += '  </url>\n'
    
    sitemap_xml += '</urlset>'
    
    response = app.response_class(
        response=sitemap_xml,
        status=200,
        mimetype='application/xml'
    )
    return response

@socketio.on('connect')
def handle_connect():
    print("Client connected")

@socketio.on('disconnect')
def handle_disconnect():
    print("Client disconnected")

@app.after_request
def add_security_headers(response):
    """Add security headers to each response"""
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self' https: 'unsafe-inline' 'unsafe-eval'"
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

if __name__ == '__main__':
    socketio.run(app, debug=False)
