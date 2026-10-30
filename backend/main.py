import os

from dotenv import load_dotenv

load_dotenv()

if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import auth_router, chat_router

app = FastAPI(title="Claude Chat API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["X-Conversation-Id"],
)

app.include_router(auth_router.router)
app.include_router(chat_router.router)

if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app)
