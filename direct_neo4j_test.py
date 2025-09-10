import sys
from neo4j import GraphDatabase
import neo4j

# Try multiple URIs to see which one works
uris_to_try = [
    "bolt://data-api-neo4j:7687",
    "neo4j://data-api-neo4j:7687",
    "bolt://localhost:7687",
    "bolt://127.0.0.1:7687"
]

auth = ("neo4j", "your-neo4j-password")

# Print Python and Neo4j driver versions
print(f"Python version: {sys.version}")
print(f"Neo4j driver version: {neo4j.__version__}\n")  # Fixed version check

# Try each URI
for uri in uris_to_try:
    print(f"\nTrying URI: {uri}")
    print("-" * 40)
    
    try:
        # Create driver with explicit protocol
        driver = GraphDatabase.driver(uri, auth=auth)
        
        # Test connectivity
        print("Testing connectivity...")
        driver.verify_connectivity()
        print("✓ Connection successful!")
        
        # Run a simple query
        print("Running test query...")
        with driver.session() as session:
            result = session.run("RETURN 1 as test")
            record = result.single()
            value = record["test"]
            print(f"✓ Query successful. Result: {value}")
        
        driver.close()
        print(f"\n✓ SUCCESS with URI: {uri}")
        print("Use this URI in your configuration.")
        sys.exit(0)  # Exit with success
        
    except Exception as e:
        print(f"✗ Failed: {type(e).__name__}: {str(e)}")
        print(f"  Detailed error: {e}")

# If we get here, all URIs failed
print("\n✗ All connection attempts failed.")
sys.exit(1)
