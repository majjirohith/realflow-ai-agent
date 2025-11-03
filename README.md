Realflow AI Voice Agent

Overview
Built a complete inbound commercial real estate AI agent system using Vapi, Cartesia Sonic 3, FastAPI, and Supabase.

Features
- Natural AI voice conversations with GPT-4 + Cartesia Sonic 3
- Automatic lead qualification and scoring (0-100 algorithm)
- Hot lead detection with intelligent criteria
- Real-time analytics dashboard
- 4 function tools: collect info, schedule callback, property requests, hot lead flagging
- Production deployment on Railway

Architecture
```
Vapi AI Agent → Railway Backend (FastAPI) → Supabase Database
                        ↓
                Analytics Dashboard
```

Live Demo
- **Dashboard:** https://web-production-4dd75.up.railway.app/dashboard
- **API:** https://web-production-4dd75.up.railway.app
- **Analytics Endpoint:** https://web-production-4dd75.up.railway.app/analytics

Tech Stack:
-> **Voice AI:** Vapi + Cartesia Sonic 3 + GPT-4o
-> **Backend:** Python, FastAPI, Uvicorn
-> **Database:** Supabase (PostgreSQL)
-> **Deployment:** Railway
-> **Frontend:** HTML/CSS/JavaScript

Features Implemented:
-> Natural conversation with empathy and fillers  
-> Lead scoring algorithm (urgency, deal size, role, sentiment)  
-> Hot lead auto-detection  
-> Multi-function tool support  
-> Real-time analytics dashboard  
-> Production deployment  

How to Test
1. Visit the dashboard: [link]
2. Call the Vapi agent: [phone number or link]
3. Have a conversation about commercial real estate
4. Watch data appear in real-time on the dashboard

Project Structure
```
realflow-ai-agent/
├── main.py              # FastAPI backend
├── dashboard.html       # Analytics dashboard
├── requirements.txt     # Python dependencies
├── .env.example         # Environment template
└── README.md           # This file
```

Author & Developer - Rohith Majji
