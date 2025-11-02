import time
from enum import Enum
from typing import Dict, Any, Literal

from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# --- 1. Importaciones del Proyecto ---
# Fíjate que ya NO importamos get_product_mapping ni preload_data.
from config import (
    settings,
    get_size_chart,
    logger,
    ALLOWED_ORIGINS_LIST
)

# --- 2. Modelos de Datos (Pydantic) ---
# Esto no cambia. Define la estructura de los datos.
class FitType(str, Enum):
    slim = "slim"
    regular = "regular"
    loose = "loose"

class RecommendationResponse(BaseModel):
    recommended_size: str
    target_measurement: float
    unit: str
    mode: Literal["in-range", "closest"]
    chart_key: str
    chart_name: str

# --- 3. Inicialización de la Aplicación FastAPI ---
app = FastAPI(
    title="Locura Segura - Size Recommendation Service (v2 - Simple)",
    version="2.0.0",
    description="Microservicio para calcular tallas. Usa 'chart_key' directamente."
)

# --- 4. Middlewares ---
# Se ejecutan con cada petición. Esto no cambia.
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    logger.info(f"Request a '{request.url.path}' procesada en {process_time:.4f}s")
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS_LIST,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# --- 5. Endpoints de la API (las URLs) ---

@app.get("/health", tags=["Monitoring"])
def health_check():
    """Endpoint de 'health check' para verificar que el servicio está vivo."""
    return {"ok": True}

@app.get(
    "/recommend-size",
    tags=["Sizing"],
    response_model=RecommendationResponse
)
def recommend_size(
    # Parámetros. 'chart_key' y 'value' ahora son obligatorios.
    chart_key: str = Query(..., description="Key de la guía (ej: VELILLA-333)"),
    value: float = Query(..., gt=0, description="Medida en plano proporcionada por el usuario (cm)"),
    fit: FitType = Query(FitType.regular, description="Ajuste deseado por el usuario")
):
    """
    Endpoint principal. Ahora es mucho más simple.
    """
    # Paso 1: Cargar la guía de tallas directamente con la key.
    size_chart = get_size_chart(chart_key)
    if not size_chart:
        raise HTTPException(status_code=404, detail=f"No se encontró la guía de tallas: {chart_key}")

    # Paso 2: Usar el valor del cliente DIRECTAMENTE.
    # ¡YA NO HAY MULTIPLICACIÓN POR 2!
    target_measurement = value

    # Paso 3: Aplicar ajuste de 'fit'. Esto sigue igual.
    fit_adjustments = {
        "slim": settings.FIT_ADJUSTMENT_SLIM,
        "regular": settings.FIT_ADJUSTMENT_REGULAR,
        "loose": settings.FIT_ADJUSTMENT_LOOSE,
    }
    target_measurement += fit_adjustments[fit.value]

    # Paso 4: Encontrar la talla. Esto sigue igual.
    ranges = size_chart.get("ranges", [])
    if not ranges:
        raise HTTPException(status_code=500, detail=f"La guía de tallas '{chart_key}' no tiene rangos definidos.")

    # Búsqueda de talla dentro de un rango
    for r in ranges:
        if r.get("min", 0) <= target_measurement <= r.get("max", float('inf')):
            return RecommendationResponse(
                recommended_size=r["size"],
                target_measurement=round(target_measurement, 2),
                unit=size_chart.get("unit", "cm"),
                mode="in-range",
                chart_key=chart_key,
                chart_name=size_chart.get("name", chart_key)
            )

    # Si no se encuentra, buscar la talla más cercana
    closest_range = min(
        ranges,
        key=lambda r: min(abs(target_measurement - r.get("min", 0)), abs(target_measurement - r.get("max", 0)))
    )
    return RecommendationResponse(
        recommended_size=closest_range["size"],
        target_measurement=round(target_measurement, 2),
        unit=size_chart.get("unit", "cm"),
        mode="closest",
        chart_key=chart_key,
        chart_name=size_chart.get("name", chart_key)
    )

@app.get("/charts/{chart_key}", tags=["Debugging"])
def get_chart_details(chart_key: str):
    """Endpoint de depuración para ver el contenido de una guía. Sigue siendo útil."""
    chart = get_size_chart(chart_key)
    if not chart:
        raise HTTPException(status_code=404, detail=f"Guía de tallas no encontrada: {chart_key}")
    
    headers = {"Cache-Control": "public, max-age=3600"}
    return JSONResponse(content=chart, headers=headers)