from fastapi import APIRouter, Depends, HTTPException
from neo4j.exceptions import ServiceUnavailable, AuthError
from app.core.neo_database import Neo4jClient, get_neo4j_session
import time

router = APIRouter(prefix="/data-sources", tags=["data-sources"])

@router.get("/neo4j/health")
async def neo4j_health_check():
    """Basic health check for Neo4j database."""
    start_time = time.time()
    try:
        driver = Neo4jClient.get_driver()
        driver.verify_connectivity()
        
        # Simple query to verify database is responsive
        with get_neo4j_session() as session:
            result = session.run("RETURN 1 as test")
            value = result.single()["test"]
            
        response_time = time.time() - start_time
        
        return {
            "status": "success",
            "message": "Neo4j connection successful",
            "response_time_ms": round(response_time * 1000, 2),
            "test_value": value
        }
    except ServiceUnavailable:
        raise HTTPException(status_code=503, detail="Neo4j database is unavailable")
    except AuthError:
        raise HTTPException(status_code=500, detail="Neo4j authentication failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Neo4j connection failed: {str(e)}")

@router.get("/neo4j/version")
async def neo4j_version():
    """Get Neo4j database version information."""
    try:
        with get_neo4j_session() as session:
            result = session.run("CALL dbms.components() YIELD name, versions, edition")
            record = result.single()
            
            return {
                "status": "success",
                "database_name": record["name"],
                "version": record["versions"][0],
                "edition": record["edition"]
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/neo4j/statistics")
async def neo4j_statistics():
    """Get basic statistics about Neo4j database."""
    try:
        with get_neo4j_session() as session:
            # Get node count
            node_result = session.run("MATCH (n) RETURN count(n) as node_count")
            node_count = node_result.single()["node_count"]
            
            # Get relationship count
            rel_result = session.run("MATCH ()-[r]->() RETURN count(r) as rel_count")
            rel_count = rel_result.single()["rel_count"]
            
            # Get label information
            label_result = session.run("""
                CALL db.labels() YIELD label
                MATCH (n:`$label`)
                RETURN label, count(n) as count
                ORDER BY count DESC
            """)
            labels = {record["label"]: record["count"] for record in label_result}
            
            return {
                "status": "success",
                "node_count": node_count,
                "relationship_count": rel_count,
                "labels": labels
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/neo4j/connection-info")
async def neo4j_connection_info():
    """Get information about the Neo4j connection pool."""
    try:
        driver = Neo4jClient.get_driver()
        # Neo4j Python driver doesn't expose detailed pool stats like SQLAlchemy
        # but we can provide basic info
        return {
            "status": "success",
            "connection_active": driver.verify_connectivity(),
            "uri": driver._pool_config.uri,
            "max_connection_pool_size": driver._pool_config.max_connection_pool_size,
            "connection_timeout": driver._pool_config.connection_acquisition_timeout,
            "connection_lifetime": driver._pool_config.max_connection_lifetime
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/neo4j/query-test")
async def neo4j_query_test():
    """Run a sample query to test Neo4j performance."""
    start_time = time.time()
    try:
        with get_neo4j_session() as session:
            # Simple test query
            result = session.run("""
                UNWIND range(1, 1000) AS number
                RETURN sum(number) AS sum, min(number) AS min, max(number) AS max
            """)
            record = result.single()
            
            query_time = time.time() - start_time
            
            return {
                "status": "success",
                "query_time_ms": round(query_time * 1000, 2),
                "results": {
                    "sum": record["sum"],
                    "min": record["min"],
                    "max": record["max"]
                }
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}