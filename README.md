# Realtime AI Backend (WebSockets + Supabase)

A production-ready asynchronous Python backend implementing real-time conversational sessions with LLM integration, WebSocket communication, and persistent data storage.

## Features

- **Real-time WebSocket Communication**: Bi-directional messaging with clients
- **LLM Integration**: Claude 3.5 Sonnet with function calling capabilities
- **Async Architecture**: FastAPI-based async processing
- **Database Persistence**: Supabase PostgreSQL with session tracking and event logging
- **Post-Session Processing**: Automatic session summary generation
- **Simple UI**: Minimal frontend for testing

## Setup Instructions

### Prerequisites

- Python 3.8+
- Supabase account (free tier available)
- Anthropic API key

### Installation

1. Clone the repository:

```bash
git clone https://github.com/Samarthmaske/realtime-ai-backend.git
cd realtime-ai-backend
```

2. Create virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Set up Supabase:
   - Create a new Supabase project
   - Run the SQL schema (see database_schema.sql)
   - Copy your URL and anon key

5. Configure environment:

```bash
cp .env.example .env
```

Edit .env with your API keys

6. Run the server:

```bash
python main.py
```

Visit `http://localhost:8000` to start a conversation.

## Database Schema

Execute the SQL commands in database_schema.sql in your Supabase database.

## Project Structure

```
realtime-ai-backend/
├── main.py                 # FastAPI server & WebSocket logic
├── requirements.txt        # Python dependencies
├── database_schema.sql     # Supabase schema
├── .env.example           # Example env file
├── .env                   # Environment variables
├── .gitignore             # Git ignore rules
├── README.md              # This file
└── static/
    └── index.html         # Simple frontend
```

## Architecture & Design Choices

### WebSocket Endpoint
- Endpoint: `/ws/session/{session_id}`
- Bidirectional real-time messaging
- Automatic reconnection support in frontend

### LLM Integration
- **Model**: Claude 3.5 Sonnet
- **Function Calling**: Supports tool use for data fetching
- **Streaming**: Response tokens streamed directly to client
- **State Management**: Full conversation history maintained

### Database Design
- **Sessions Table**: High-level metadata (start/end times, summaries)
- **Event Logs**: Granular event tracking (messages, tool calls, responses)
- **Indexes**: Performance optimization for queries

### Post-Session Processing
- Triggered on WebSocket disconnect
- Generates concise summary from event logs
- Persists summary and session completion metadata

## Testing

1. Open `http://localhost:8000` in your browser
2. Click "Start Session"
3. Send messages like:
   - "Can you fetch user data for user_123?"
   - "Show me analytics for this session"
   - "What's the status of my account?"

## Key Implementation Details

1. **Async Streaming**: Response tokens streamed immediately
2. **Tool Calling**: LLM can invoke simulated tools
3. **Session State**: Conversation history tracked in memory
4. **Persistence**: All events logged to Supabase
5. **Error Handling**: Graceful error recovery

## Deployment

For production, consider:
- Docker containerization
- Cloud deployment (AWS, GCP, Azure)
- Redis for session caching
- Rate limiting
- Authentication & Authorization

## License

MIT License
