from fastapi import FastAPI
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.api.routes import router as dfe_router

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Motor de Emissão de Documentos Fiscais Eletrônicos (NF-e, NFC-e e NFS-e) no Simples Nacional",
)

# Inclusão dos endpoints operacionais DF-e
app.include_router(dfe_router)


@app.get("/")
def root():
    return {
        "status": "online",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.DFE_ENVIRONMENT.value,
        "tp_amb": settings.tp_amb,
        "emitente_uf": settings.EMITENTE_UF,
    }


@app.get("/health")
def health_check():
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "environment": settings.DFE_ENVIRONMENT.value,
            "tp_amb": settings.tp_amb,
        },
    )
