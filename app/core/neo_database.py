from neo4j import GraphDatabase
from app.core.config import settings
from contextlib import contextmanager

class Neo4jClient:
    _driver = None

    @classmethod
    def get_driver(cls):
        if cls._driver is None:
            cls._driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                max_connection_lifetime=settings.NEO4J_MAX_CONNECTION_LIFETIME,
                max_connection_pool_size=settings.NEO4J_MAX_CONNECTION_POOL_SIZE,
                connection_acquisition_timeout=settings.NEO4J_CONNECTION_TIMEOUT
            )
        return cls._driver

    @classmethod
    def close_driver(cls):
        if cls._driver is not None:
            cls._driver.close()
            cls._driver = None

@contextmanager
def get_neo4j_session():
    """Provide a transactional scope around a series of operations."""
    driver = Neo4jClient.get_driver()
    session = driver.session()
    try:
        yield session
    finally:
        session.close()

def get_neo4j_read_session():
    """Get a read session for Neo4j database."""
    driver = Neo4jClient.get_driver()
    return driver.session(database=settings.NEO4J_DATABASE, access_mode="READ")

def get_neo4j_write_session():
    """Get a write session for Neo4j database."""
    driver = Neo4jClient.get_driver()
    return driver.session(database=settings.NEO4J_DATABASE, access_mode="WRITE")