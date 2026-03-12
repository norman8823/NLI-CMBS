from fastapi import FastAPI

from nli_cmbs.api.router import router

app = FastAPI(title="NLI-CMBS", description="CMBS portfolio intelligence tool", version="0.1.0")
app.include_router(router)
