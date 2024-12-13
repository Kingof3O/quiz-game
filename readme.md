# Quiz Game - Multiplayer Online Game

## Overview

Quiz Game is an interactive multiplayer web application where players submit, vote on, and guess answers to various questions. The game combines strategy, creativity, and social interaction.

## Features

- Multiplayer Gameplay
- Answer Submission
- Voting Mechanism
- User Avatars
- Scoring System
- Admin Controls

## Prerequisites

- Python 3.8+
- pip

## Setup

1. Clone the repository
   ```bash
   git clone https://github.com/Kingof3O/quiz-game.git
   cd quiz-game
   ```

2. Create virtual environment
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables
   Create a `.env` file with:
   ```
   SECRET_KEY=your_secret_key
   ADMIN_PASSWORD=your_admin_password
   USER_PASSWORD=your_user_password
   ```

## Running the Application

```bash
python app.py
```

## Game Modes

### Player Mode
- Login with user password
- Submit answers
- Vote on answers
- Earn points

### Admin Mode
- Manage questions
- Control game state
- Calculate points

## Security

- Use strong passwords
- Keep `.env` private
- Do not share credentials

## License

MIT License - see [LICENSE](LICENSE) file

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit changes
4. Push to branch
5. Open pull request
