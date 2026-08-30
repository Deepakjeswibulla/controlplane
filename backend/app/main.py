from dotenv import load_dotenv
load_dotenv()

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("controlplane")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ControlPlane.ai backend started")
    yield


app = FastAPI(
    title="ControlPlane.ai",
    description="Context-aware, policy-driven runtime control layer for enterprise AI (Round 2 prototype).",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # prototype only; restrict in a real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
