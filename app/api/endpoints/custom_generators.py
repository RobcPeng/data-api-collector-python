"""
EXPERIMENTAL: Custom data generators for Neo4j and PostgreSQL.
Lets users POST a JSON schema definition to generate ad-hoc data
for POCs without modifying server code.

Neo4j: Define node labels, properties, and relationships via JSON.
Postgres: Define table schemas and column generation rules via JSON.
"""
import random
import uuid
import logging
import asyncio
from typing import Optional
from datetime import datetime, timezone, timedelta
from enum import Enum
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.core.neo_database import get_neo4j_session
from app.core.database import engine
from sqlalchemy import text

neo4j_router = APIRouter(
    prefix="/data-sources/neo4j/custom",
    tags=["neo4j-custom-generators", "experimental"],
)
postgres_router = APIRouter(
    prefix="/data-sources/custom",
    tags=["postgres-custom-generators", "experimental"],
)
logger = logging.getLogger(__name__)

_active_neo4j_jobs: dict[str, dict] = {}
_active_pg_jobs: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Shared value generation helpers
# ---------------------------------------------------------------------------
def _generate_value(rule: dict) -> object:
    """Generate a single value from a column generation rule."""
    gen_type = rule.get("generator", "random")

    if gen_type == "uuid":
        return str(uuid.uuid4())

    if gen_type == "sequence":
        prefix = rule.get("prefix", "")
        width = rule.get("width", 6)
        # sequence_val is injected by the caller
        return f"{prefix}{rule['_seq']:0{width}d}"

    if gen_type == "choice":
        values = rule.get("values", [])
        weights = rule.get("weights", None)
        if not values:
            return None
        return random.choices(values, weights=weights, k=1)[0]

    if gen_type == "range_int":
        return random.randint(rule.get("min", 0), rule.get("max", 100))

    if gen_type == "range_float":
        return round(random.uniform(rule.get("min", 0.0), rule.get("max", 100.0)), rule.get("precision", 2))

    if gen_type == "bool":
        return random.random() < rule.get("probability", 0.5)

    if gen_type == "date":
        start = datetime.fromisoformat(rule.get("start", "2023-01-01"))
        end = datetime.fromisoformat(rule.get("end", "2025-12-31"))
        delta = end - start
        rand_date = start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))
        return rand_date.strftime(rule.get("format", "%Y-%m-%d"))

    if gen_type == "timestamp":
        start = datetime.fromisoformat(rule.get("start", "2023-01-01T00:00:00"))
        end = datetime.fromisoformat(rule.get("end", "2025-12-31T23:59:59"))
        delta = end - start
        rand_ts = start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))
        return rand_ts.isoformat()

    if gen_type == "name":
        first = ["James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael",
                 "Linda", "David", "Elizabeth", "William", "Barbara", "Richard", "Susan",
                 "Joseph", "Jessica", "Thomas", "Sarah", "Christopher", "Karen"]
        last = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
                "Davis", "Rodriguez", "Martinez", "Wilson", "Anderson", "Thomas", "Taylor"]
        return f"{random.choice(first)} {random.choice(last)}"

    if gen_type == "email":
        prefix = rule.get("_seq", random.randint(1, 99999))
        domain = rule.get("domain", "example.com")
        return f"user{prefix}@{domain}"

    if gen_type == "phone":
        return f"({random.randint(200,999)}) {random.randint(200,999)}-{random.randint(1000,9999)}"

    if gen_type == "address":
        streets = ["Main St", "Oak Ave", "Maple Dr", "Cedar Ln", "Pine St", "Elm St",
                   "Washington Ave", "Park Blvd", "Lake Dr", "Hill Rd"]
        return f"{random.randint(100, 9999)} {random.choice(streets)}"

    if gen_type == "constant":
        return rule.get("value")

    if gen_type == "null_or":
        null_pct = rule.get("null_percent", 20)
        if random.randint(1, 100) <= null_pct:
            return None
        inner_rule = rule.get("rule", {"generator": "random"})
        return _generate_value(inner_rule)

    # Default: random string
    length = rule.get("length", 8)
    chars = "abcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(random.choices(chars, k=length))


def _generate_row(columns: list[dict], seq: int) -> dict:
    """Generate a single row from column definitions."""
    row = {}
    for col_def in columns:
        rule = col_def.get("generator_rule", {"generator": "random"})
        rule["_seq"] = seq
        row[col_def["name"]] = _generate_value(rule)
    return row


# ===========================================================================
# NEO4J CUSTOM GENERATORS
# ===========================================================================

class Neo4jNodeSpec(BaseModel):
    """Define a node type with label, properties, and count."""
    label: str = Field(..., description="Node label, e.g. 'Person', 'Company'")
    count: int = Field(default=1000, ge=1, le=500000, description="Number of nodes to create")
    properties: list[dict] = Field(..., description="Property definitions with name and generator_rule")


class Neo4jRelationshipSpec(BaseModel):
    """Define a relationship between two node types."""
    type: str = Field(..., description="Relationship type, e.g. 'WORKS_AT', 'FRIENDS_WITH'")
    from_label: str = Field(..., description="Source node label")
    to_label: str = Field(..., description="Target node label")
    probability: float = Field(default=0.1, ge=0.001, le=1.0, description="Probability of relationship between any two nodes (controls density)")
    properties: list[dict] = Field(default=[], description="Relationship property definitions")
    max_per_source: Optional[int] = Field(None, ge=1, description="Max relationships per source node (limits fan-out)")


class CustomNeo4jRequest(BaseModel):
    """Define a custom Neo4j graph to generate."""
    name: str = Field(..., min_length=1, max_length=100)
    nodes: list[Neo4jNodeSpec] = Field(..., min_length=1)
    relationships: list[Neo4jRelationshipSpec] = Field(default=[])
    clear_before: bool = Field(default=False, description="Clear existing nodes with these labels before populating")


class CustomNeo4jStatus(BaseModel):
    job_id: str
    name: str
    status: str
    nodes_created: dict = {}
    relationships_created: dict = {}
    error: Optional[str] = None


def _neo4j_create_custom_nodes(node_spec: Neo4jNodeSpec) -> int:
    """Create nodes for a custom spec."""
    batch_size = 500
    total = 0

    with get_neo4j_session() as session:
        for batch_start in range(0, node_spec.count, batch_size):
            batch_end = min(batch_start + batch_size, node_spec.count)
            rows = []
            for i in range(batch_start, batch_end):
                row = _generate_row(
                    [{"name": p["name"], "generator_rule": p.get("generator_rule", {"generator": "random"})}
                     for p in node_spec.properties],
                    seq=i + 1,
                )
                rows.append(row)

            if rows:
                props_str = ", ".join([f"{p['name']}: row.{p['name']}" for p in node_spec.properties])
                session.run(
                    f"UNWIND $rows AS row CREATE (n:{node_spec.label} {{{props_str}}})",
                    rows=rows,
                )
                total += len(rows)

    return total


def _neo4j_create_custom_relationships(rel_spec: Neo4jRelationshipSpec) -> int:
    """Create relationships between existing nodes."""
    with get_neo4j_session() as session:
        max_clause = ""
        if rel_spec.max_per_source:
            max_clause = f"WITH a, b, rand() AS r ORDER BY r LIMIT {rel_spec.max_per_source}"

        props = ""
        if rel_spec.properties:
            prop_parts = []
            for p in rel_spec.properties:
                rule = p.get("generator_rule", {"generator": "random"})
                gen = rule.get("generator", "random")
                if gen == "range_int":
                    prop_parts.append(f"{p['name']}: toInteger(rand() * {rule.get('max', 100) - rule.get('min', 0)} + {rule.get('min', 0)})")
                elif gen == "range_float":
                    prop_parts.append(f"{p['name']}: rand() * {rule.get('max', 100.0) - rule.get('min', 0.0)} + {rule.get('min', 0.0)}")
                elif gen == "choice":
                    vals = rule.get("values", ["default"])
                    prop_parts.append(f"{p['name']}: [{', '.join(repr(v) for v in vals)}][toInteger(rand() * {len(vals)})]")
                elif gen == "bool":
                    prob = rule.get("probability", 0.5)
                    prop_parts.append(f"{p['name']}: rand() < {prob}")
                elif gen == "timestamp":
                    prop_parts.append(f"{p['name']}: toString(datetime())")
                else:
                    prop_parts.append(f"{p['name']}: toString(rand())")
            props = " {" + ", ".join(prop_parts) + "}"

        query = f"""
            MATCH (a:{rel_spec.from_label}), (b:{rel_spec.to_label})
            WITH a, b, rand() AS r WHERE r < $prob
            {max_clause}
            CREATE (a)-[:{rel_spec.type}{props}]->(b)
            RETURN count(*) AS created
        """
        result = session.run(query, prob=rel_spec.probability)
        record = result.single()
        return record["created"] if record else 0


def _run_custom_neo4j(request: CustomNeo4jRequest, state: dict):
    """Execute a custom Neo4j generation job."""
    try:
        # Clear if requested
        if request.clear_before:
            with get_neo4j_session() as session:
                for node_spec in request.nodes:
                    session.run(f"MATCH (n:{node_spec.label}) DETACH DELETE n")

        # Create nodes
        for node_spec in request.nodes:
            count = _neo4j_create_custom_nodes(node_spec)
            state["nodes_created"][node_spec.label] = count
            logger.info(f"Custom Neo4j: created {count} {node_spec.label} nodes")

        # Create relationships
        for rel_spec in request.relationships:
            count = _neo4j_create_custom_relationships(rel_spec)
            state["relationships_created"][rel_spec.type] = count
            logger.info(f"Custom Neo4j: created {count} {rel_spec.type} relationships")

        state["status"] = "completed"
    except Exception as e:
        logger.error(f"Custom Neo4j error: {e}", exc_info=True)
        state["status"] = "error"
        state["error"] = str(e)


# --- Neo4j endpoints ---

@neo4j_router.get("/health")
async def neo4j_custom_health():
    return {
        "status": "ok",
        "service": "custom-neo4j-generators",
        "active": len([s for s in _active_neo4j_jobs.values() if s["status"] == "running"]),
        "total": len(_active_neo4j_jobs),
    }


@neo4j_router.post("/start", response_model=CustomNeo4jStatus)
async def start_custom_neo4j(request: CustomNeo4jRequest):
    """Generate a custom graph in Neo4j from a JSON node/relationship spec."""
    job_id = str(uuid.uuid4())[:8]
    state = {
        "job_id": job_id,
        "name": request.name,
        "status": "running",
        "nodes_created": {},
        "relationships_created": {},
    }
    _active_neo4j_jobs[job_id] = state

    async def _run():
        await asyncio.get_event_loop().run_in_executor(None, _run_custom_neo4j, request, state)

    asyncio.create_task(_run())
    return CustomNeo4jStatus(**state)


@neo4j_router.get("", response_model=list[CustomNeo4jStatus])
async def list_custom_neo4j():
    return [CustomNeo4jStatus(**{k: v for k, v in s.items()}) for s in _active_neo4j_jobs.values()]


@neo4j_router.get("/{job_id}", response_model=CustomNeo4jStatus)
async def get_custom_neo4j(job_id: str):
    state = _active_neo4j_jobs.get(job_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return CustomNeo4jStatus(**state)


@neo4j_router.delete("/{job_id}/clear")
async def clear_custom_neo4j(job_id: str):
    """Clear all nodes created by a custom job (by label)."""
    state = _active_neo4j_jobs.get(job_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    deleted = {}
    with get_neo4j_session() as session:
        for label, count in state.get("nodes_created", {}).items():
            result = session.run(f"MATCH (n:{label}) DETACH DELETE n RETURN count(n) AS count")
            record = result.single()
            deleted[label] = record["count"] if record else 0
    return {"job_id": job_id, "status": "cleared", "deleted": deleted}


@neo4j_router.delete("/cleanup")
async def cleanup_custom_neo4j():
    to_remove = [jid for jid, s in _active_neo4j_jobs.items() if s["status"] != "running"]
    for jid in to_remove:
        del _active_neo4j_jobs[jid]
    return {"removed": len(to_remove), "active": len(_active_neo4j_jobs)}


# ===========================================================================
# POSTGRES CUSTOM GENERATORS
# ===========================================================================

class PgColumnSpec(BaseModel):
    """Define a PostgreSQL column with type and generation rule."""
    name: str = Field(..., description="Column name")
    sql_type: str = Field(..., description="PostgreSQL type: VARCHAR(n), INT, BIGINT, DECIMAL(p,s), BOOLEAN, DATE, TIMESTAMPTZ, TEXT, etc.")
    primary_key: bool = Field(default=False)
    generator_rule: dict = Field(default={"generator": "random"}, description="Value generation rule")


class CustomPgRequest(BaseModel):
    """Define a custom PostgreSQL table to generate."""
    name: str = Field(..., min_length=1, max_length=100, description="Job name")
    table_name: str = Field(..., min_length=1, max_length=100, description="Table name (will be prefixed with custom_)")
    columns: list[PgColumnSpec] = Field(..., min_length=1)
    num_records: int = Field(default=5000, ge=1, le=500000)
    drop_existing: bool = Field(default=False, description="Drop table if it already exists")
    inject_timestamp: bool = Field(default=True, description="Auto-add a created_at TIMESTAMPTZ column")


class CustomPgStatus(BaseModel):
    job_id: str
    name: str
    table_name: str
    status: str
    rows_created: int = 0
    error: Optional[str] = None


def _run_custom_pg(request: CustomPgRequest, state: dict):
    """Execute a custom Postgres generation job."""
    table = f"custom_{request.table_name}"
    state["table_name"] = table

    try:
        with engine.connect() as conn:
            # Drop if requested
            if request.drop_existing:
                conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))

            # Build CREATE TABLE
            col_defs = []
            for col in request.columns:
                pk = " PRIMARY KEY" if col.primary_key else ""
                col_defs.append(f"{col.name} {col.sql_type}{pk}")
            if request.inject_timestamp:
                col_defs.append("created_at TIMESTAMPTZ DEFAULT NOW()")

            create_sql = f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(col_defs)})"
            conn.execute(text(create_sql))
            conn.commit()

            # Generate and insert data in batches
            batch_size = 1000
            total = 0
            col_names = [col.name for col in request.columns]
            col_list = ", ".join(col_names)
            val_list = ", ".join([f":{c}" for c in col_names])
            insert_sql = f"INSERT INTO {table} ({col_list}) VALUES ({val_list})"

            for batch_start in range(0, request.num_records, batch_size):
                batch_end = min(batch_start + batch_size, request.num_records)
                rows = []
                for i in range(batch_start, batch_end):
                    row = {}
                    for col in request.columns:
                        rule = col.generator_rule.copy()
                        rule["_seq"] = i + 1
                        row[col.name] = _generate_value(rule)
                    rows.append(row)

                conn.execute(text(insert_sql), rows)
                total += len(rows)

            conn.commit()
            state["rows_created"] = total
            state["status"] = "completed"
            logger.info(f"Custom Postgres: created {total} rows in {table}")

    except Exception as e:
        logger.error(f"Custom Postgres error: {e}", exc_info=True)
        state["status"] = "error"
        state["error"] = str(e)


# --- Postgres endpoints ---

@postgres_router.get("/health")
async def pg_custom_health():
    return {
        "status": "ok",
        "service": "custom-postgres-generators",
        "active": len([s for s in _active_pg_jobs.values() if s["status"] == "running"]),
        "total": len(_active_pg_jobs),
    }


@postgres_router.post("/start", response_model=CustomPgStatus)
async def start_custom_pg(request: CustomPgRequest):
    """Generate a custom PostgreSQL table from a JSON column spec."""
    job_id = str(uuid.uuid4())[:8]
    state = {
        "job_id": job_id,
        "name": request.name,
        "table_name": f"custom_{request.table_name}",
        "status": "running",
        "rows_created": 0,
    }
    _active_pg_jobs[job_id] = state

    async def _run():
        await asyncio.get_event_loop().run_in_executor(None, _run_custom_pg, request, state)

    asyncio.create_task(_run())
    return CustomPgStatus(**state)


@postgres_router.get("", response_model=list[CustomPgStatus])
async def list_custom_pg():
    return [CustomPgStatus(**{k: v for k, v in s.items()}) for s in _active_pg_jobs.values()]


@postgres_router.get("/{job_id}", response_model=CustomPgStatus)
async def get_custom_pg(job_id: str):
    state = _active_pg_jobs.get(job_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return CustomPgStatus(**state)


@postgres_router.delete("/{job_id}/clear")
async def clear_custom_pg(job_id: str):
    """Truncate the table created by a custom job."""
    state = _active_pg_jobs.get(job_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    table = state["table_name"]
    with engine.connect() as conn:
        try:
            result = conn.execute(text(f"SELECT count(*) FROM {table}"))
            count = result.scalar()
            conn.execute(text(f"TRUNCATE TABLE {table}"))
            conn.commit()
            return {"job_id": job_id, "table": table, "status": "truncated", "rows_removed": count}
        except Exception:
            return {"job_id": job_id, "table": table, "status": "table_not_found"}


@postgres_router.delete("/{job_id}/drop")
async def drop_custom_pg(job_id: str):
    """Drop the table created by a custom job."""
    state = _active_pg_jobs.get(job_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    table = state["table_name"]
    with engine.connect() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
        conn.commit()
    return {"job_id": job_id, "table": table, "status": "dropped"}


@postgres_router.get("/{job_id}/schema")
async def get_custom_pg_schema(job_id: str):
    """Get the schema of a custom-generated table."""
    state = _active_pg_jobs.get(job_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    table = state["table_name"]
    with engine.connect() as conn:
        try:
            result = conn.execute(text(f"""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = :table
                ORDER BY ordinal_position
            """), {"table": table})
            columns = [dict(row._mapping) for row in result]
            count_result = conn.execute(text(f"SELECT count(*) FROM {table}"))
            row_count = count_result.scalar()
            return {"job_id": job_id, "table": table, "columns": columns, "row_count": row_count}
        except Exception:
            return {"job_id": job_id, "table": table, "status": "table_not_found"}


@postgres_router.get("/{job_id}/sample")
async def sample_custom_pg(job_id: str, limit: int = 10):
    """Get sample rows from a custom-generated table."""
    state = _active_pg_jobs.get(job_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    table = state["table_name"]
    with engine.connect() as conn:
        try:
            result = conn.execute(text(f"SELECT * FROM {table} LIMIT :limit"), {"limit": limit})
            rows = [dict(row._mapping) for row in result]
            # Convert non-serializable types
            for row in rows:
                for k, v in row.items():
                    if isinstance(v, (datetime,)):
                        row[k] = v.isoformat()
                    elif hasattr(v, '__float__'):
                        row[k] = float(v)
            return {"job_id": job_id, "table": table, "rows": rows}
        except Exception:
            return {"job_id": job_id, "table": table, "status": "table_not_found"}


@postgres_router.delete("/cleanup")
async def cleanup_custom_pg():
    to_remove = [jid for jid, s in _active_pg_jobs.items() if s["status"] != "running"]
    for jid in to_remove:
        del _active_pg_jobs[jid]
    return {"removed": len(to_remove), "active": len(_active_pg_jobs)}
