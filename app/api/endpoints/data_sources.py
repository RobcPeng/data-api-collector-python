from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db, engine
from app.core.config import settings


router = APIRouter(prefix="/data-sources", tags=["data-sources"])


@router.get("/test/orm")
async def test_orm_connection(db: Session = Depends(get_db)):
    try:
        result = db.execute(text("SELECT version() as db_version"))
        row = result.fetchone()
        return {
            "status" : "success",
            "connection_type" : "SQLAlchemy ORM",
            "database_version": row.db_version
        }
    except Exception as e:
        return {"status":"error", "message":str(e)}
    
@router.get("/test/raw/sql")
async def test_raw_sql():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT current_database() as current_db, now() as current_time"))
            row = result.fetchone()
            return {
                "status":"Success",
                "connection_type":"Raw SQL",
                "current_database":row.current_db,
                "current_time": str(row.current_time)
            }
    except Exception as e:
         return {"status":"error", "message":str(e)} 
     
     
@router.get("/test/connection-info")
async def connection_info():
    pool = engine.pool
    return {
        "pool_size": pool.size(),
        "checked_in_connections": pool.checkedin(),
        "checked_out_connections": pool.checkedout(),
        "total_connections": pool.size() + pool.checkedout()
    }
