import json
import logging
from pathlib import Path
from typing import Dict, List, Literal, Any
from functools import lru_cache

# pydantic_settings nos ayuda a cargar la configuración de forma robusta
from pydantic_settings import BaseSettings, SettingsConfigDict

# --- 1. Configuración del Logging ---
# Esto nos permite ver mensajes informativos en la consola cuando el servidor arranca.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --- 2. Definición de la Configuración ---
class Settings(BaseSettings):
    """
    Define y carga la configuración de la app.
    Lee automáticamente las variables del archivo .env que creamos.
    """
    ENVIRONMENT: Literal["development", "staging", "production"] = "production"
    
    # Leemos la variable de los orígenes como una ÚNICA CADENA de texto.
    # Esta es la corrección clave para evitar errores de parseo.
    ALLOWED_ORIGINS_STR: str

    # Los otros ajustes de configuración van aquí.
    FIT_ADJUSTMENT_SLIM: float = -1.0
    FIT_ADJUSTMENT_REGULAR: float = 0.0
    FIT_ADJUSTMENT_LOOSE: float = 1.0

    # Pydantic-settings buscará un archivo .env para cargar estas variables.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        case_sensitive=False, # No distingue mayúsculas/minúsculas en .env
        extra='ignore'
    )

# --- 3. Creación de la Instancia de Configuración y Procesamiento ---
# (Esta lógica va FUERA de la clase Settings)

# Creamos una única instancia de la configuración para toda la app.
# Ahora 'settings' contiene la variable 'ALLOWED_ORIGINS_STR'.
settings = Settings()

# Convertimos la cadena de orígenes (ej: "url1,url2") a una lista real de Python
# que será la que usemos en main.py para configurar CORS.
ALLOWED_ORIGINS_LIST = [origin.strip() for origin in settings.ALLOWED_ORIGINS_STR.split(',')]


# --- 4. Lógica para Cargar Guías y Mapeos desde Archivos JSON ---

BASE_DIR = Path(__file__).resolve().parent
CHARTS_DIR = BASE_DIR / "charts"
MAPPING_FILE = BASE_DIR / "mapping/products_map.json"

@lru_cache(maxsize=None)  # El cache evita leer el archivo del disco en cada petición
def get_product_mapping() -> Dict[str, str]:
    """Carga el mapeo de productos a guías desde el archivo JSON."""
    try:
        with open(MAPPING_FILE, "r", encoding="utf-8") as f:
            logger.info("Cargando mapeo de productos desde JSON...")
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"¡ERROR! Archivo de mapeo no encontrado en: {MAPPING_FILE}")
        return {}
    except json.JSONDecodeError:
        logger.error(f"¡ERROR! El archivo de mapeo JSON está mal formateado: {MAPPING_FILE}")
        return {}

@lru_cache(maxsize=128)  # Cachea hasta 128 guías de tallas diferentes
def get_size_chart(chart_key: str) -> Dict[str, Any] | None:
    """Carga una guía de tallas específica por su key desde un archivo JSON."""
    chart_file = CHARTS_DIR / f"{chart_key}.json"
    try:
        with open(chart_file, "r", encoding="utf-8") as f:
            logger.info(f"Cargando guía de tallas '{chart_key}' desde JSON...")
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"Guía de tallas no encontrada para la key: {chart_key}")
        return None
    except json.JSONDecodeError:
        logger.error(f"¡ERROR! La guía JSON está mal formateada: {chart_file}")
        return None

def preload_data():
    """Función para precargar todos los datos al iniciar la aplicación."""
    logger.info("Precargando datos iniciales...")
    product_map = get_product_mapping()
    # Usamos set() para evitar cargar la misma guía varias veces si está asignada a varios productos
    for chart_key in set(product_map.values()):
        get_size_chart(chart_key)
    logger.info("Datos precargados con éxito.")