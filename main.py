from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import uuid4
from postgrest.exceptions import APIError
import os
from supabase import create_client, Client
import json
import gspread
from google.oauth2.service_account import Credentials

# Initialize FastAPI
app = FastAPI(title="Realflow AI Agent Backend", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "your_webhook_secret_key")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_SHEETS_CREDENTIALS = os.getenv("GOOGLE_SHEETS_CREDENTIALS")

# Initialize Supabase client
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase connected successfully!")
except Exception as e:
    print(f"⚠️ Supabase connection warning: {e}")
    supabase = None

# Initialize Google Sheets client
google_sheet = None
try:
    if GOOGLE_SHEETS_CREDENTIALS and GOOGLE_SHEET_ID:
        # Parse credentials from environment variable
        creds_dict = json.loads(GOOGLE_SHEETS_CREDENTIALS)
        
        # Define the scope
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Create credentials
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        
        # Authorize gspread
        gc = gspread.authorize(credentials)
        
        # Open the sheet
        google_sheet = gc.open_by_key(GOOGLE_SHEET_ID).sheet1
        print("✅ Google Sheets connected successfully!")
    else:
        print("⚠️ Google Sheets credentials not found")
except Exception as e:
    print(f"⚠️ Google Sheets connection error: {e}")
    import traceback
    traceback.print_exc()

# Helper functions
def calculate_lead_score(data: Dict[str, Any]) -> int:
    """Calculate lead score (0-100) based on caller information"""
    score = 0
    
    # Urgency scoring (0-30 points)
    urgency = data.get("urgency", "")
    urgency_scores = {
        "immediate": 30,
        "1-3 months": 25,
        "3-6 months": 15,
        "6+ months": 5,
        "just browsing": 0
    }
    score += urgency_scores.get(urgency, 0)
    
    # Deal size scoring (0-25 points)
    deal_size = data.get("deal_size", "")
    if deal_size:
        deal_lower = str(deal_size).lower()
        if any(indicator in deal_lower for indicator in ["10m", "million", "20m", "50m"]):
            score += 25
        elif any(indicator in deal_lower for indicator in ["5m", "1m", "2m"]):
            score += 20
        elif any(indicator in deal_lower for indicator in ["500k", "750k"]):
            score += 15
        else:
            score += 10
    
    # Role scoring (0-15 points)
    role = data.get("caller_role", "")
    role_scores = {
        "buyer": 15,
        "investor": 15,
        "developer": 12,
        "seller": 10,
        "broker": 8,
        "tenant": 5,
        "landlord": 5
    }
    score += role_scores.get(role, 0)
    
    # Asset type scoring (0-10 points)
    asset_type = data.get("asset_type", "")
    premium_assets = ["multifamily", "industrial", "mixed-use", "office"]
    if asset_type in premium_assets:
        score += 10
    elif asset_type:
        score += 5
    
    # Sentiment scoring (0-10 points)
    sentiment = data.get("sentiment", "neutral")
    sentiment_scores = {
        "very_positive": 10,
        "positive": 8,
        "neutral": 5,
        "negative": 2,
        "frustrated": 0
    }
    score += sentiment_scores.get(sentiment, 5)
    
    # Email provided (0-10 points)
    if data.get("caller_email"):
        score += 10
    
    return min(score, 100)

def is_hot_lead(score: int, urgency: str, deal_size: str) -> tuple:
    """Determine if lead is hot and why"""
    reasons = []
    
    if score >= 75:
        reasons.append(f"High lead score ({score}/100)")
    
    if urgency == "immediate":
        reasons.append("Immediate timeline")
    
    if deal_size and any(indicator in str(deal_size).lower() for indicator in ["10m", "million", "20m", "50m"]):
        reasons.append(f"High deal value ({deal_size})")
    
    is_hot = score >= 75 or urgency == "immediate" or len(reasons) >= 2
    reason = ", ".join(reasons) if reasons else None
    
    return is_hot, reason

async def log_to_google_sheets(parameters: Dict):
    """Log call data to Google Sheets"""
    try:
        if not google_sheet:
            print("⚠️ Google Sheets not configured")
            return False
        
        # Calculate lead score
        lead_score = calculate_lead_score(parameters)
        
        # Prepare row data matching your sheet headers
        row_data = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # Timestamp
            parameters.get("caller_name", ""),              # Caller Name
            parameters.get("caller_phone", ""),             # Phone
            parameters.get("caller_email", ""),             # Email
            parameters.get("caller_role", ""),              # Role
            parameters.get("asset_type", ""),               # Asset Type
            parameters.get("location", ""),                 # Location
            parameters.get("deal_size", ""),                # Deal Size
            parameters.get("urgency", ""),                  # Urgency
            parameters.get("inquiry_summary", ""),          # Inquiry Summary
            "YES" if parameters.get("is_hot_lead", False) else "NO",  # Hot Lead
            f"Score: {lead_score}/100 | " + (parameters.get("additional_notes", "") or "")  # Notes
        ]
        
        # Append to sheet
        google_sheet.append_row(row_data)
        print("✅ Logged to Google Sheets successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error logging to Google Sheets: {e}")
        import traceback
        traceback.print_exc()
        return False

# API Endpoints
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Realflow AI Agent Backend",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "supabase_connected": supabase is not None,
        "google_sheets_connected": google_sheet is not None
    }

@app.post("/webhook/vapi")
async def vapi_webhook(request: Request):
    """Main Vapi webhook endpoint"""
    try:
        payload = await request.json()
        
        # ✅ COMPREHENSIVE LOGGING
        print("\n" + "="*80)
        print("📞 WEBHOOK RECEIVED")
        print("="*80)
        print(f"📦 FULL PAYLOAD:\n{json.dumps(payload, indent=2)}")
        print("="*80)

        # Extract core message info
        message = payload.get("message", {})
        call = payload.get("call", {}) or {}
        call_id = call.get("id", "unknown")
        
        # Check both locations for message type
        message_type = message.get("type") or payload.get("type", "unknown")

        print(f"📋 Message type: {message_type}")
        print(f"🆔 Call ID: {call_id}")

        results = []  # Responses to send back to Vapi

        # ✅ Handle tool-calls (new Vapi format)
        if message_type == "tool-calls":
            tool_calls = message.get("toolCalls", [])
            print(f"🔧 Processing {len(tool_calls)} tool calls")
            print(f"🔍 Tool calls raw data: {json.dumps(tool_calls, indent=2)}")

            for tool_call in tool_calls:
                tool_call_id = tool_call.get("id")
                function_data = tool_call.get("function", {})
                function_name = function_data.get("name", "unknown")

                # Parse arguments (string or dict)
                arguments = function_data.get("arguments", {})
                
                print(f"\n--- Processing Tool Call ---")
                print(f"Tool Call ID: {tool_call_id}")
                print(f"Function Name: {function_name}")
                print(f"Arguments Type: {type(arguments)}")
                print(f"Arguments Raw: {arguments}")
                
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                        print(f"✅ Parsed arguments from string to dict")
                    except Exception as e:
                        print(f"⚠️ Could not parse arguments as JSON: {e}")
                        arguments = {}

                print(f"Final Arguments: {json.dumps(arguments, indent=2)}")

                # ✅ Route to appropriate handler
                handler_result = None
                try:
                    if function_name == "collect_caller_information":
                        print(f"\n🎯 Calling handle_collect_caller_info")
                        handler_result = await handle_collect_caller_info(call_id, arguments, payload)
                    elif function_name == "schedule_callback":
                        print(f"\n🎯 Calling handle_callback_request")
                        handler_result = await handle_callback_request(call_id, arguments)
                    elif function_name == "request_property_information":
                        print(f"\n🎯 Calling handle_property_request")
                        handler_result = await handle_property_request(call_id, arguments)
                    elif function_name == "flag_hot_lead":
                        print(f"\n🎯 Calling handle_hot_lead_flag")
                        handler_result = await handle_hot_lead_flag(call_id, arguments)
                    else:
                        print(f"⚠️ Unrecognized function: {function_name}")
                        handler_result = {"error": f"Unknown function: {function_name}"}
                        
                    print(f"✅ Handler result: {handler_result}")
                    
                except Exception as e:
                    print(f"❌ Error in {function_name}: {e}")
                    import traceback
                    traceback.print_exc()
                    handler_result = {"error": str(e)}

                # ✅ Format tool call result for Vapi
                result_obj = {
                    "toolCallId": tool_call_id,
                    "result": json.dumps(handler_result) if isinstance(handler_result, dict) else str(handler_result)
                }
                results.append(result_obj)
                print(f"📤 Added result to response: {result_obj}")

        # ✅ Handle end-of-call-report
        elif message_type == "end-of-call-report":
            print("📊 Call ended – end-of-call-report received")
            print(f"📦 End-of-call payload: {json.dumps(message, indent=2)}")
            
            # Log any analysis or transcript data
            analysis = message.get("analysis", {})
            if analysis:
                print(f"📊 Analysis data: {json.dumps(analysis, indent=2)}")

        else:
            print(f"⚠️ Unknown message type: {message_type}")
            print(f"📦 Full message: {json.dumps(message, indent=2)}")

        # ✅ Send response to Vapi
        if results:
            response = {"results": results}
            print(f"\n✅ Sending response to Vapi:")
            print(json.dumps(response, indent=2))
            return response
        else:
            print(f"\n✅ No results to send back")
            return {"status": "success", "message": "Processed successfully"}

    except Exception as e:
        print(f"❌ WEBHOOK ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

# ----------------------------------------------------------------------
# ✅ Helper: Process "collect_caller_info" tool calls from Vapi
# ----------------------------------------------------------------------
async def handle_collect_caller_info(call_id: str, arguments: dict, payload: dict):
    """Process caller info, call logging, and hot lead handling"""
    try:
        parameters = arguments or {}
        
        print("\n" + "="*60)
        print("📞 HANDLING COLLECT_CALLER_INFO")
        print("="*60)
        print(f"Call ID: {call_id}")
        print(f"Parameters received: {json.dumps(parameters, indent=2)}")
        
        # ✅ CALCULATE lead score and hot lead status
        lead_score = calculate_lead_score(parameters)
        is_hot, hot_reason = is_hot_lead(lead_score, parameters.get("urgency", ""), parameters.get("deal_size", ""))
        
        print(f"\n📊 CALCULATED VALUES:")
        print(f"  Lead Score: {lead_score}/100")
        print(f"  Is Hot: {is_hot}")
        print(f"  Reason: {hot_reason}")
        
        # ✅ ADD calculated values to parameters
        parameters["is_hot_lead"] = is_hot
        parameters["lead_score"] = lead_score
        parameters["hot_lead_reason"] = hot_reason
        
        print(f"\n📝 ATTEMPTING TO LOG TO GOOGLE SHEETS...")
        # ✅ LOG TO GOOGLE SHEETS FIRST
        sheets_success = await log_to_google_sheets(parameters)
        
        if sheets_success:
            print("✅ Google Sheets logging successful")
        else:
            print("❌ Google Sheets logging failed")

        # ✅ THEN log to Supabase (Bonus feature)
        if supabase:
            call_data = {
                "call_id": call_id,
                "caller_name": parameters.get("caller_name"),
                "caller_phone": parameters.get("caller_phone"),
                "caller_email": parameters.get("caller_email"),
                "caller_role": parameters.get("caller_role"),
                "asset_type": parameters.get("asset_type"),
                "location": parameters.get("location"),
                "deal_size": parameters.get("deal_size"),
                "urgency": parameters.get("urgency"),
                "lead_score": lead_score,  # ✅ Use calculated value
                "hot_lead_reason": hot_reason,  # ✅ Use calculated reason
                "is_hot_lead": is_hot,  # ✅ Use calculated value
                "inquiry_summary": parameters.get("inquiry_summary"),
                "additional_notes": parameters.get("additional_notes"),
                "created_at": datetime.now().isoformat(),
            }

            phone = (parameters.get("caller_phone") or "").strip()
            inserted_call_id = None

            # Look for existing call by call_id or phone number
            if call_id and call_id != "unknown":
                existing = (
                    supabase.table("calls")
                    .select("id,call_id")
                    .eq("call_id", call_id)
                    .execute()
                )
            else:
                existing = (
                    supabase.table("calls")
                    .select("id,call_id")
                    .eq("caller_phone", phone)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )

            if existing.data:
                existing_id = existing.data[0]["id"]
                print(f"⚡ Updating existing Supabase record (id={existing_id})")
                supabase.table("calls").update(call_data).eq("id", existing_id).execute()
                inserted_call_id = existing_id
                supabase.table("conversation_topics").delete().eq("call_id", inserted_call_id).execute()
                supabase.table("questions_asked").delete().eq("call_id", inserted_call_id).execute()
            else:
                if not call_id or call_id == "unknown":
                    generated = str(uuid4())
                    call_data["call_id"] = generated
                    print(f"🆕 Generated new internal call_id: {generated}")
                result = supabase.table("calls").insert(call_data).execute()
                if not result.data:
                    print("❌ Failed to insert call to Supabase")
                else:
                    inserted_call_id = result.data[0]["id"]
                    print(f"📝 Created new Supabase call record id={inserted_call_id}")

            # Save conversation topics
            if inserted_call_id:
                topics = parameters.get("conversation_topics", [])
                if topics:
                    for topic in topics:
                        supabase.table("conversation_topics").insert({
                            "call_id": inserted_call_id,
                            "topic": topic
                        }).execute()
                    print(f"📝 Saved {len(topics)} topics")

                # Save questions
                questions = parameters.get("questions_asked", [])
                if questions:
                    for question in questions:
                        supabase.table("questions_asked").insert({
                            "call_id": inserted_call_id,
                            "question": question
                        }).execute()
                    print(f"✅ Saved {len(questions)} questions")

                # Handle hot leads
                if is_hot:
                    print(f"🔥 Processing hot lead (call_uuid={inserted_call_id})")
                    existing_hot = supabase.table("hot_leads").select("id").eq("call_id", inserted_call_id).execute()
                    if not existing_hot.data and phone:
                        existing_hot = supabase.table("hot_leads").select("id").eq("caller_phone", phone).order("created_at", desc=True).limit(1).execute()

                    hot_lead_data = {
                        "call_id": inserted_call_id,
                        "caller_name": parameters.get("caller_name"),
                        "caller_phone": phone,
                        "urgency_reason": hot_reason,
                        "deal_value": parameters.get("deal_size"),
                        "notified_at": datetime.now().isoformat(),
                    }

                    if existing_hot.data:
                        supabase.table("hot_leads").update(hot_lead_data).eq("id", existing_hot.data[0]["id"]).execute()
                        print("✅ Hot lead updated in Supabase")
                    else:
                        supabase.table("hot_leads").insert(hot_lead_data).execute()
                        print("✅ Hot lead created in Supabase")

                    supabase.table("calls").update({
                        "is_hot_lead": True,
                        "hot_lead_reason": hot_reason,
                    }).eq("id", inserted_call_id).execute()

        return {"success": True, "message": "Caller info processed successfully"}

    print("="*60)
        return {"success": True, "message": "Caller info processed successfully"}

    except Exception as e:
        print(f"❌ ERROR IN handle_collect_caller_info: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": str(e)}


async def handle_callback_request(call_id: str, parameters: Dict):
    """Handle callback scheduling"""
    try:
        print(f"\n📅 Scheduling callback for call: {call_id}")
        
        if supabase:
            # Get the UUID for this call_id
            call_result = supabase.table("calls").select("id").eq("call_id", call_id).execute()
            
            if call_result.data:
                db_call_id = call_result.data[0]["id"]
                print(f"🆔 Found call UUID: {db_call_id}")
                
                callback_data = {
                    "call_id": db_call_id,
                    "caller_name": parameters.get("caller_name"),
                    "callback_phone": parameters.get("callback_phone"),
                    "preferred_date": parameters.get("preferred_date"),
                    "preferred_time": parameters.get("preferred_time"),
                    "timezone": parameters.get("timezone"),
                    "reason": parameters.get("reason"),
                    "status": "scheduled"
                }
                
                # ALWAYS INSERT - each callback is a new record
                supabase.table("callbacks").insert(callback_data).execute()
                print(f"✅ Callback scheduled (NEW record)")
            else:
                print(f"⚠️ Call {call_id} not found in database")
        
        return {
            "success": True,
            "message": f"Callback scheduled for {parameters.get('preferred_date')} {parameters.get('preferred_time')}"
        }
        
    except Exception as e:
        print(f"❌ Error handling callback: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Error scheduling callback: {str(e)}"
        }

async def handle_property_request(call_id: str, parameters: Dict):
    """Handle property information requests"""
    try:
        print(f"\n🏢 Property info requested for call: {call_id}")
        
        if supabase:
            # Get the UUID for this call_id
            call_result = supabase.table("calls").select("id").eq("call_id", call_id).execute()
            
            if call_result.data:
                db_call_id = call_result.data[0]["id"]
                print(f"🆔 Found call UUID: {db_call_id}")
                
                prop_data = {
                    "call_id": db_call_id,
                    "email": parameters.get("email"),
                    "property_type": parameters.get("property_type"),
                    "location": parameters.get("location"),
                    "budget_range": parameters.get("budget_range"),
                    "specific_requirements": parameters.get("specific_requirements"),
                    "status": "pending"
                }
                
                # ALWAYS INSERT - each property request is a new record
                supabase.table("property_requests").insert(prop_data).execute()
                print(f"✅ Property request saved (NEW record)")
            else:
                print(f"⚠️ Call {call_id} not found in database")
        
        return {
            "success": True,
            "message": f"Property information will be sent to {parameters.get('email')}"
        }
        
    except Exception as e:
        print(f"❌ Error handling property request: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Error processing request: {str(e)}"
        }

async def handle_hot_lead_flag(call_id: str, parameters: Dict):
    """Handle manual hot lead flagging"""
    try:
        print(f"\n🔥 Manual hot lead flag for call: {call_id}")
        
        if supabase:
            # Get the UUID for this call_id
            call_result = supabase.table("calls").select("id").eq("call_id", call_id).execute()
            
            if call_result.data:
                db_call_id = call_result.data[0]["id"]
                print(f"🆔 Found call UUID: {db_call_id}")
                
                # Check if hot lead ALREADY exists for THIS specific call
                existing_hot = supabase.table("hot_leads").select("id").eq("call_id", db_call_id).execute()
                
                hot_lead_data = {
                    "call_id": db_call_id,
                    "caller_name": parameters.get("caller_name"),
                    "caller_phone": parameters.get("caller_phone"),
                    "urgency_reason": parameters.get("urgency_reason"),
                    "deal_value": parameters.get("deal_value"),
                    "has_competition": parameters.get("competition", False),
                    "notified_at": datetime.now().isoformat()
                }
                
                if existing_hot.data:
                    # Update existing hot lead for THIS call (duplicate tool call)
                    supabase.table("hot_leads").update(hot_lead_data).eq("call_id", db_call_id).execute()
                    print(f"✅ Hot lead updated (duplicate tool call)")
                else:
                    # Insert NEW hot lead
                    supabase.table("hot_leads").insert(hot_lead_data).execute()
                    print(f"✅ Hot lead created (NEW)")
                
                # Update call record to mark as hot
                supabase.table("calls").update({
                    "is_hot_lead": True,
                    "hot_lead_reason": parameters.get("urgency_reason")
                }).eq("id", db_call_id).execute()
            else:
                print(f"⚠️ Call {call_id} not found in database")
        
        return {
            "success": True,
            "message": "Lead flagged as urgent and will receive priority attention"
        }
        
    except Exception as e:
        print(f"❌ Error handling hot lead flag: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Error flagging lead: {str(e)}"
        }

@app.get("/analytics")
async def get_analytics():
    """Get analytics dashboard data"""
    try:
        if not supabase:
            return {"error": "Supabase not connected"}
        
        # Total calls
        total_calls = supabase.table("calls").select("id", count="exact").execute()
        
        # Hot leads count
        hot_leads = supabase.table("calls").select("id", count="exact").eq("is_hot_lead", True).execute()
        
        # Average lead score
        all_scores = supabase.table("calls").select("lead_score").execute()
        avg_score = sum(row["lead_score"] for row in all_scores.data) / len(all_scores.data) if all_scores.data else 0
        
        # Recent calls
        recent = supabase.table("calls").select("*").order("created_at", desc=True).limit(10).execute()
        
        return {
            "total_calls": total_calls.count or 0,
            "hot_leads_count": hot_leads.count or 0,
            "average_lead_score": round(avg_score, 2),
            "recent_calls": recent.data,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"❌ Analytics error: {e}")
        return {"error": str(e)}

@app.get("/hot-leads")
async def get_hot_leads():
    """Get all hot leads"""
    try:
        if not supabase:
            return {"error": "Supabase not connected"}
        
        hot_leads = supabase.table("calls")\
            .select("*")\
            .eq("is_hot_lead", True)\
            .order("created_at", desc=True)\
            .execute()
        
        return {
            "count": len(hot_leads.data),
            "hot_leads": hot_leads.data
        }
        
    except Exception as e:
        print(f"❌ Hot leads error: {e}")
        return {"error": str(e)}

@app.get("/calls")
async def get_all_calls(limit: int = 50, offset: int = 0):
    """Get all calls with pagination"""
    try:
        if not supabase:
            return {"error": "Supabase not connected"}
        
        result = supabase.table("calls").select("*")\
            .order("created_at", desc=True)\
            .range(offset, offset + limit - 1)\
            .execute()
        
        return {
            "count": len(result.data),
            "calls": result.data
        }
        
    except Exception as e:
        print(f"❌ Calls error: {e}")
        return {"error": str(e)}

@app.get("/dashboard")
async def serve_dashboard():
    """Serve the analytics dashboard"""
    dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
    return FileResponse(dashboard_path)

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Realflow AI Agent Backend...")
    print(f"📊 Supabase URL: {SUPABASE_URL}")
    print(f"📊 Google Sheets ID: {GOOGLE_SHEET_ID}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
