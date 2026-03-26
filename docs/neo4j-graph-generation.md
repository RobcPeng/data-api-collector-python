# Neo4j Graph Generation: How It Works

This guide explains how the system populates Neo4j with graph data — the data model, how nodes and relationships are created, and how to query the resulting graphs from Databricks.

## Table of Contents

- [Why Graph Data?](#why-graph-data)
- [Architecture](#architecture)
- [How Graph Population Works](#how-graph-population-works)
- [SLED Use Cases — Graph Models](#sled-use-cases--graph-models)
  - [Student Enrollment](#student-enrollment)
  - [Grant & Budget](#grant--budget)
  - [Citizen Services (311)](#citizen-services-311)
  - [K-12 Early Warning](#k-12-early-warning)
  - [Procurement](#procurement)
  - [Case Management (HHS)](#case-management-hhs)
- [Custom Graph Generators](#custom-graph-generators)
- [Querying from Databricks](#querying-from-databricks)
- [Graph vs. Relational: When to Use Each](#graph-vs-relational-when-to-use-each)

---

## Why Graph Data?

Some data is naturally about **connections**. When a student enrolls in a course, offered by a department, leading to a degree — that chain of relationships is awkward in SQL (lots of JOINs) but natural in a graph:

```
(Student)-[:ENROLLED_IN]->(Course)-[:OFFERED_BY]->(Department)
    |
    └──[:PURSUING]->(DegreeProgram)-[:OFFERED_BY]->(Department)
```

Graph databases like Neo4j excel at:
- **Traversal queries**: "Find all students connected to a professor through 2+ courses" (trivial in Cypher, expensive in SQL)
- **Relationship-heavy analytics**: Network analysis, fraud rings, supply chain tracing
- **Flexible schemas**: Adding a new relationship type doesn't require a migration

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  FastAPI App Container                                   │
│                                                          │
│  POST /data-sources/neo4j/sled/{use_case}/populate       │
│       │                                                  │
│       ▼                                                  │
│  ┌──────────────────────────────────────────────────┐    │
│  │  Background asyncio task                         │    │
│  │                                                  │    │
│  │  1. Generate node data (Python random/faker)     │    │
│  │  2. Batch UNWIND → CREATE nodes (500 per batch)  │    │
│  │  3. Create relationships via MATCH + probability │    │
│  │                                                  │    │
│  └──────────────────┬───────────────────────────────┘    │
│                     │                                    │
│                     │ Cypher queries via neo4j driver     │
│                     ▼                                    │
│              ┌────────────┐                               │
│              │   Neo4j     │                               │
│              │   :7474     │ (HTTP browser)                │
│              │   :7687     │ (Bolt protocol)               │
│              └────────────┘                               │
└─────────────────────────────────────────────────────────┘
```

Unlike the Kafka generators (which use a separate container with PySpark), Neo4j population runs inside the main FastAPI app using Python's random module and the Neo4j Python driver directly. No Spark involved — the data generation is lightweight enough that Python handles it.

## How Graph Population Works

### Step 1: Generate node data in Python

Each use case has a population function that generates node properties using Python:

```python
# Example: generating student nodes
students = []
for i in range(num_records):
    students.append({
        "student_id": f"STU-{i+1:05d}",
        "name": _rand_name(),            # Random first + last name
        "email": f"student{i+1}@university.edu",
        "gpa": round(random.uniform(1.5, 4.0), 2),
        "campus": random.choice(["Main", "North", "Online", "Downtown", "West"]),
        # ... more properties
    })
```

The `_rand_name()` helper picks from pools of 72 first names and 72 last names — enough variety to look realistic without the overhead of a full faker library.

### Step 2: Batch-create nodes with UNWIND

Rather than running one `CREATE` per node (which would be slow), the system uses Cypher's `UNWIND` to batch-create nodes:

```cypher
UNWIND $batch AS row
CREATE (s:Student {
    student_id: row.student_id,
    name: row.name,
    email: row.email,
    gpa: row.gpa,
    campus: row.campus
})
```

The `$batch` parameter is a list of 500 dictionaries. For 5,000 students, this runs 10 batch queries instead of 5,000 individual queries — roughly 50x faster.

### Step 3: Create relationships with probabilistic matching

After all nodes exist, the system creates relationships by matching nodes and applying probability-based logic:

```cypher
-- Every student pursues a degree program
MATCH (s:Student), (dp:DegreeProgram)
WITH s, dp, rand() AS r
ORDER BY r
WITH s, collect(dp)[0] AS program
CREATE (s)-[:PURSUING {start_semester: "Fall 2024", expected_graduation: "Spring 2028"}]->(program)
```

```cypher
-- Students enroll in courses (3 enrollments per student on average)
MATCH (s:Student), (c:Course)
WITH s, c, rand() AS r
WHERE r < 0.002  -- probability controls density
CREATE (s)-[:ENROLLED_IN {
    grade: CASE int(rand()*10)
           WHEN 0 THEN "A" WHEN 1 THEN "A-" WHEN 2 THEN "B+"
           WHEN 3 THEN "B" WHEN 4 THEN "B-" WHEN 5 THEN "C+"
           ELSE "C" END,
    semester: CASE int(rand()*4)
              WHEN 0 THEN "Fall 2024" WHEN 1 THEN "Spring 2025"
              ELSE "Summer 2025" END
}]->(c)
```

The `rand() < probability` pattern is how graph density is controlled. A probability of `0.002` between 5,000 students and 2,000 courses creates roughly 5000 * 2000 * 0.002 = 20,000 enrollment relationships.

### Why relationships have properties

In Neo4j, relationships aren't just pointers — they carry data. An `ENROLLED_IN` relationship has `grade`, `status`, and `semester` properties. This means you can query:

```cypher
-- Find students who failed a course and then re-enrolled
MATCH (s:Student)-[e1:ENROLLED_IN {grade: "F"}]->(c:Course)
MATCH (s)-[e2:ENROLLED_IN]->(c)
WHERE e2.semester > e1.semester
RETURN s.name, c.name, e1.semester, e2.semester, e2.grade
```

This kind of temporal relationship query is why graph databases shine for certain analytics.

## SLED Use Cases — Graph Models

### Student Enrollment

**Nodes and relationships:**

```
(Department)
    ▲
    │ OFFERED_BY
    │
(DegreeProgram)                    (Course)──[:OFFERED_BY]──>(Department)
    ▲                                  ▲
    │ PURSUING                         │ ENROLLED_IN
    │                                  │
(Student)──────────────────────────────┘
                                   (Course)──[:REQUIRES]──>(Course)  [prerequisites]
```

| Node | Count | Key Properties |
|------|-------|---------------|
| Department | ~18 | name (Computer Science, Mathematics, English, ...) |
| DegreeProgram | ~45 | name, level (Bachelor/Master/PhD), credits_required |
| Course | ~2,000 | course_id, name, department, credits, level |
| Student | num_records | student_id, name, email, gpa, campus, enrollment_year |

| Relationship | Properties | Notes |
|-------------|-----------|-------|
| OFFERED_BY | — | Connects courses and degrees to departments |
| REQUIRES | — | Course prerequisites (sparse — ~10% of courses) |
| PURSUING | start_semester, expected_graduation | Every student pursues one degree |
| ENROLLED_IN | grade, status, semester | ~3 per student on average |

### Grant & Budget

**Nodes and relationships:**

```
(FundingSource)──[:FUNDS {amount, fiscal_year}]──>(Agency)
                                                      │
                                            [:MANAGES {role}]
                                                      │
                                                      ▼
(Vendor)<──[:AWARDS {contract_amount}]──(Program)──[:HAS_LINE_ITEM]──>(LineItem)
    │
    └──[:SUBCONTRACTS {percentage}]──>(Vendor)
```

This model captures the money flow in government: federal/state funds → agencies → programs → vendors, with subcontracting relationships showing how money cascades through the vendor ecosystem.

### Citizen Services (311)

```
(District)
    ▲
    │ IN_DISTRICT
    │
(Asset) <───[:AFFECTS]───(ServiceRequest)<───[:SUBMITTED {channel}]───(Citizen)
                              │
                    [:ASSIGNED_TO {date}]
                              │
                              ▼
                      (ServiceDepartment)
```

Models a 311-style citizen request system. Citizens submit requests (pothole repair, streetlight outage), which are assigned to departments and linked to physical assets (a specific streetlight, a section of road).

### K-12 Early Warning

```
(School)<──[:WORKS_AT]──(Teacher)
    ▲                       ▲
    │ ATTENDS                │ TAUGHT_BY {subject, period}
    │                        │
(K12Student)─────────────────┘
    │
    └──[:RECEIVED {referred_by}]──>(Intervention)──[:TARGETS]──>(RiskIndicator)
```

Models the early warning system that K-12 schools use to identify at-risk students. Risk indicators (chronic absenteeism, failing grades, behavior issues) trigger interventions (tutoring, mentoring, counseling). The graph lets you trace which interventions are effective for which risk profiles.

### Procurement

```
(ProcAgency)──[:ISSUED {fiscal_year}]──>(Contract)──[:AWARDED_TO {bid_count}]──>(ProcVendor)
                                                                                     │
(Lobbyist)──[:REPRESENTS {since}]──>(ProcVendor)<──[:SUBCONTRACTS_TO {%}]────────────┘
```

Models government procurement — from RFP posting through contract award to vendor subcontracting. The lobbyist relationships add a transparency/compliance dimension.

### Case Management (HHS)

```
(HHSAgency)──[:ADMINISTERS]──>(HHSProgram)
    ▲
    │ WORKS_AT
    │
(Caseworker)<──[:MANAGED_BY {date}]──(Case)<──[:HAS_CASE {intake}]──(Client)
                                       │                                │
                             [:ENROLLED_IN {benefit}]     [:REFERRED]──>│
                                       │                   {source}
                                       ▼
                                 (HHSProgram)
```

Models the social services case management system — SNAP, Medicaid, TANF, housing assistance. Clients have cases managed by caseworkers, enrolled in programs administered by agencies. The REFERRED relationship captures how clients are connected (family members, referrals from healthcare providers or schools).

## Custom Graph Generators

For one-off demos, you can define node types and relationships via JSON:

```python
requests.post(f"{API}/data-sources/neo4j/custom/start", headers=HEADERS, json={
    "name": "org_chart",
    "clear_before": True,   # Wipe existing nodes of these labels first
    "nodes": [
        {
            "label": "Employee",
            "count": 500,
            "properties": [
                {"name": "emp_id", "generator_rule": {"generator": "sequence", "prefix": "EMP-", "width": 5}},
                {"name": "name", "generator_rule": {"generator": "name"}},
                {"name": "salary", "generator_rule": {"generator": "range_int", "min": 50000, "max": 200000}},
            ]
        },
        {
            "label": "Office",
            "count": 10,
            "properties": [
                {"name": "city", "generator_rule": {"generator": "choice", "values": ["NYC", "SF", "Chicago"]}},
            ]
        },
    ],
    "relationships": [
        # Each employee works in one office (probability controls density)
        {"type": "WORKS_IN", "from_label": "Employee", "to_label": "Office",
         "probability": 0.15, "max_per_source": 1},
        # Some employees report to other employees
        {"type": "REPORTS_TO", "from_label": "Employee", "to_label": "Employee",
         "probability": 0.003, "max_per_source": 1},
    ],
})
```

**Available property generators**: `uuid`, `sequence`, `choice`, `range_int`, `range_float`, `bool`, `date`, `timestamp`, `name`, `email`, `phone`, `address`, `constant`, `null_or`.

## Querying from Databricks

### Setup

Add the Neo4j Spark connector to your cluster:

```
spark.jars.packages org.neo4j:neo4j-connector-apache-spark_2.12:5.3.1_for_spark_3
```

### Read nodes as a DataFrame

```python
neo4j_host = dbutils.secrets.get(scope="neo4j", key="host")
neo4j_pass = dbutils.secrets.get(scope="neo4j", key="password")

students_df = (
    spark.read
    .format("org.neo4j.spark.DataSource")
    .option("url", f"bolt://{neo4j_host}:7687")
    .option("authentication.type", "basic")
    .option("authentication.basic.username", "neo4j")
    .option("authentication.basic.password", neo4j_pass)
    .option("labels", "Student")
    .load()
)
```

### Run Cypher queries

```python
# Find at-risk students with low attendance and high behavior incidents
at_risk = (
    spark.read
    .format("org.neo4j.spark.DataSource")
    .option("url", f"bolt://{neo4j_host}:7687")
    .option("authentication.type", "basic")
    .option("authentication.basic.username", "neo4j")
    .option("authentication.basic.password", neo4j_pass)
    .option("query", """
        MATCH (s:K12Student)-[:ATTENDS]->(school:School)
        WHERE s.attendance_rate < 80 AND s.behavior_incidents_ytd > 5
        OPTIONAL MATCH (s)-[:RECEIVED]->(i:Intervention)
        RETURN s.student_id, s.name, s.attendance_rate, s.gpa,
               school.name AS school, collect(i.type) AS interventions
        ORDER BY s.attendance_rate
    """)
    .load()
)
```

### Write data back to Neo4j

```python
# Write fraud analysis results back as nodes
(
    fraud_results_df.write
    .format("org.neo4j.spark.DataSource")
    .option("url", f"bolt://{neo4j_host}:7687")
    .option("authentication.type", "basic")
    .option("authentication.basic.username", "neo4j")
    .option("authentication.basic.password", neo4j_pass)
    .option("labels", ":FraudAlert")
    .option("node.keys", "alert_id")
    .mode("Overwrite")
    .save()
)
```

## Graph vs. Relational: When to Use Each

This stack generates the **same SLED data** in both Neo4j and PostgreSQL, which makes it a good comparison tool:

| Question type | Better fit | Why |
|--------------|-----------|-----|
| "How many students enrolled in Fall 2024?" | PostgreSQL | Simple aggregate — COUNT with a WHERE clause |
| "Which students share 3+ courses with a flagged student?" | Neo4j | Multi-hop traversal — trivial in Cypher, expensive JOINs in SQL |
| "Show me budget transactions over $1M" | PostgreSQL | Filtering and sorting — bread and butter SQL |
| "Trace the subcontracting chain from a prime vendor" | Neo4j | Recursive traversal — variable-length paths in Cypher |
| "Calculate average GPA by department" | PostgreSQL | Grouped aggregation — SQL was built for this |
| "Find communities of caseworkers who share clients" | Neo4j | Community detection — graph algorithms |

The system lets you populate both and run the same analytical questions against each, which is valuable for understanding when to reach for a graph database vs. sticking with relational.
