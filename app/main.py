from fastapi import FastAPI
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.api.routes import router as dfe_router
from app.api.v1.endpoints.fiscal import router as fiscal_v1_router
from app.api.v1.endpoints.fiscal_records import router as fiscal_records_router
from app.api.v1.endpoints.notifications import router as notifications_router
from app.api.v1.endpoints.inbound import router as inbound_router

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Motor de Emissão e Gestão de Documentos Fiscais Eletrônicos (NF-e mod 55, NFC-e mod 65 e NFS-e ADN) para o Simples Nacional",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Inclusão dos endpoints operacionais DF-e, v1, records, notificações e inbound
app.include_router(dfe_router)
app.include_router(fiscal_v1_router)
app.include_router(fiscal_records_router)
app.include_router(notifications_router)
app.include_router(inbound_router)



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
