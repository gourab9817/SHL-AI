# Streamlit UI Guide

A minimal, clean one-page UI for the SHL AI Assessment Recommender.

## Features

✨ **Simple & Intuitive**
- Single page conversation interface
- Real-time health check
- Visual recommendation cards
- Clear message history

🎯 **Two Main Functions**
1. **Health Check** - Verify API is running
2. **Chat** - Conversational assessment recommendation

## Quick Start

### Option 1: Run Locally (Development)

```bash
# Install dependencies
pip install -r requirements.txt

# Set API key (optional)
export GROQ_API_KEY=sk_...

# Start both backend + frontend
./scripts/start_full_app.sh
```

Then open: http://localhost:8501

### Option 2: Docker (Production)

```bash
# Build image
docker build -t shl-recommender .

# Run container
docker run -e GROQ_API_KEY=sk_... -p 8000:8000 -p 8501:8501 shl-recommender
```

Then open: http://localhost:8501

### Option 3: Docker Compose (Easiest)

```bash
# Set API key
export GROQ_API_KEY=sk_...

# Start everything
docker-compose up

# Open browser
open http://localhost:8501
```

## UI Layout

### Sidebar
- 🔄 **Health Check** button
  - Shows green ✅ if API is healthy
  - Shows red ❌ if API is unavailable
- 🗑️ **Clear Conversation** button
  - Resets chat history
  - Starts fresh conversation
- ℹ️ **About** section
  - Quick description
  - Use case examples

### Main Area
- **Chat History** - Shows all messages
  - User messages: blue background
  - Assistant messages: gray background
- **Input Box** - Type your assessment needs
- **Recommendations** - Visual cards showing:
  - Assessment name
  - Test type code
  - Link to SHL product page

## Usage Example

### Step 1: Check Health
Click the 🔄 "Check Health" button to verify API is running.

### Step 2: Start Conversation
```
You: "I need assessment"
Assistant: "What role or position are you hiring for?"
```

### Step 3: Provide Details
```
You: "Senior Java developer"
Assistant: "Here are recommendations for senior Java engineers:
  ✓ Core Java (Advanced Level)
  ✓ Spring
  ✓ SQL
  ✓ SHL Verify Interactive G+
  ✓ Occupational Personality Questionnaire OPQ32r"
```

### Step 4: Refine (Optional)
```
You: "Add Docker and AWS"
Assistant: "Updated shortlist:
  ✓ Core Java (Advanced Level)
  ✓ Spring
  ✓ SQL
  ✓ AWS Development
  ✓ Docker
  ✓ SHL Verify Interactive G+
  ✓ OPQ32r"
```

### Step 5: Confirm
```
You: "Perfect. Confirmed. Locking it in."
Assistant: "Great! Your assessment battery is locked in..."
[end_of_conversation: true ✅]
```

## Features Explained

### Health Check
- **Button**: 🔄 Verify API is running
- **Green ✅**: API is healthy and responding
- **Red ❌**: API is unavailable (check if running)

### Message Display
- **Blue boxes**: Your messages
- **Gray boxes**: Assistant responses
- **Full history**: All messages remain visible

### Recommendations
- **Card layout**: Easy to scan
- **Assessment name**: Bold, clear
- **Test type**: Code (K, P, S, etc.)
- **SHL link**: Click to view full product details

### End of Conversation
- **Green success message**: When you confirm final battery
- **Blue info message**: Suggestion to refine further
- **Flag**: `end_of_conversation: true`

## Tips & Tricks

### Quick Scenarios

**Scenario 1: Vague Start**
```
You: I need some assessments
→ Assistant asks clarifying questions
```

**Scenario 2: Full JD**
```
You: Senior backend engineer with Java, Spring, SQL, AWS
→ Assistant recommends immediately
```

**Scenario 3: Refine**
```
You: Add Docker, drop OPQ32r
→ Assistant updates the list
```

**Scenario 4: Make it Shorter**
```
You: Too many, make it shorter
→ Assistant removes some items
```

### Keyboard Shortcuts
- **Enter**: Send message
- **Ctrl+C**: Stop app (if running locally)

## File Structure

```
streamlit_app.py          # Main Streamlit app
app/main.py              # FastAPI backend
Dockerfile               # Container with both services
docker-compose.yml       # Easy deployment
scripts/
  ├── start_full_app.sh  # Run both locally
  ├── start_dev.sh       # Dev backend only
  └── start_production.sh # Production backend
```

## Deployment Checklist

- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] GROQ_API_KEY set: `export GROQ_API_KEY=sk_...`
- [ ] Backend running on 8000: `curl http://localhost:8000/health`
- [ ] Frontend running on 8501: `open http://localhost:8501`
- [ ] Health check shows green ✅
- [ ] Can send messages and get responses
- [ ] Recommendations display correctly

## Troubleshooting

### "API is unavailable" (red ❌)

**Problem**: Streamlit can't connect to FastAPI backend

**Solution**:
```bash
# Make sure backend is running
curl http://localhost:8000/health

# If not running, start it:
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Streamlit won't start

**Problem**: Port 8501 already in use

**Solution**:
```bash
# Kill the process using port 8501
lsof -i :8501
kill -9 <PID>

# Or use different port
streamlit run streamlit_app.py --server.port=8502
```

### Messages not being sent

**Problem**: Backend not responding

**Solution**:
1. Check health button (should show green ✅)
2. Try clearing conversation (🗑️ button)
3. Restart both services:
   ```bash
   # Stop: Ctrl+C
   ./scripts/start_full_app.sh
   ```

### Docker won't build

**Problem**: Docker build fails

**Solution**:
```bash
# Clean build
docker build --no-cache -t shl-recommender .

# Check if docker is running
docker ps
```

## Performance

- **Health check**: ~10ms
- **Message send**: 1-5s (depends on Groq)
- **UI response**: Instant
- **Full page load**: <1s

## Customization

### Change Colors
Edit `streamlit_app.py` CSS section:
```python
st.markdown("""
<style>
    .recommendation-box {
        background-color: #f0f2f6;  # Change this
        ...
    }
</style>
""", unsafe_allow_html=True)
```

### Add Features
- [ ] Export conversation as PDF
- [ ] Save conversation history
- [ ] Batch recommendations
- [ ] Assessment comparison table
- [ ] Admin dashboard

## Architecture

```
User Browser (Port 8501)
    ↓
Streamlit Frontend
    ↓ (HTTP API calls)
    ↓
FastAPI Backend (Port 8000)
    ↓
Catalog Index (377 products)
    ↓
Groq LLM (optional)
```

No stored state between requests = safe, stateless design.

## Support

For issues:

1. Check health button in sidebar
2. Review terminal for error messages
3. Try clearing conversation
4. Restart both services
5. Check DEPLOYMENT.md for API troubleshooting

## Next Steps

- Deploy to production (see DEPLOYMENT.md)
- Add custom branding
- Integrate with hiring workflows
- Add analytics/logging
