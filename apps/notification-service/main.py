from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import asyncio

app = FastAPI(
    title="CodeForge AI - Notification Service",
    description="Handles webhooks, Server-Sent Events, Slack dispatch, and email alerts",
    version="1.0.0"
)

@app.get("/healthz", status_code=200)
async def health_check():
    return {"status": "healthy", "service": "notification-service"}

@app.post("/api/v1/notifications/slack")
async def send_slack_notification(payload: dict):
    # Dispatch JSON payloads to external Slack webhooks
    return {"status": "dispatched", "channel": "slack"}

@app.post("/api/v1/notifications/email")
async def send_email_notification(payload: dict):
    # Dispatch email alerts via SMTP/SendGrid
    return {"status": "dispatched", "channel": "email"}

# Server-Sent Events (SSE) endpoint for Next.js 15 realtime updates
@app.get("/api/v1/notifications/stream")
async def sse_event_stream():
    async def event_generator():
        try:
            while True:
                # Poll message queue/Redis pubsub, yield format-compliant text
                yield "data: {\"event\": \"ping\", \"time\": \"now\"}\n\n"
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            pass
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")
