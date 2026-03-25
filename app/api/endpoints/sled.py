import random
import uuid
import logging
import asyncio
from enum import Enum
from typing import Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.core.neo_database import get_neo4j_session
from app.core.database import engine
from sqlalchemy import text

neo4j_router = APIRouter(prefix="/data-sources/neo4j/sled", tags=["neo4j", "sled"])
postgres_router = APIRouter(prefix="/data-sources/sled", tags=["data-sources", "sled"])
logger = logging.getLogger(__name__)

# Track running populate jobs
_active_jobs: dict[str, dict] = {}


class SledUseCase(str, Enum):
    student_enrollment = "student_enrollment"
    grant_budget = "grant_budget"
    citizen_services = "citizen_services"
    k12_early_warning = "k12_early_warning"
    procurement = "procurement"
    case_management = "case_management"


class PopulateRequest(BaseModel):
    num_records: int = Field(default=5000, ge=100, le=500000, description="Base number of records to generate. Actual counts vary by entity type.")


class PopulateResponse(BaseModel):
    use_case: str
    target: str
    status: str
    job_id: str
    num_records: int


class ClearResponse(BaseModel):
    use_case: str
    target: str
    status: str
    details: dict


class StatusResponse(BaseModel):
    use_case: str
    target: str
    counts: dict


# ---------------------------------------------------------------------------
# Value lists — shared across generators for realistic SLED data
# ---------------------------------------------------------------------------
FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
    "David", "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Christopher", "Karen", "Charles", "Lisa", "Daniel", "Nancy",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Dorothy", "Andrew", "Kimberly", "Paul", "Emily", "Joshua", "Donna",
    "Kenneth", "Michelle", "Kevin", "Carol", "Brian", "Amanda", "George", "Melissa",
    "Timothy", "Deborah", "Ronald", "Stephanie", "Edward", "Rebecca", "Jason", "Sharon",
    "Jeffrey", "Laura", "Ryan", "Cynthia", "Jacob", "Kathleen", "Gary", "Amy",
    "Nicholas", "Angela", "Eric", "Shirley", "Jonathan", "Anna", "Stephen", "Brenda",
    "Larry", "Pamela", "Justin", "Emma", "Scott", "Nicole", "Brandon", "Helen",
    "Benjamin", "Samantha", "Samuel", "Katherine", "Raymond", "Christine", "Gregory", "Debra",
    "Frank", "Rachel", "Alexander", "Carolyn", "Patrick", "Janet", "Jack", "Catherine",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill",
    "Flores", "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell",
    "Mitchell", "Carter", "Roberts", "Gomez", "Phillips", "Evans", "Turner", "Diaz",
    "Parker", "Cruz", "Edwards", "Collins", "Reyes", "Stewart", "Morris", "Morales",
    "Murphy", "Cook", "Rogers", "Gutierrez", "Ortiz", "Morgan", "Cooper", "Peterson",
    "Bailey", "Reed", "Kelly", "Howard", "Ramos", "Kim", "Cox", "Ward",
]

STREET_NAMES = [
    "Main St", "Oak Ave", "Maple Dr", "Cedar Ln", "Pine St", "Elm St", "Washington Ave",
    "Park Blvd", "Lake Dr", "Hill Rd", "River Rd", "Church St", "School St", "High St",
    "Forest Ave", "Meadow Ln", "Sunset Blvd", "Spring St", "Valley Rd", "Center St",
]

CITIES = [
    "Springfield", "Franklin", "Greenville", "Bristol", "Clinton", "Fairview", "Salem",
    "Madison", "Georgetown", "Arlington", "Burlington", "Manchester", "Milton", "Oxford",
    "Ashland", "Dover", "Jackson", "Newport", "Riverside", "Chester",
]

STATES = ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
          "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
          "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
          "VA","WA","WV","WI","WY"]


def _rand_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def _rand_date(start_year=2023, end_year=2026):
    start = datetime(start_year, 1, 1, tzinfo=timezone.utc)
    end = datetime(end_year, 12, 31, tzinfo=timezone.utc)
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))


def _rand_id(prefix, max_val):
    width = len(str(max_val))
    return f"{prefix}-{random.randint(1, max_val):0{width}d}"


# ============================= NEO4J GENERATORS =============================

def _neo4j_populate_student_enrollment(num_records: int):
    """Generate student enrollment graph data in Neo4j."""
    num_departments = 18
    num_programs = 45
    num_courses = min(num_records // 2, 2000)
    num_students = num_records
    num_enrollments = num_records * 3

    departments = [
        "Computer Science", "Mathematics", "English", "Biology", "Chemistry",
        "Physics", "History", "Psychology", "Business Administration", "Engineering",
        "Nursing", "Education", "Art", "Music", "Philosophy", "Political Science",
        "Sociology", "Economics"
    ]
    colleges = ["Engineering", "Arts & Sciences", "Business", "Health Sciences", "Education", "Fine Arts"]
    degree_types = ["BS", "BA", "MS", "MA", "PhD", "MBA", "MEd", "BSN", "BFA", "MFA"]
    campuses = ["Main", "North", "Online", "Downtown", "West"]
    semesters = ["Fall 2023", "Spring 2024", "Summer 2024", "Fall 2024", "Spring 2025", "Summer 2025", "Fall 2025"]

    with get_neo4j_session() as session:
        # Create departments
        session.run("""
            UNWIND $depts AS dept_info
            CREATE (d:Department {
                department_id: dept_info.id,
                name: dept_info.name,
                college: dept_info.college,
                building: dept_info.building,
                faculty_count: dept_info.faculty_count
            })
        """, depts=[{
            "id": f"DEPT-{i+1:03d}",
            "name": departments[i],
            "college": colleges[i % len(colleges)],
            "building": f"Building {chr(65 + i % 10)}{random.randint(100,999)}",
            "faculty_count": random.randint(15, 80)
        } for i in range(num_departments)])

        # Create degree programs
        session.run("""
            UNWIND $programs AS p
            MATCH (d:Department {department_id: p.dept_id})
            CREATE (dp:DegreeProgram {
                program_id: p.id,
                name: p.name,
                degree_type: p.degree_type,
                total_credits: p.credits,
                accredited: p.accredited
            })-[:OFFERED_BY]->(d)
        """, programs=[{
            "id": f"PGM-{i+1:03d}",
            "name": f"{departments[i % num_departments]} {degree_types[i % len(degree_types)]}",
            "degree_type": degree_types[i % len(degree_types)],
            "dept_id": f"DEPT-{(i % num_departments)+1:03d}",
            "credits": random.choice([30, 36, 42, 60, 120, 128, 132]),
            "accredited": random.random() > 0.1,
        } for i in range(num_programs)])

        # Create courses in batches
        course_levels = [100, 200, 300, 400, 500, 600]
        course_suffixes = [
            "Introduction to", "Principles of", "Advanced", "Topics in", "Seminar in",
            "Research Methods in", "Applied", "Foundations of", "Survey of", "Theory of"
        ]
        batch_size = 500
        for batch_start in range(0, num_courses, batch_size):
            batch_end = min(batch_start + batch_size, num_courses)
            session.run("""
                UNWIND $courses AS c
                MATCH (d:Department {department_id: c.dept_id})
                CREATE (cr:Course {
                    course_id: c.id,
                    name: c.name,
                    level: c.level,
                    credits: c.credits,
                    max_enrollment: c.max_enrollment,
                    semester: c.semester
                })-[:OFFERED_BY]->(d)
            """, courses=[{
                "id": f"CRS-{i+1:04d}",
                "name": f"{random.choice(course_suffixes)} {departments[i % num_departments]} {random.choice(course_levels)+random.randint(0,9):03d}",
                "level": random.choice(course_levels),
                "credits": random.choice([1, 2, 3, 3, 3, 4, 4]),
                "max_enrollment": random.choice([25, 30, 35, 40, 50, 100, 150, 200]),
                "dept_id": f"DEPT-{(i % num_departments)+1:03d}",
                "semester": random.choice(semesters),
            } for i in range(batch_start, batch_end)])

        # Create prerequisite relationships between courses
        session.run("""
            MATCH (c:Course) WHERE c.level >= 200
            WITH c, rand() AS r WHERE r < 0.6
            MATCH (prereq:Course)
            WHERE prereq.level < c.level
            WITH c, prereq, rand() AS r2 ORDER BY r2 LIMIT 1
            CREATE (c)-[:REQUIRES]->(prereq)
        """)

        # Create students in batches
        for batch_start in range(0, num_students, batch_size):
            batch_end = min(batch_start + batch_size, num_students)
            session.run("""
                UNWIND $students AS s
                CREATE (st:Student {
                    student_id: s.id,
                    name: s.name,
                    email: s.email,
                    enrollment_year: s.enrollment_year,
                    campus: s.campus,
                    gpa: s.gpa,
                    total_credits: s.total_credits,
                    status: s.status
                })
            """, students=[{
                "id": f"STU-{i+1:06d}",
                "name": _rand_name(),
                "email": f"student{i+1}@university.edu",
                "enrollment_year": random.choice([2020, 2021, 2022, 2023, 2024, 2025]),
                "campus": random.choice(campuses),
                "gpa": round(random.uniform(1.5, 4.0), 2),
                "total_credits": random.randint(0, 132),
                "status": random.choices(["active", "graduated", "on_leave", "suspended", "withdrawn"], weights=[60, 15, 10, 5, 10])[0],
            } for i in range(batch_start, batch_end)])

        # Students pursuing degree programs
        session.run("""
            MATCH (s:Student), (dp:DegreeProgram)
            WITH s, dp, rand() AS r ORDER BY r LIMIT $count
            CREATE (s)-[:PURSUING {start_semester: $semester, expected_graduation: $grad}]->(dp)
        """, count=num_students, semester="Fall 2023", grad="Spring 2027")

        # Actually, let's do it properly with varied data per student
        session.run("""
            MATCH (s:Student)
            WITH s
            MATCH (dp:DegreeProgram)
            WITH s, dp, rand() AS r ORDER BY r LIMIT 1
            CREATE (s)-[:PURSUING {
                start_semester: CASE toInteger(rand() * 4)
                    WHEN 0 THEN 'Fall 2022' WHEN 1 THEN 'Spring 2023'
                    WHEN 2 THEN 'Fall 2023' ELSE 'Spring 2024' END,
                expected_graduation: CASE toInteger(rand() * 3)
                    WHEN 0 THEN 'Spring 2026' WHEN 1 THEN 'Spring 2027'
                    ELSE 'Spring 2028' END,
                advisor_assigned: rand() > 0.2
            }]->(dp)
        """)

        # Enrollment relationships (students enrolled in courses)
        session.run(f"""
            MATCH (s:Student)
            WITH s
            MATCH (c:Course) WITH s, c, rand() AS r ORDER BY r LIMIT toInteger(rand() * 4 + 2)
            CREATE (s)-[:ENROLLED_IN {{
                semester: c.semester,
                grade: CASE toInteger(rand() * 12)
                    WHEN 0 THEN 'A' WHEN 1 THEN 'A-' WHEN 2 THEN 'B+'
                    WHEN 3 THEN 'B' WHEN 4 THEN 'B-' WHEN 5 THEN 'C+'
                    WHEN 6 THEN 'C' WHEN 7 THEN 'C-' WHEN 8 THEN 'D'
                    WHEN 9 THEN 'F' WHEN 10 THEN 'W' ELSE 'IP' END,
                status: CASE toInteger(rand() * 4)
                    WHEN 0 THEN 'completed' WHEN 1 THEN 'in_progress'
                    WHEN 2 THEN 'dropped' ELSE 'completed' END
            }}]->( c)
        """)

        logger.info(f"Student enrollment: created {num_departments} departments, {num_programs} programs, {num_courses} courses, {num_students} students")


def _neo4j_populate_grant_budget(num_records: int):
    """Generate grant & budget fund flow graph data in Neo4j."""
    num_sources = min(num_records // 25, 200)
    num_agencies = min(num_records // 100, 50)
    num_programs = min(num_records // 10, 500)
    num_vendors = min(num_records // 3, 2000)
    num_line_items = num_records

    fund_categories = [
        "Federal Grant", "State Appropriation", "Local Revenue", "Bond Proceeds",
        "Tuition & Fees", "Endowment", "Auxiliary Revenue", "Research Grant",
        "Foundation Gift", "Fee-for-Service"
    ]
    federal_programs = [
        "Title I", "IDEA", "Title II-A", "Title III", "Title IV-A", "ESSER I",
        "ESSER II", "ESSER III", "Perkins V", "GEAR UP", "TRIO", "Pell Grant",
        "Work-Study", "SEOG", "AmeriCorps", "CDBG", "HOME", "WIOA", "Head Start", "SNAP-Ed"
    ]
    agency_types = ["School District", "County", "City", "State Agency", "Authority", "Commission", "University", "Community College"]

    batch_size = 500

    with get_neo4j_session() as session:
        # Funding sources
        session.run("""
            UNWIND $sources AS s
            CREATE (f:FundingSource {
                fund_id: s.id, name: s.name, category: s.category,
                total_budget: s.total_budget, fiscal_year: s.fiscal_year,
                cfda_number: s.cfda_number
            })
        """, sources=[{
            "id": f"FUND-{i+1:03d}",
            "name": f"{random.choice(federal_programs)} - FY{random.choice([2023,2024,2025,2026])}",
            "category": random.choice(fund_categories),
            "total_budget": round(random.uniform(50000, 50000000), 2),
            "fiscal_year": random.choice([2023, 2024, 2025, 2026]),
            "cfda_number": f"{random.randint(10,99)}.{random.randint(100,999)}",
        } for i in range(num_sources)])

        # Agencies
        session.run("""
            UNWIND $agencies AS a
            CREATE (ag:Agency {
                agency_id: a.id, name: a.name, type: a.type,
                jurisdiction: a.jurisdiction, employee_count: a.employee_count
            })
        """, agencies=[{
            "id": f"AGY-{i+1:03d}",
            "name": f"{random.choice(CITIES)} {random.choice(agency_types)}",
            "type": random.choice(agency_types),
            "jurisdiction": random.choice(CITIES),
            "employee_count": random.randint(20, 5000),
        } for i in range(num_agencies)])

        # Programs
        program_names = [
            "Infrastructure Improvement", "Public Safety Enhancement", "Youth Development",
            "Senior Services", "Environmental Restoration", "Education Technology",
            "Workforce Training", "Community Health", "Transportation Planning",
            "Housing Development", "Water Quality", "Energy Efficiency",
            "Digital Equity", "Emergency Preparedness", "Parks & Recreation",
            "Arts & Culture", "Food Security", "Mental Health Services",
            "Broadband Expansion", "Economic Development"
        ]
        for batch_start in range(0, num_programs, batch_size):
            batch_end = min(batch_start + batch_size, num_programs)
            session.run("""
                UNWIND $programs AS p
                CREATE (pg:Program {
                    program_id: p.id, name: p.name,
                    budget_allocated: p.budget, status: p.status,
                    start_date: p.start_date
                })
            """, programs=[{
                "id": f"PGM-{i+1:04d}",
                "name": f"{random.choice(program_names)} Phase {random.randint(1,5)}",
                "budget": round(random.uniform(10000, 5000000), 2),
                "status": random.choices(["active", "completed", "pending", "suspended"], weights=[5, 2, 2, 1])[0],
                "start_date": _rand_date().isoformat(),
            } for i in range(batch_start, batch_end)])

        # Vendors
        vendor_types = ["Contractor", "Supplier", "Consultant", "Technology", "Services", "Construction"]
        vendor_suffixes = ["LLC", "Inc.", "Corp.", "& Associates", "Group", "Partners", "Solutions", "Enterprises"]
        for batch_start in range(0, num_vendors, batch_size):
            batch_end = min(batch_start + batch_size, num_vendors)
            session.run("""
                UNWIND $vendors AS v
                CREATE (vn:Vendor {
                    vendor_id: v.id, name: v.name, type: v.type,
                    state: v.state, minority_owned: v.minority_owned,
                    small_business: v.small_business, duns_number: v.duns
                })
            """, vendors=[{
                "id": f"VND-{i+1:04d}",
                "name": f"{random.choice(LAST_NAMES)} {random.choice(vendor_types)} {random.choice(vendor_suffixes)}",
                "type": random.choice(vendor_types),
                "state": random.choice(STATES),
                "minority_owned": random.random() < 0.18,
                "small_business": random.random() < 0.35,
                "duns": f"{random.randint(100000000, 999999999)}",
            } for i in range(batch_start, batch_end)])

        # Line items
        for batch_start in range(0, num_line_items, batch_size):
            batch_end = min(batch_start + batch_size, num_line_items)
            session.run("""
                UNWIND $items AS li
                CREATE (l:LineItem {
                    line_item_id: li.id, account_code: li.account_code,
                    description: li.description, amount: li.amount,
                    transaction_type: li.type, fiscal_quarter: li.quarter
                })
            """, items=[{
                "id": f"LI-{i+1:06d}",
                "account_code": f"{random.randint(1000, 9999)}",
                "description": f"{random.choice(['Personnel costs -', 'Equipment purchase -', 'Professional services for', 'Facilities maintenance -', 'Software licensing -', 'Travel and training -', 'Capital improvement -', 'Consulting fees for'])} {random.choice(program_names)}",
                "amount": round(random.uniform(100, 500000), 2),
                "type": random.choices(["expenditure", "encumbrance", "allocation", "transfer"], weights=[5, 2, 2, 1])[0],
                "quarter": random.choice(["Q1", "Q2", "Q3", "Q4"]),
            } for i in range(batch_start, batch_end)])

        # Relationships: FundingSource -[FUNDS]-> Agency -[MANAGES]-> Program -[HAS_LINE_ITEM]-> LineItem
        session.run("""
            MATCH (f:FundingSource), (a:Agency)
            WITH f, a, rand() AS r WHERE r < 0.3
            CREATE (f)-[:FUNDS {amount: toInteger(rand() * 5000000), fiscal_year: f.fiscal_year}]->(a)
        """)
        session.run("""
            MATCH (a:Agency), (p:Program)
            WITH a, p, rand() AS r WHERE r < 0.15
            CREATE (a)-[:MANAGES {role: CASE toInteger(rand()*3) WHEN 0 THEN 'lead' WHEN 1 THEN 'partner' ELSE 'fiscal_agent' END}]->(p)
        """)
        session.run("""
            MATCH (p:Program), (li:LineItem)
            WITH p, li, rand() AS r ORDER BY r LIMIT $count
            CREATE (p)-[:HAS_LINE_ITEM]->(li)
        """, count=num_line_items)
        session.run("""
            MATCH (p:Program), (v:Vendor)
            WITH p, v, rand() AS r WHERE r < 0.05
            CREATE (p)-[:AWARDS {contract_amount: toInteger(rand() * 2000000), award_date: toString(date())}]->(v)
        """)
        # Subcontractor relationships
        session.run("""
            MATCH (v1:Vendor), (v2:Vendor)
            WHERE v1.vendor_id <> v2.vendor_id
            WITH v1, v2, rand() AS r WHERE r < 0.008
            CREATE (v1)-[:SUBCONTRACTS {percentage: toInteger(rand() * 40 + 5)}]->(v2)
        """)

        logger.info(f"Grant budget: created {num_sources} sources, {num_agencies} agencies, {num_programs} programs, {num_vendors} vendors, {num_line_items} line items")


def _neo4j_populate_citizen_services(num_records: int):
    """Generate 311/citizen services graph data in Neo4j."""
    num_citizens = num_records
    num_requests = num_records * 2
    num_assets = min(num_records // 2, 10000)
    num_departments = 10
    num_districts = 15

    departments = [
        "Public Works", "Transportation", "Water & Sewer", "Code Enforcement",
        "Parks & Recreation", "Building & Permits", "Police", "Fire & Rescue",
        "Health Department", "Environmental Services"
    ]
    request_types = [
        "Pothole Repair", "Streetlight Outage", "Water Main Break", "Noise Complaint",
        "Illegal Dumping", "Graffiti Removal", "Tree Trimming", "Sidewalk Repair",
        "Traffic Signal Malfunction", "Building Inspection", "Permit Application",
        "Animal Control", "Park Maintenance", "Snow Removal", "Sewer Backup",
        "Abandoned Vehicle", "Street Sweeping", "Crosswalk Request", "Speed Bump Request",
        "Weed Abatement"
    ]
    asset_types = ["Road Segment", "Bridge", "Building", "Park", "Water Main", "Sewer Line",
                   "Traffic Signal", "Streetlight", "Fire Hydrant", "Playground"]

    batch_size = 500

    with get_neo4j_session() as session:
        # Districts
        session.run("""
            UNWIND $districts AS d
            CREATE (dist:District {
                district_id: d.id, name: d.name, council_member: d.member,
                population: d.population, area_sq_miles: d.area
            })
        """, districts=[{
            "id": f"DIST-{i+1:02d}",
            "name": f"District {i+1}",
            "member": _rand_name(),
            "population": random.randint(15000, 80000),
            "area": round(random.uniform(2.0, 25.0), 1),
        } for i in range(num_districts)])

        # Departments
        session.run("""
            UNWIND $depts AS d
            CREATE (dept:ServiceDepartment {
                department_id: d.id, name: d.name,
                staff_count: d.staff, avg_response_hours: d.response
            })
        """, depts=[{
            "id": f"SDPT-{i+1:02d}",
            "name": departments[i],
            "staff": random.randint(20, 200),
            "response": round(random.uniform(4, 72), 1),
        } for i in range(num_departments)])

        # Assets
        for batch_start in range(0, num_assets, batch_size):
            batch_end = min(batch_start + batch_size, num_assets)
            session.run("""
                UNWIND $assets AS a
                MATCH (dist:District {district_id: a.district_id})
                CREATE (ast:Asset {
                    asset_id: a.id, type: a.type, condition: a.condition,
                    install_year: a.install_year, last_inspection: a.last_inspection,
                    latitude: a.lat, longitude: a.lon
                })-[:IN_DISTRICT]->(dist)
            """, assets=[{
                "id": f"AST-{i+1:05d}",
                "type": random.choice(asset_types),
                "condition": random.choices(["good", "fair", "poor", "critical"], weights=[4, 3, 2, 1])[0],
                "install_year": random.randint(1970, 2024),
                "last_inspection": _rand_date(2022, 2025).strftime("%Y-%m-%d"),
                "district_id": f"DIST-{random.randint(1, num_districts):02d}",
                "lat": round(random.uniform(38.8, 39.4), 5),
                "lon": round(random.uniform(-77.2, -76.6), 5),
            } for i in range(batch_start, batch_end)])

        # Citizens
        for batch_start in range(0, num_citizens, batch_size):
            batch_end = min(batch_start + batch_size, num_citizens)
            session.run("""
                UNWIND $citizens AS c
                CREATE (cit:Citizen {
                    citizen_id: c.id, name: c.name, email: c.email,
                    phone: c.phone, district_id: c.district_id,
                    registered_date: c.reg_date
                })
            """, citizens=[{
                "id": f"CIT-{i+1:05d}",
                "name": _rand_name(),
                "email": f"citizen{i+1}@email.com",
                "phone": f"({random.randint(200,999)}) {random.randint(200,999)}-{random.randint(1000,9999)}",
                "district_id": f"DIST-{random.randint(1, num_districts):02d}",
                "reg_date": _rand_date(2020, 2025).strftime("%Y-%m-%d"),
            } for i in range(batch_start, batch_end)])

        # Service requests
        for batch_start in range(0, num_requests, batch_size):
            batch_end = min(batch_start + batch_size, num_requests)
            session.run("""
                UNWIND $requests AS r
                CREATE (sr:ServiceRequest {
                    request_id: r.id, type: r.type, status: r.status,
                    priority: r.priority, description: r.description,
                    created_date: r.created, resolved_date: r.resolved,
                    latitude: r.lat, longitude: r.lon
                })
            """, requests=[{
                "id": f"SR-{i+1:06d}",
                "type": random.choice(request_types),
                "status": random.choices(["opened", "assigned", "in_progress", "pending_review", "resolved", "closed", "reopened"], weights=[2, 2, 3, 1, 4, 5, 1])[0],
                "priority": random.choices(["critical", "high", "medium", "low"], weights=[1, 2, 4, 3])[0],
                "description": f"{random.choice(request_types)} reported at {random.randint(100,9999)} {random.choice(STREET_NAMES)}",
                "created": _rand_date(2023, 2025).isoformat(),
                "resolved": _rand_date(2023, 2026).isoformat() if random.random() > 0.3 else None,
                "lat": round(random.uniform(38.8, 39.4), 5),
                "lon": round(random.uniform(-77.2, -76.6), 5),
            } for i in range(batch_start, batch_end)])

        # Relationships
        session.run("""
            MATCH (cit:Citizen), (sr:ServiceRequest)
            WITH cit, sr, rand() AS r ORDER BY r LIMIT $count
            CREATE (cit)-[:SUBMITTED {channel: CASE toInteger(rand()*4) WHEN 0 THEN 'phone' WHEN 1 THEN 'web' WHEN 2 THEN 'app' ELSE 'walk_in' END}]->(sr)
        """, count=num_requests)
        session.run("""
            MATCH (sr:ServiceRequest), (dept:ServiceDepartment)
            WITH sr, dept, rand() AS r ORDER BY r LIMIT 1
            CREATE (sr)-[:ASSIGNED_TO]->(dept)
        """)
        # Fix: assign each request to one department
        session.run("""
            MATCH (sr:ServiceRequest) WHERE NOT (sr)-[:ASSIGNED_TO]->()
            WITH sr
            MATCH (dept:ServiceDepartment) WITH sr, dept, rand() AS r ORDER BY r LIMIT 1
            CREATE (sr)-[:ASSIGNED_TO {assigned_date: sr.created_date}]->(dept)
        """)
        session.run("""
            MATCH (sr:ServiceRequest), (ast:Asset)
            WITH sr, ast, rand() AS r WHERE r < 0.3
            WITH sr, ast ORDER BY rand() LIMIT 1
            CREATE (sr)-[:AFFECTS]->(ast)
        """)

        logger.info(f"Citizen services: created {num_districts} districts, {num_departments} depts, {num_assets} assets, {num_citizens} citizens, {num_requests} requests")


def _neo4j_populate_k12_early_warning(num_records: int):
    """Generate K-12 early warning system graph data in Neo4j."""
    num_schools = min(num_records // 50, 100)
    num_teachers = min(num_records // 5, 3000)
    num_students = num_records
    num_interventions = num_records // 3

    school_name_prefixes = [
        "Washington", "Lincoln", "Jefferson", "Roosevelt", "Martin Luther King Jr.",
        "Kennedy", "Franklin", "Madison", "Adams", "Hamilton", "Oakwood", "Riverside",
        "Lakewood", "Hillcrest", "Westfield", "Northview", "Southgate", "Eastport",
        "Meadowbrook", "Pinecrest"
    ]
    risk_indicators = [
        "Chronic Absenteeism", "Failing Grades", "Behavioral Issues",
        "Social Isolation", "Family Crisis", "Substance Abuse Risk",
        "Mental Health Concern", "Bullying Involvement", "Learning Disability",
        "Language Barrier", "Homelessness", "Trauma Exposure"
    ]
    intervention_types = [
        "Academic Tutoring", "Peer Mentoring", "School Counseling", "Parent Conference",
        "Schedule Modification", "Behavioral Plan", "After-School Program",
        "Community Mentoring", "Restorative Justice", "Social-Emotional Learning",
        "Reading Intervention", "Math Support", "Attendance Contract"
    ]

    batch_size = 500

    with get_neo4j_session() as session:
        # Schools
        session.run("""
            UNWIND $schools AS s
            CREATE (sc:School {
                school_id: s.id, name: s.name, type: s.type,
                enrollment: s.enrollment, title_i: s.title_i,
                graduation_rate: s.grad_rate, principal: s.principal
            })
        """, schools=[{
            "id": f"SCH-{i+1:03d}",
            "name": f"{school_name_prefixes[i % len(school_name_prefixes)]} {random.choice(['Elementary', 'Middle', 'High'])} School",
            "type": random.choices(["elementary", "middle", "high"], weights=[5, 3, 2])[0],
            "enrollment": random.randint(200, 2500),
            "title_i": random.random() < 0.55,
            "grad_rate": round(random.uniform(65, 99), 1) if random.random() > 0.3 else None,
            "principal": _rand_name(),
        } for i in range(num_schools)])

        # Teachers
        subjects = ["Mathematics", "English Language Arts", "Science", "Social Studies", "Special Education",
                     "Art", "Music", "Physical Education", "ESL/ELL", "Technology", "Reading Specialist", "Counselor"]
        for batch_start in range(0, num_teachers, batch_size):
            batch_end = min(batch_start + batch_size, num_teachers)
            session.run("""
                UNWIND $teachers AS t
                MATCH (sc:School {school_id: t.school_id})
                CREATE (tc:Teacher {
                    teacher_id: t.id, name: t.name, subject: t.subject,
                    years_experience: t.experience, certification: t.cert
                })-[:WORKS_AT]->(sc)
            """, teachers=[{
                "id": f"TCH-{i+1:04d}",
                "name": _rand_name(),
                "subject": random.choice(subjects),
                "experience": random.randint(1, 35),
                "cert": random.choices(["standard", "advanced", "national_board", "provisional", "emergency"], weights=[5, 3, 1, 1, 1])[0],
                "school_id": f"SCH-{random.randint(1, num_schools):03d}",
            } for i in range(batch_start, batch_end)])

        # Risk indicators as nodes
        session.run("""
            UNWIND $indicators AS ri
            CREATE (r:RiskIndicator {
                indicator_id: ri.id, name: ri.name,
                category: ri.category, severity_weight: ri.weight
            })
        """, indicators=[{
            "id": f"RI-{i+1:02d}",
            "name": risk_indicators[i],
            "category": random.choice(["academic", "behavioral", "social_emotional", "environmental"]),
            "weight": round(random.uniform(0.5, 1.0), 2),
        } for i in range(len(risk_indicators))])

        # Students
        for batch_start in range(0, num_students, batch_size):
            batch_end = min(batch_start + batch_size, num_students)
            session.run("""
                UNWIND $students AS s
                CREATE (st:K12Student {
                    student_id: s.id, name: s.name, grade_level: s.grade,
                    gpa: s.gpa, attendance_rate: s.attendance,
                    behavior_incidents_ytd: s.incidents,
                    free_reduced_lunch: s.frl, english_learner: s.ell,
                    special_education: s.sped, risk_score: s.risk_score,
                    gifted: s.gifted
                })
            """, students=[{
                "id": f"K12-{i+1:05d}",
                "name": _rand_name(),
                "grade": random.randint(1, 12),
                "gpa": round(random.uniform(0.5, 4.0), 2),
                "attendance": round(random.uniform(60, 100), 1),
                "incidents": random.choices(range(0, 15), weights=[50]+[10]+[8]+[6]+[5]+[4]+[3]+[2]+[2]+[2]+[1]*5)[0],
                "frl": random.random() < 0.45,
                "ell": random.random() < 0.15,
                "sped": random.random() < 0.13,
                "risk_score": round(random.uniform(0, 100), 1),
                "gifted": random.random() < 0.08,
            } for i in range(batch_start, batch_end)])

        # Student -> School (ATTENDS)
        session.run("""
            MATCH (s:K12Student)
            WITH s
            MATCH (sc:School) WITH s, sc, rand() AS r ORDER BY r LIMIT 1
            CREATE (s)-[:ATTENDS {enrollment_date: toString(date() - duration('P' + toString(toInteger(rand()*1000)) + 'D'))}]->(sc)
        """)

        # Student -> Teacher (TAUGHT_BY) - each student has 3-7 teachers
        session.run("""
            MATCH (s:K12Student)-[:ATTENDS]->(sc:School)<-[:WORKS_AT]-(t:Teacher)
            WITH s, t, rand() AS r ORDER BY r LIMIT toInteger(rand() * 4 + 3)
            CREATE (s)-[:TAUGHT_BY {subject: t.subject, period: toInteger(rand() * 8 + 1)}]->(t)
        """)

        # Interventions
        for batch_start in range(0, num_interventions, batch_size):
            batch_end = min(batch_start + batch_size, num_interventions)
            session.run("""
                UNWIND $interventions AS iv
                CREATE (i:Intervention {
                    intervention_id: iv.id, type: iv.type,
                    start_date: iv.start_date, end_date: iv.end_date,
                    status: iv.status, effectiveness: iv.effectiveness,
                    notes: iv.notes
                })
            """, interventions=[{
                "id": f"INT-{i+1:05d}",
                "type": random.choice(intervention_types),
                "start_date": _rand_date(2023, 2025).strftime("%Y-%m-%d"),
                "end_date": _rand_date(2024, 2026).strftime("%Y-%m-%d"),
                "status": random.choices(["active", "completed", "discontinued", "pending"], weights=[4, 3, 2, 1])[0],
                "effectiveness": random.choices(["highly_effective", "effective", "moderate", "ineffective", "too_early"], weights=[1, 3, 3, 2, 2])[0],
                "notes": f"{random.choice(intervention_types)} for student showing {random.choice(risk_indicators).lower()}",
            } for i in range(batch_start, batch_end)])

        # Intervention -> RiskIndicator
        session.run("""
            MATCH (i:Intervention), (ri:RiskIndicator)
            WITH i, ri, rand() AS r WHERE r < 0.15
            CREATE (i)-[:TARGETS]->(ri)
        """)

        # Student -> Intervention (RECEIVED)
        session.run("""
            MATCH (s:K12Student) WHERE s.risk_score > 40
            WITH s
            MATCH (i:Intervention)
            WITH s, i, rand() AS r ORDER BY r LIMIT toInteger(rand() * 2 + 1)
            CREATE (s)-[:RECEIVED {referred_by: CASE toInteger(rand()*3) WHEN 0 THEN 'teacher' WHEN 1 THEN 'counselor' ELSE 'parent' END}]->(i)
        """)

        logger.info(f"K12 early warning: created {num_schools} schools, {num_teachers} teachers, {num_students} students, {num_interventions} interventions")


def _neo4j_populate_procurement(num_records: int):
    """Generate procurement & vendor network graph data in Neo4j."""
    num_agencies = min(num_records // 100, 50)
    num_vendors = min(num_records // 3, 3000)
    num_contracts = min(num_records // 2, 5000)
    num_lobbyists = min(num_records // 20, 200)

    agency_names = [
        "Department of Transportation", "Department of Education", "Public Safety",
        "Health & Human Services", "Environmental Protection", "General Services",
        "Information Technology", "Finance & Administration", "Parks & Recreation",
        "Housing Authority", "Water Authority", "Port Authority", "Transit Authority",
        "Corrections Department", "Labor Department", "Agriculture Department"
    ]
    commodity_categories = [
        "Construction", "Professional Services", "IT Services & Equipment",
        "Office Supplies", "Facilities Management", "Consulting",
        "Staffing & Temp Services", "Transportation & Fleet", "Utilities",
        "Medical & Lab Supplies", "Security Services", "Food Services",
        "Janitorial Services", "Legal Services", "Marketing & Communications"
    ]

    batch_size = 500

    with get_neo4j_session() as session:
        # Agencies
        session.run("""
            UNWIND $agencies AS a
            CREATE (ag:ProcAgency {
                agency_id: a.id, name: a.name,
                annual_procurement_budget: a.budget,
                procurement_officer: a.officer,
                state: a.state
            })
        """, agencies=[{
            "id": f"PAGY-{i+1:03d}",
            "name": f"{random.choice(CITIES)} {agency_names[i % len(agency_names)]}",
            "budget": round(random.uniform(1000000, 500000000), 2),
            "officer": _rand_name(),
            "state": random.choice(STATES),
        } for i in range(num_agencies)])

        # Vendors
        vendor_specialties = commodity_categories
        for batch_start in range(0, num_vendors, batch_size):
            batch_end = min(batch_start + batch_size, num_vendors)
            session.run("""
                UNWIND $vendors AS v
                CREATE (vn:ProcVendor {
                    vendor_id: v.id, name: v.name, specialty: v.specialty,
                    state: v.state, minority_owned: v.mbe, small_business: v.sbe,
                    woman_owned: v.wbe, local_vendor: v.local,
                    years_in_business: v.years, bonded: v.bonded,
                    annual_revenue: v.revenue
                })
            """, vendors=[{
                "id": f"PVND-{i+1:04d}",
                "name": f"{random.choice(LAST_NAMES)} {random.choice(['Construction', 'Services', 'Solutions', 'Technologies', 'Consulting', 'Group', 'Industries', 'Associates'])} {random.choice(['LLC', 'Inc.', 'Corp.', 'LP'])}",
                "specialty": random.choice(vendor_specialties),
                "state": random.choice(STATES),
                "mbe": random.random() < 0.18,
                "sbe": random.random() < 0.35,
                "wbe": random.random() < 0.15,
                "local": random.random() < 0.40,
                "years": random.randint(1, 50),
                "bonded": random.random() < 0.6,
                "revenue": round(random.uniform(100000, 100000000), 2),
            } for i in range(batch_start, batch_end)])

        # Contracts
        for batch_start in range(0, num_contracts, batch_size):
            batch_end = min(batch_start + batch_size, num_contracts)
            session.run("""
                UNWIND $contracts AS c
                CREATE (ct:Contract {
                    contract_id: c.id, title: c.title,
                    amount: c.amount, method: c.method,
                    category: c.category, status: c.status,
                    start_date: c.start_date, end_date: c.end_date,
                    duration_months: c.duration, payment_terms: c.terms
                })
            """, contracts=[{
                "id": f"CTR-{i+1:05d}",
                "title": f"{random.choice(commodity_categories)} - {random.choice(['Phase', 'Project', 'Program', 'Initiative', 'Contract'])} {random.randint(1, 999)}",
                "amount": round(random.uniform(5000, 25000000), 2),
                "method": random.choices(["competitive_bid", "sole_source", "emergency", "cooperative", "micro_purchase", "rfq"], weights=[5, 2, 1, 2, 3, 2])[0],
                "category": random.choice(commodity_categories),
                "status": random.choices(["active", "completed", "pending", "terminated", "expired"], weights=[4, 3, 1, 1, 1])[0],
                "start_date": _rand_date(2022, 2025).strftime("%Y-%m-%d"),
                "end_date": _rand_date(2024, 2028).strftime("%Y-%m-%d"),
                "duration": random.choice([3, 6, 12, 18, 24, 36, 48, 60]),
                "terms": random.choice(["net_30", "net_45", "net_60", "upon_delivery"]),
            } for i in range(batch_start, batch_end)])

        # Lobbyists
        session.run("""
            UNWIND $lobbyists AS l
            CREATE (lb:Lobbyist {
                lobbyist_id: l.id, name: l.name, firm: l.firm,
                registration_date: l.reg_date, specialization: l.spec,
                total_compensation: l.compensation
            })
        """, lobbyists=[{
            "id": f"LOB-{i+1:03d}",
            "name": _rand_name(),
            "firm": f"{random.choice(LAST_NAMES)} & {random.choice(LAST_NAMES)} {random.choice(['Government Relations', 'Public Affairs', 'Advocacy Group', 'Policy Advisors'])}",
            "reg_date": _rand_date(2018, 2025).strftime("%Y-%m-%d"),
            "spec": random.choice(commodity_categories),
            "compensation": round(random.uniform(50000, 2000000), 2),
        } for i in range(num_lobbyists)])

        # Relationships
        # Agency -> Contract (ISSUED)
        session.run("""
            MATCH (ag:ProcAgency), (ct:Contract)
            WITH ag, ct, rand() AS r ORDER BY r LIMIT $count
            CREATE (ag)-[:ISSUED {fiscal_year: toInteger(rand() * 3 + 2023)}]->(ct)
        """, count=num_contracts)

        # Contract -> Vendor (AWARDED_TO)
        session.run("""
            MATCH (ct:Contract)
            WITH ct
            MATCH (vn:ProcVendor) WITH ct, vn, rand() AS r ORDER BY r LIMIT 1
            CREATE (ct)-[:AWARDED_TO {award_date: ct.start_date, bid_count: toInteger(rand() * 12 + 1)}]->(vn)
        """)

        # Vendor subcontracting
        session.run("""
            MATCH (v1:ProcVendor), (v2:ProcVendor)
            WHERE v1.vendor_id <> v2.vendor_id
            WITH v1, v2, rand() AS r WHERE r < 0.005
            CREATE (v1)-[:SUBCONTRACTS_TO {percentage: toInteger(rand() * 35 + 5), scope: v2.specialty}]->(v2)
        """)

        # Lobbyist -> Vendor (REPRESENTS)
        session.run("""
            MATCH (lb:Lobbyist), (vn:ProcVendor)
            WITH lb, vn, rand() AS r WHERE r < 0.02
            CREATE (lb)-[:REPRESENTS {since: lb.registration_date}]->(vn)
        """)

        logger.info(f"Procurement: created {num_agencies} agencies, {num_vendors} vendors, {num_contracts} contracts, {num_lobbyists} lobbyists")


def _neo4j_populate_case_management(num_records: int):
    """Generate HHS case management graph data in Neo4j."""
    num_agencies = min(num_records // 200, 30)
    num_caseworkers = min(num_records // 10, 1500)
    num_clients = num_records
    num_cases = int(num_records * 1.5)

    programs = [
        "SNAP", "Medicaid", "TANF", "WIC", "CHIP", "Housing Assistance",
        "Energy Assistance (LIHEAP)", "Childcare Subsidy (CCDF)", "Unemployment Insurance",
        "Disability (SSDI)", "SSI", "Veterans Benefits", "Foster Care",
        "Adoption Assistance", "Refugee Resettlement", "Substance Abuse Treatment",
        "Mental Health Services", "Domestic Violence Services", "Homeless Prevention",
        "Job Training (WIOA)"
    ]
    agency_names = [
        "County Social Services", "Family & Children Services", "Aging Services",
        "Disability Services", "Behavioral Health", "Community Action Agency",
        "Public Health Department", "Veterans Affairs", "Refugee Services",
        "Housing Authority", "Workforce Development", "Child Protective Services"
    ]

    batch_size = 500

    with get_neo4j_session() as session:
        # HHS Agencies
        session.run("""
            UNWIND $agencies AS a
            CREATE (ag:HHSAgency {
                agency_id: a.id, name: a.name, type: a.type,
                county: a.county, case_load: a.case_load,
                annual_budget: a.budget
            })
        """, agencies=[{
            "id": f"HHS-{i+1:03d}",
            "name": f"{random.choice(CITIES)} {random.choice(agency_names)}",
            "type": random.choice(agency_names),
            "county": f"{random.choice(CITIES)} County",
            "case_load": random.randint(500, 15000),
            "budget": round(random.uniform(1000000, 100000000), 2),
        } for i in range(num_agencies)])

        # Programs as nodes
        session.run("""
            UNWIND $programs AS p
            CREATE (pg:HHSProgram {
                program_id: p.id, name: p.name, category: p.category,
                federal_funded: p.federal, max_benefit: p.max_benefit,
                eligibility_criteria: p.criteria
            })
        """, programs=[{
            "id": f"HPGM-{i+1:02d}",
            "name": programs[i],
            "category": random.choice(["nutrition", "healthcare", "cash_assistance", "housing", "employment", "disability", "child_welfare"]),
            "federal": random.random() < 0.7,
            "max_benefit": round(random.uniform(200, 15000), 2),
            "criteria": random.choice(["income_based", "categorical", "means_tested", "universal", "age_based"]),
        } for i in range(len(programs))])

        # Agency manages programs
        session.run("""
            MATCH (ag:HHSAgency), (pg:HHSProgram)
            WITH ag, pg, rand() AS r WHERE r < 0.25
            CREATE (ag)-[:ADMINISTERS]->(pg)
        """)

        # Caseworkers
        for batch_start in range(0, num_caseworkers, batch_size):
            batch_end = min(batch_start + batch_size, num_caseworkers)
            session.run("""
                UNWIND $workers AS w
                MATCH (ag:HHSAgency {agency_id: w.agency_id})
                CREATE (cw:Caseworker {
                    caseworker_id: w.id, name: w.name,
                    specialization: w.spec, caseload: w.caseload,
                    years_experience: w.experience, license: w.license
                })-[:WORKS_AT]->(ag)
            """, workers=[{
                "id": f"CW-{i+1:04d}",
                "name": _rand_name(),
                "spec": random.choice(["generalist", "child_welfare", "mental_health", "disability", "elderly", "substance_abuse", "housing", "employment"]),
                "caseload": random.randint(15, 80),
                "experience": random.randint(1, 30),
                "license": random.choices(["LCSW", "LSW", "LMHC", "none", "MSW"], weights=[3, 3, 2, 1, 2])[0],
                "agency_id": f"HHS-{random.randint(1, num_agencies):03d}",
            } for i in range(batch_start, batch_end)])

        # Clients
        for batch_start in range(0, num_clients, batch_size):
            batch_end = min(batch_start + batch_size, num_clients)
            session.run("""
                UNWIND $clients AS c
                CREATE (cl:Client {
                    client_id: c.id, name: c.name, dob: c.dob,
                    household_size: c.hh_size, income_bracket: c.income,
                    county: c.county, zip_code: c.zip,
                    primary_language: c.language, veteran: c.veteran,
                    disabled: c.disabled
                })
            """, clients=[{
                "id": f"CLT-{i+1:05d}",
                "name": _rand_name(),
                "dob": f"{random.randint(1945, 2008)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
                "hh_size": random.choices([1,2,3,4,5,6,7,8], weights=[15,25,20,20,10,5,3,2])[0],
                "income": random.choices(["below_poverty", "low_income", "moderate_income"], weights=[4, 4, 2])[0],
                "county": f"{random.choice(CITIES)} County",
                "zip": f"{random.randint(10000, 99999)}",
                "language": random.choices(["English", "Spanish", "Chinese", "Vietnamese", "Arabic", "French", "Korean", "Russian"], weights=[60, 20, 5, 3, 3, 3, 3, 3])[0],
                "veteran": random.random() < 0.08,
                "disabled": random.random() < 0.15,
            } for i in range(batch_start, batch_end)])

        # Cases
        for batch_start in range(0, num_cases, batch_size):
            batch_end = min(batch_start + batch_size, num_cases)
            session.run("""
                UNWIND $cases AS c
                CREATE (cs:Case {
                    case_id: c.id, status: c.status,
                    opened_date: c.opened, closed_date: c.closed,
                    priority: c.priority, determination: c.determination,
                    referral_source: c.referral, benefit_amount: c.amount,
                    review_date: c.review_date
                })
            """, cases=[{
                "id": f"CASE-{i+1:05d}",
                "status": random.choices(["open", "under_review", "approved", "denied", "closed", "appealed"], weights=[3, 2, 4, 2, 3, 1])[0],
                "opened": _rand_date(2022, 2025).strftime("%Y-%m-%d"),
                "closed": _rand_date(2023, 2026).strftime("%Y-%m-%d") if random.random() > 0.4 else None,
                "priority": random.choices(["emergency", "urgent", "standard", "low"], weights=[1, 2, 5, 2])[0],
                "determination": random.choices(["approved", "denied", "pending", "deferred", "conditional"], weights=[5, 2, 2, 1, 1])[0],
                "referral": random.choices(["self", "agency", "community_org", "healthcare", "school", "court", "law_enforcement"], weights=[3, 3, 2, 2, 1, 1, 1])[0],
                "amount": round(random.uniform(0, 15000), 2),
                "review_date": _rand_date(2024, 2026).strftime("%Y-%m-%d"),
            } for i in range(batch_start, batch_end)])

        # Relationships
        # Client -> Case (HAS_CASE)
        session.run("""
            MATCH (cl:Client), (cs:Case)
            WITH cl, cs, rand() AS r ORDER BY r LIMIT $count
            CREATE (cl)-[:HAS_CASE {intake_date: cs.opened_date}]->(cs)
        """, count=num_cases)

        # Case -> Caseworker (MANAGED_BY)
        session.run("""
            MATCH (cs:Case) WHERE NOT (cs)-[:MANAGED_BY]->()
            WITH cs
            MATCH (cw:Caseworker) WITH cs, cw, rand() AS r ORDER BY r LIMIT 1
            CREATE (cs)-[:MANAGED_BY {assigned_date: cs.opened_date}]->(cw)
        """)

        # Case -> Program (ENROLLED_IN)
        session.run("""
            MATCH (cs:Case) WHERE cs.determination = 'approved'
            WITH cs
            MATCH (pg:HHSProgram) WITH cs, pg, rand() AS r ORDER BY r LIMIT toInteger(rand() * 2 + 1)
            CREATE (cs)-[:ENROLLED_IN {
                start_date: cs.opened_date,
                monthly_benefit: cs.benefit_amount,
                status: CASE toInteger(rand()*3) WHEN 0 THEN 'active' WHEN 1 THEN 'suspended' ELSE 'active' END
            }]->(pg)
        """)

        # Client referral chains (Client -> Client via REFERRED)
        session.run("""
            MATCH (c1:Client), (c2:Client)
            WHERE c1.client_id <> c2.client_id AND c1.county = c2.county
            WITH c1, c2, rand() AS r WHERE r < 0.003
            CREATE (c1)-[:REFERRED {date: toString(date()), source: 'community'}]->(c2)
        """)

        logger.info(f"Case management: created {num_agencies} agencies, {num_caseworkers} caseworkers, {num_clients} clients, {num_cases} cases")


# Neo4j clear functions
_NEO4J_CLEAR_LABELS = {
    SledUseCase.student_enrollment: ["Student", "Course", "Department", "DegreeProgram"],
    SledUseCase.grant_budget: ["FundingSource", "Agency", "Program", "Vendor", "LineItem"],
    SledUseCase.citizen_services: ["Citizen", "ServiceRequest", "ServiceDepartment", "Asset", "District"],
    SledUseCase.k12_early_warning: ["K12Student", "School", "Teacher", "RiskIndicator", "Intervention"],
    SledUseCase.procurement: ["ProcAgency", "ProcVendor", "Contract", "Lobbyist"],
    SledUseCase.case_management: ["Client", "Case", "Caseworker", "HHSAgency", "HHSProgram"],
}

_NEO4J_POPULATORS = {
    SledUseCase.student_enrollment: _neo4j_populate_student_enrollment,
    SledUseCase.grant_budget: _neo4j_populate_grant_budget,
    SledUseCase.citizen_services: _neo4j_populate_citizen_services,
    SledUseCase.k12_early_warning: _neo4j_populate_k12_early_warning,
    SledUseCase.procurement: _neo4j_populate_procurement,
    SledUseCase.case_management: _neo4j_populate_case_management,
}


# ============================ POSTGRES GENERATORS ============================

# Table definitions per use case (CREATE TABLE IF NOT EXISTS statements)
_PG_TABLES = {
    SledUseCase.student_enrollment: [
        """CREATE TABLE IF NOT EXISTS sled_students (
            student_id VARCHAR(12) PRIMARY KEY, name VARCHAR(100), email VARCHAR(120),
            enrollment_year INT, campus VARCHAR(30), gpa DECIMAL(3,2),
            total_credits INT, status VARCHAR(20), major VARCHAR(60),
            advisor VARCHAR(100), state VARCHAR(2), created_at TIMESTAMPTZ DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS sled_courses (
            course_id VARCHAR(12) PRIMARY KEY, name VARCHAR(120), department VARCHAR(60),
            level INT, credits INT, max_enrollment INT, semester VARCHAR(20),
            instructor VARCHAR(100), delivery_mode VARCHAR(20), created_at TIMESTAMPTZ DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS sled_enrollment_events (
            event_id VARCHAR(40) PRIMARY KEY, student_id VARCHAR(12), course_id VARCHAR(12),
            action VARCHAR(20), semester VARCHAR(20), grade VARCHAR(5),
            credits INT, campus VARCHAR(30), gpa_impact DECIMAL(4,2),
            event_timestamp TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW()
        )""",
    ],
    SledUseCase.grant_budget: [
        """CREATE TABLE IF NOT EXISTS sled_budget_transactions (
            transaction_id VARCHAR(40) PRIMARY KEY, fund_source_id VARCHAR(12),
            agency_id VARCHAR(12), program_id VARCHAR(12), vendor_id VARCHAR(12),
            transaction_type VARCHAR(30), amount DECIMAL(14,2), fund_category VARCHAR(40),
            fiscal_year INT, quarter VARCHAR(4), cost_center VARCHAR(12),
            account_code VARCHAR(8), description TEXT, approved_by VARCHAR(100),
            event_timestamp TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS sled_agencies (
            agency_id VARCHAR(12) PRIMARY KEY, name VARCHAR(120), type VARCHAR(40),
            jurisdiction VARCHAR(60), employee_count INT, annual_budget DECIMAL(14,2),
            state VARCHAR(2), created_at TIMESTAMPTZ DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS sled_vendors (
            vendor_id VARCHAR(12) PRIMARY KEY, name VARCHAR(120), type VARCHAR(40),
            state VARCHAR(2), minority_owned BOOLEAN, small_business BOOLEAN,
            woman_owned BOOLEAN, duns_number VARCHAR(12), annual_revenue DECIMAL(14,2),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""",
    ],
    SledUseCase.citizen_services: [
        """CREATE TABLE IF NOT EXISTS sled_service_requests (
            request_id VARCHAR(40) PRIMARY KEY, citizen_id VARCHAR(12),
            request_type VARCHAR(40), department VARCHAR(40), status VARCHAR(20),
            priority VARCHAR(10), district INT, asset_id VARCHAR(12),
            latitude DECIMAL(8,5), longitude DECIMAL(9,5),
            description TEXT, response_time_hours INT,
            satisfaction_rating INT, channel VARCHAR(20),
            event_timestamp TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS sled_citizens (
            citizen_id VARCHAR(12) PRIMARY KEY, name VARCHAR(100), email VARCHAR(120),
            phone VARCHAR(20), district INT, address VARCHAR(200),
            registered_date DATE, preferred_language VARCHAR(20),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS sled_assets (
            asset_id VARCHAR(12) PRIMARY KEY, type VARCHAR(30), condition VARCHAR(10),
            district INT, install_year INT, last_inspection DATE,
            latitude DECIMAL(8,5), longitude DECIMAL(9,5),
            replacement_cost DECIMAL(12,2), created_at TIMESTAMPTZ DEFAULT NOW()
        )""",
    ],
    SledUseCase.k12_early_warning: [
        """CREATE TABLE IF NOT EXISTS sled_k12_students (
            student_id VARCHAR(12) PRIMARY KEY, name VARCHAR(100), grade_level INT,
            school_id VARCHAR(12), gpa DECIMAL(3,2), attendance_rate DECIMAL(5,2),
            behavior_incidents_ytd INT, risk_score DECIMAL(5,2),
            free_reduced_lunch BOOLEAN, english_learner BOOLEAN,
            special_education BOOLEAN, gifted BOOLEAN, cohort_year INT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS sled_k12_events (
            event_id VARCHAR(40) PRIMARY KEY, student_id VARCHAR(12),
            school_id VARCHAR(12), event_type VARCHAR(30), grade_level INT,
            teacher_id VARCHAR(12), details TEXT, risk_score_delta DECIMAL(5,2),
            intervention_type VARCHAR(30), event_timestamp TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS sled_schools (
            school_id VARCHAR(12) PRIMARY KEY, name VARCHAR(120), type VARCHAR(20),
            enrollment INT, title_i BOOLEAN, graduation_rate DECIMAL(4,1),
            principal VARCHAR(100), district VARCHAR(60), state VARCHAR(2),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""",
    ],
    SledUseCase.procurement: [
        """CREATE TABLE IF NOT EXISTS sled_procurement_events (
            event_id VARCHAR(40) PRIMARY KEY, agency_id VARCHAR(12),
            vendor_id VARCHAR(12), event_type VARCHAR(30), contract_id VARCHAR(12),
            amount DECIMAL(14,2), procurement_method VARCHAR(30),
            commodity_code VARCHAR(6), category VARCHAR(40),
            minority_owned BOOLEAN, small_business BOOLEAN, local_vendor BOOLEAN,
            contract_duration_months INT, payment_terms VARCHAR(20),
            event_timestamp TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS sled_contracts (
            contract_id VARCHAR(12) PRIMARY KEY, title VARCHAR(200),
            agency_id VARCHAR(12), vendor_id VARCHAR(12),
            amount DECIMAL(14,2), method VARCHAR(30), category VARCHAR(40),
            status VARCHAR(20), start_date DATE, end_date DATE,
            duration_months INT, payment_terms VARCHAR(20),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""",
    ],
    SledUseCase.case_management: [
        """CREATE TABLE IF NOT EXISTS sled_case_events (
            event_id VARCHAR(40) PRIMARY KEY, client_id VARCHAR(12),
            case_id VARCHAR(12), caseworker_id VARCHAR(12),
            event_type VARCHAR(30), program VARCHAR(40), agency_id VARCHAR(12),
            benefit_amount DECIMAL(10,2), household_size INT,
            income_bracket VARCHAR(20), county VARCHAR(60),
            determination VARCHAR(20), referral_source VARCHAR(30),
            priority VARCHAR(20), event_timestamp TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS sled_clients (
            client_id VARCHAR(12) PRIMARY KEY, name VARCHAR(100),
            dob DATE, household_size INT, income_bracket VARCHAR(20),
            county VARCHAR(60), zip_code VARCHAR(10), primary_language VARCHAR(20),
            veteran BOOLEAN, disabled BOOLEAN, created_at TIMESTAMPTZ DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS sled_cases (
            case_id VARCHAR(12) PRIMARY KEY, client_id VARCHAR(12),
            caseworker_id VARCHAR(12), status VARCHAR(20),
            opened_date DATE, closed_date DATE, priority VARCHAR(20),
            determination VARCHAR(20), referral_source VARCHAR(30),
            benefit_amount DECIMAL(10,2), program VARCHAR(40),
            review_date DATE, created_at TIMESTAMPTZ DEFAULT NOW()
        )""",
    ],
}

# Table names per use case (for clearing)
_PG_TABLE_NAMES = {
    SledUseCase.student_enrollment: ["sled_enrollment_events", "sled_courses", "sled_students"],
    SledUseCase.grant_budget: ["sled_budget_transactions", "sled_vendors", "sled_agencies"],
    SledUseCase.citizen_services: ["sled_service_requests", "sled_assets", "sled_citizens"],
    SledUseCase.k12_early_warning: ["sled_k12_events", "sled_schools", "sled_k12_students"],
    SledUseCase.procurement: ["sled_procurement_events", "sled_contracts"],
    SledUseCase.case_management: ["sled_case_events", "sled_cases", "sled_clients"],
}


def _pg_create_tables(use_case: SledUseCase):
    """Create tables for a use case if they don't exist."""
    with engine.connect() as conn:
        for ddl in _PG_TABLES[use_case]:
            conn.execute(text(ddl))
        conn.commit()


def _pg_insert_batch(conn, table: str, rows: list[dict]):
    """Bulk insert rows into a table."""
    if not rows:
        return
    columns = rows[0].keys()
    col_list = ", ".join(columns)
    val_list = ", ".join([f":{c}" for c in columns])
    conn.execute(text(f"INSERT INTO {table} ({col_list}) VALUES ({val_list})"), rows)


def _pg_populate_student_enrollment(num_records: int):
    departments = [
        "Computer Science", "Mathematics", "English", "Biology", "Chemistry",
        "Physics", "History", "Psychology", "Business Administration", "Engineering",
        "Nursing", "Education", "Art", "Music", "Philosophy", "Political Science",
        "Sociology", "Economics"
    ]
    campuses = ["Main", "North", "Online", "Downtown", "West"]
    semesters = ["Fall 2023", "Spring 2024", "Summer 2024", "Fall 2024", "Spring 2025", "Summer 2025", "Fall 2025"]
    delivery_modes = ["in_person", "online", "hybrid"]
    actions = ["enroll", "drop", "transfer", "grade_posted", "waitlist"]
    action_weights = [5, 2, 1, 3, 1]
    grades = ["A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "F", "W", "IP"]
    grade_weights = [8, 6, 7, 10, 6, 5, 8, 4, 3, 2, 3, 15]
    statuses = ["active", "graduated", "on_leave", "suspended", "withdrawn"]
    status_weights = [60, 15, 10, 5, 10]
    course_prefixes = ["Introduction to", "Principles of", "Advanced", "Topics in", "Seminar in",
                        "Research Methods in", "Applied", "Foundations of", "Survey of", "Theory of"]

    num_students = num_records
    num_courses = min(num_records // 3, 2000)
    num_events = num_records * 2

    batch_size = 1000

    _pg_create_tables(SledUseCase.student_enrollment)

    with engine.connect() as conn:
        # Students
        for batch_start in range(0, num_students, batch_size):
            batch_end = min(batch_start + batch_size, num_students)
            _pg_insert_batch(conn, "sled_students", [{
                "student_id": f"STU-{i+1:06d}",
                "name": _rand_name(),
                "email": f"student{i+1}@university.edu",
                "enrollment_year": random.choice([2020, 2021, 2022, 2023, 2024, 2025]),
                "campus": random.choice(campuses),
                "gpa": round(random.uniform(1.5, 4.0), 2),
                "total_credits": random.randint(0, 132),
                "status": random.choices(statuses, weights=status_weights)[0],
                "major": random.choice(departments),
                "advisor": _rand_name(),
                "state": random.choice(STATES),
            } for i in range(batch_start, batch_end)])
        conn.commit()

        # Courses
        for batch_start in range(0, num_courses, batch_size):
            batch_end = min(batch_start + batch_size, num_courses)
            _pg_insert_batch(conn, "sled_courses", [{
                "course_id": f"CRS-{i+1:04d}",
                "name": f"{random.choice(course_prefixes)} {random.choice(departments)} {random.choice([100,200,300,400,500])+random.randint(0,9):03d}",
                "department": random.choice(departments),
                "level": random.choice([100, 200, 300, 400, 500]),
                "credits": random.choice([1, 2, 3, 3, 3, 4, 4]),
                "max_enrollment": random.choice([25, 30, 35, 40, 50, 100, 150, 200]),
                "semester": random.choice(semesters),
                "instructor": _rand_name(),
                "delivery_mode": random.choice(delivery_modes),
            } for i in range(batch_start, batch_end)])
        conn.commit()

        # Events
        for batch_start in range(0, num_events, batch_size):
            batch_end = min(batch_start + batch_size, num_events)
            _pg_insert_batch(conn, "sled_enrollment_events", [{
                "event_id": str(uuid.uuid4()),
                "student_id": f"STU-{random.randint(1, num_students):06d}",
                "course_id": f"CRS-{random.randint(1, num_courses):04d}",
                "action": random.choices(actions, weights=action_weights)[0],
                "semester": random.choice(semesters),
                "grade": random.choices(grades, weights=grade_weights)[0],
                "credits": random.choice([1, 2, 3, 3, 3, 4, 4]),
                "campus": random.choice(campuses),
                "gpa_impact": round(random.uniform(-2.0, 2.0), 2),
                "event_timestamp": _rand_date().isoformat(),
            } for i in range(batch_start, batch_end)])
        conn.commit()

    logger.info(f"PG student enrollment: {num_students} students, {num_courses} courses, {num_events} events")


def _pg_populate_grant_budget(num_records: int):
    fund_categories = ["federal_grant", "state_appropriation", "local_revenue", "bond_proceeds",
                       "tuition_fees", "endowment", "auxiliary", "research_grant"]
    transaction_types = ["allocation", "expenditure", "transfer", "encumbrance", "reimbursement", "adjustment"]
    tx_weights = [2, 5, 1, 2, 1, 1]
    agency_types = ["School District", "County", "City", "State Agency", "Authority", "University"]
    vendor_types = ["Contractor", "Supplier", "Consultant", "Technology", "Services", "Construction"]
    descriptions = ["Personnel costs -", "Equipment purchase -", "Professional services for",
                    "Facilities maintenance -", "Software licensing -", "Travel and training -",
                    "Capital improvement -", "Consulting fees for", "Research equipment -",
                    "Program supplies for", "Building renovation -", "IT infrastructure for"]
    program_names = ["Infrastructure", "Public Safety", "Youth Development", "Senior Services",
                     "Education Technology", "Workforce Training", "Community Health",
                     "Housing Development", "Digital Equity", "Economic Development"]

    num_agencies = min(num_records // 100, 50)
    num_vendors = min(num_records // 5, 2000)
    num_transactions = num_records

    batch_size = 1000
    _pg_create_tables(SledUseCase.grant_budget)

    with engine.connect() as conn:
        # Agencies
        _pg_insert_batch(conn, "sled_agencies", [{
            "agency_id": f"AGY-{i+1:03d}",
            "name": f"{random.choice(CITIES)} {random.choice(agency_types)}",
            "type": random.choice(agency_types),
            "jurisdiction": random.choice(CITIES),
            "employee_count": random.randint(20, 5000),
            "annual_budget": round(random.uniform(500000, 500000000), 2),
            "state": random.choice(STATES),
        } for i in range(num_agencies)])
        conn.commit()

        # Vendors
        for batch_start in range(0, num_vendors, batch_size):
            batch_end = min(batch_start + batch_size, num_vendors)
            _pg_insert_batch(conn, "sled_vendors", [{
                "vendor_id": f"VND-{i+1:04d}",
                "name": f"{random.choice(LAST_NAMES)} {random.choice(vendor_types)} {random.choice(['LLC', 'Inc.', 'Corp.'])}",
                "type": random.choice(vendor_types),
                "state": random.choice(STATES),
                "minority_owned": random.random() < 0.18,
                "small_business": random.random() < 0.35,
                "woman_owned": random.random() < 0.15,
                "duns_number": f"{random.randint(100000000, 999999999)}",
                "annual_revenue": round(random.uniform(100000, 100000000), 2),
            } for i in range(batch_start, batch_end)])
        conn.commit()

        # Transactions
        for batch_start in range(0, num_transactions, batch_size):
            batch_end = min(batch_start + batch_size, num_transactions)
            _pg_insert_batch(conn, "sled_budget_transactions", [{
                "transaction_id": str(uuid.uuid4()),
                "fund_source_id": f"FUND-{random.randint(1, 200):03d}",
                "agency_id": f"AGY-{random.randint(1, num_agencies):03d}",
                "program_id": f"PGM-{random.randint(1, 500):04d}",
                "vendor_id": f"VND-{random.randint(1, num_vendors):04d}",
                "transaction_type": random.choices(transaction_types, weights=tx_weights)[0],
                "amount": round(random.uniform(100, 5000000), 2),
                "fund_category": random.choice(fund_categories),
                "fiscal_year": random.choice([2023, 2024, 2025, 2026]),
                "quarter": random.choice(["Q1", "Q2", "Q3", "Q4"]),
                "cost_center": f"CC-{random.randint(1, 300):04d}",
                "account_code": f"{random.randint(1000, 9999)}",
                "description": f"{random.choice(descriptions)} {random.choice(program_names)}",
                "approved_by": _rand_name(),
                "event_timestamp": _rand_date().isoformat(),
            } for i in range(batch_start, batch_end)])
        conn.commit()

    logger.info(f"PG grant budget: {num_agencies} agencies, {num_vendors} vendors, {num_transactions} transactions")


def _pg_populate_citizen_services(num_records: int):
    request_types = [
        "pothole_repair", "streetlight_outage", "water_main_break", "noise_complaint",
        "illegal_dumping", "graffiti_removal", "tree_trimming", "sidewalk_repair",
        "traffic_signal", "building_inspection", "permit_application", "animal_control",
        "park_maintenance", "snow_removal", "sewer_backup", "abandoned_vehicle"
    ]
    departments = ["Public Works", "Transportation", "Water", "Code Enforcement",
                   "Parks", "Building", "Police", "Fire", "Health", "Environmental"]
    statuses = ["opened", "assigned", "in_progress", "pending_review", "resolved", "closed", "reopened"]
    status_weights = [2, 2, 3, 1, 4, 5, 1]
    priorities = ["critical", "high", "medium", "low"]
    priority_weights = [1, 2, 4, 3]
    channels = ["phone", "web", "mobile_app", "walk_in", "email", "social_media"]
    asset_types = ["Road Segment", "Bridge", "Building", "Park", "Water Main", "Sewer Line",
                   "Traffic Signal", "Streetlight", "Fire Hydrant", "Playground"]

    num_citizens = num_records
    num_assets = min(num_records // 2, 10000)
    num_requests = num_records * 2

    batch_size = 1000
    _pg_create_tables(SledUseCase.citizen_services)

    with engine.connect() as conn:
        # Citizens
        for batch_start in range(0, num_citizens, batch_size):
            batch_end = min(batch_start + batch_size, num_citizens)
            _pg_insert_batch(conn, "sled_citizens", [{
                "citizen_id": f"CIT-{i+1:05d}",
                "name": _rand_name(),
                "email": f"citizen{i+1}@email.com",
                "phone": f"({random.randint(200,999)}) {random.randint(200,999)}-{random.randint(1000,9999)}",
                "district": random.randint(1, 15),
                "address": f"{random.randint(100, 9999)} {random.choice(STREET_NAMES)}, {random.choice(CITIES)}",
                "registered_date": _rand_date(2018, 2025).strftime("%Y-%m-%d"),
                "preferred_language": random.choices(["English", "Spanish", "Chinese", "Vietnamese", "Arabic"], weights=[65, 20, 5, 5, 5])[0],
            } for i in range(batch_start, batch_end)])
        conn.commit()

        # Assets
        for batch_start in range(0, num_assets, batch_size):
            batch_end = min(batch_start + batch_size, num_assets)
            _pg_insert_batch(conn, "sled_assets", [{
                "asset_id": f"AST-{i+1:05d}",
                "type": random.choice(asset_types),
                "condition": random.choices(["good", "fair", "poor", "critical"], weights=[4, 3, 2, 1])[0],
                "district": random.randint(1, 15),
                "install_year": random.randint(1970, 2024),
                "last_inspection": _rand_date(2022, 2025).strftime("%Y-%m-%d"),
                "latitude": round(random.uniform(38.8, 39.4), 5),
                "longitude": round(random.uniform(-77.2, -76.6), 5),
                "replacement_cost": round(random.uniform(5000, 2000000), 2),
            } for i in range(batch_start, batch_end)])
        conn.commit()

        # Service requests
        for batch_start in range(0, num_requests, batch_size):
            batch_end = min(batch_start + batch_size, num_requests)
            _pg_insert_batch(conn, "sled_service_requests", [{
                "request_id": str(uuid.uuid4()),
                "citizen_id": f"CIT-{random.randint(1, num_citizens):05d}",
                "request_type": random.choice(request_types),
                "department": random.choice(departments),
                "status": random.choices(statuses, weights=status_weights)[0],
                "priority": random.choices(priorities, weights=priority_weights)[0],
                "district": random.randint(1, 15),
                "asset_id": f"AST-{random.randint(1, num_assets):05d}" if random.random() > 0.3 else None,
                "latitude": round(random.uniform(38.8, 39.4), 5),
                "longitude": round(random.uniform(-77.2, -76.6), 5),
                "description": f"{random.choice(request_types).replace('_', ' ').title()} at {random.randint(100, 9999)} {random.choice(STREET_NAMES)}",
                "response_time_hours": random.randint(1, 720),
                "satisfaction_rating": random.randint(1, 5) if random.random() > 0.4 else None,
                "channel": random.choice(channels),
                "event_timestamp": _rand_date(2023, 2025).isoformat(),
            } for i in range(batch_start, batch_end)])
        conn.commit()

    logger.info(f"PG citizen services: {num_citizens} citizens, {num_assets} assets, {num_requests} requests")


def _pg_populate_k12_early_warning(num_records: int):
    school_types = ["elementary", "middle", "high"]
    school_type_weights = [5, 3, 2]
    event_types = ["attendance", "discipline", "assessment", "intervention",
                   "counselor_note", "parent_contact", "iep_review", "health_screening"]
    event_weights = [10, 3, 5, 2, 2, 2, 1, 1]
    intervention_types = ["tutoring", "mentoring", "counseling", "parent_conference",
                          "schedule_change", "behavioral_plan", "after_school", "none"]
    intervention_weights = [2, 2, 2, 2, 1, 1, 1, 8]
    school_prefixes = ["Washington", "Lincoln", "Jefferson", "Roosevelt", "King",
                       "Kennedy", "Franklin", "Oakwood", "Riverside", "Lakewood"]

    num_schools = min(num_records // 50, 100)
    num_students = num_records
    num_events = num_records * 3

    batch_size = 1000
    _pg_create_tables(SledUseCase.k12_early_warning)

    with engine.connect() as conn:
        # Schools
        _pg_insert_batch(conn, "sled_schools", [{
            "school_id": f"SCH-{i+1:03d}",
            "name": f"{school_prefixes[i % len(school_prefixes)]} {random.choice(school_types).title()} School",
            "type": random.choices(school_types, weights=school_type_weights)[0],
            "enrollment": random.randint(200, 2500),
            "title_i": random.random() < 0.55,
            "graduation_rate": round(random.uniform(65, 99), 1) if random.random() > 0.3 else None,
            "principal": _rand_name(),
            "district": f"{random.choice(CITIES)} School District",
            "state": random.choice(STATES),
        } for i in range(num_schools)])
        conn.commit()

        # Students
        for batch_start in range(0, num_students, batch_size):
            batch_end = min(batch_start + batch_size, num_students)
            _pg_insert_batch(conn, "sled_k12_students", [{
                "student_id": f"K12-{i+1:05d}",
                "name": _rand_name(),
                "grade_level": random.randint(1, 12),
                "school_id": f"SCH-{random.randint(1, num_schools):03d}",
                "gpa": round(random.uniform(0.5, 4.0), 2),
                "attendance_rate": round(random.uniform(60, 100), 1),
                "behavior_incidents_ytd": random.choices(range(0, 15), weights=[50]+[10]+[8]+[6]+[5]+[4]+[3]+[2]+[2]+[2]+[1]*5)[0],
                "risk_score": round(random.uniform(0, 100), 1),
                "free_reduced_lunch": random.random() < 0.45,
                "english_learner": random.random() < 0.15,
                "special_education": random.random() < 0.13,
                "gifted": random.random() < 0.08,
                "cohort_year": random.choice([2020, 2021, 2022, 2023, 2024]),
            } for i in range(batch_start, batch_end)])
        conn.commit()

        # Events
        for batch_start in range(0, num_events, batch_size):
            batch_end = min(batch_start + batch_size, num_events)
            _pg_insert_batch(conn, "sled_k12_events", [{
                "event_id": str(uuid.uuid4()),
                "student_id": f"K12-{random.randint(1, num_students):05d}",
                "school_id": f"SCH-{random.randint(1, num_schools):03d}",
                "event_type": random.choices(event_types, weights=event_weights)[0],
                "grade_level": random.randint(1, 12),
                "teacher_id": f"TCH-{random.randint(1, 3000):04d}",
                "details": f"{random.choices(event_types, weights=event_weights)[0].replace('_', ' ').title()} event recorded",
                "risk_score_delta": round(random.uniform(-10, 15), 2),
                "intervention_type": random.choices(intervention_types, weights=intervention_weights)[0],
                "event_timestamp": _rand_date(2023, 2025).isoformat(),
            } for i in range(batch_start, batch_end)])
        conn.commit()

    logger.info(f"PG K12: {num_schools} schools, {num_students} students, {num_events} events")


def _pg_populate_procurement(num_records: int):
    event_types = ["rfp_posted", "bid_submitted", "bid_withdrawn", "contract_awarded",
                   "purchase_order", "invoice_submitted", "invoice_paid",
                   "contract_amended", "contract_terminated"]
    event_weights = [2, 4, 1, 2, 3, 4, 3, 1, 1]
    methods = ["competitive_bid", "sole_source", "emergency", "cooperative", "micro_purchase", "rfq"]
    method_weights = [5, 2, 1, 2, 3, 2]
    categories = ["construction", "professional_services", "it_services", "equipment",
                  "supplies", "facilities", "consulting", "staffing", "transportation", "utilities"]
    terms = ["net_30", "net_45", "net_60", "upon_delivery"]
    statuses = ["active", "completed", "pending", "terminated", "expired"]
    status_weights = [4, 3, 1, 1, 1]

    num_contracts = min(num_records // 2, 5000)
    num_events = num_records

    batch_size = 1000
    _pg_create_tables(SledUseCase.procurement)

    with engine.connect() as conn:
        # Contracts
        for batch_start in range(0, num_contracts, batch_size):
            batch_end = min(batch_start + batch_size, num_contracts)
            _pg_insert_batch(conn, "sled_contracts", [{
                "contract_id": f"CTR-{i+1:05d}",
                "title": f"{random.choice(categories).replace('_', ' ').title()} - Project {random.randint(1, 999)}",
                "agency_id": f"AGY-{random.randint(1, 50):03d}",
                "vendor_id": f"VND-{random.randint(1, 3000):04d}",
                "amount": round(random.uniform(5000, 25000000), 2),
                "method": random.choices(methods, weights=method_weights)[0],
                "category": random.choice(categories),
                "status": random.choices(statuses, weights=status_weights)[0],
                "start_date": _rand_date(2022, 2025).strftime("%Y-%m-%d"),
                "end_date": _rand_date(2024, 2028).strftime("%Y-%m-%d"),
                "duration_months": random.choice([3, 6, 12, 18, 24, 36, 48, 60]),
                "payment_terms": random.choice(terms),
            } for i in range(batch_start, batch_end)])
        conn.commit()

        # Procurement events
        for batch_start in range(0, num_events, batch_size):
            batch_end = min(batch_start + batch_size, num_events)
            _pg_insert_batch(conn, "sled_procurement_events", [{
                "event_id": str(uuid.uuid4()),
                "agency_id": f"AGY-{random.randint(1, 50):03d}",
                "vendor_id": f"VND-{random.randint(1, 3000):04d}",
                "event_type": random.choices(event_types, weights=event_weights)[0],
                "contract_id": f"CTR-{random.randint(1, num_contracts):05d}",
                "amount": round(random.uniform(500, 25000000), 2),
                "procurement_method": random.choices(methods, weights=method_weights)[0],
                "commodity_code": f"{random.randint(100, 999)}",
                "category": random.choice(categories),
                "minority_owned": random.random() < 0.18,
                "small_business": random.random() < 0.35,
                "local_vendor": random.random() < 0.40,
                "contract_duration_months": random.choice([3, 6, 12, 18, 24, 36, 48, 60]),
                "payment_terms": random.choice(terms),
                "event_timestamp": _rand_date(2023, 2025).isoformat(),
            } for i in range(batch_start, batch_end)])
        conn.commit()

    logger.info(f"PG procurement: {num_contracts} contracts, {num_events} events")


def _pg_populate_case_management(num_records: int):
    event_types = ["intake", "referral", "eligibility_determination", "benefit_disbursement",
                   "review", "closure", "appeal", "transfer"]
    event_weights = [3, 2, 3, 4, 2, 2, 1, 1]
    programs = ["SNAP", "Medicaid", "TANF", "WIC", "CHIP", "housing_assistance",
                "energy_assistance", "childcare_subsidy", "unemployment", "disability"]
    program_weights = [5, 5, 3, 3, 2, 2, 2, 2, 2, 2]
    determinations = ["approved", "denied", "pending", "deferred", "conditional"]
    det_weights = [5, 2, 2, 1, 1]
    referrals = ["self", "agency", "community_org", "healthcare", "school", "court"]
    ref_weights = [3, 3, 2, 2, 1, 1]
    priorities = ["emergency", "urgent", "standard", "low"]
    pri_weights = [1, 2, 5, 2]
    statuses = ["open", "under_review", "approved", "denied", "closed", "appealed"]
    status_weights = [3, 2, 4, 2, 3, 1]
    languages = ["English", "Spanish", "Chinese", "Vietnamese", "Arabic", "French", "Korean", "Russian"]
    lang_weights = [60, 20, 5, 3, 3, 3, 3, 3]

    num_clients = num_records
    num_cases = int(num_records * 1.5)
    num_events = num_records * 2

    batch_size = 1000
    _pg_create_tables(SledUseCase.case_management)

    with engine.connect() as conn:
        # Clients
        for batch_start in range(0, num_clients, batch_size):
            batch_end = min(batch_start + batch_size, num_clients)
            _pg_insert_batch(conn, "sled_clients", [{
                "client_id": f"CLT-{i+1:05d}",
                "name": _rand_name(),
                "dob": f"{random.randint(1945, 2008)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
                "household_size": random.choices([1,2,3,4,5,6,7,8], weights=[15,25,20,20,10,5,3,2])[0],
                "income_bracket": random.choices(["below_poverty", "low_income", "moderate_income"], weights=[4, 4, 2])[0],
                "county": f"{random.choice(CITIES)} County",
                "zip_code": f"{random.randint(10000, 99999)}",
                "primary_language": random.choices(languages, weights=lang_weights)[0],
                "veteran": random.random() < 0.08,
                "disabled": random.random() < 0.15,
            } for i in range(batch_start, batch_end)])
        conn.commit()

        # Cases
        for batch_start in range(0, num_cases, batch_size):
            batch_end = min(batch_start + batch_size, num_cases)
            _pg_insert_batch(conn, "sled_cases", [{
                "case_id": f"CASE-{i+1:05d}",
                "client_id": f"CLT-{random.randint(1, num_clients):05d}",
                "caseworker_id": f"CW-{random.randint(1, 1500):04d}",
                "status": random.choices(statuses, weights=status_weights)[0],
                "opened_date": _rand_date(2022, 2025).strftime("%Y-%m-%d"),
                "closed_date": _rand_date(2023, 2026).strftime("%Y-%m-%d") if random.random() > 0.4 else None,
                "priority": random.choices(priorities, weights=pri_weights)[0],
                "determination": random.choices(determinations, weights=det_weights)[0],
                "referral_source": random.choices(referrals, weights=ref_weights)[0],
                "benefit_amount": round(random.uniform(0, 15000), 2),
                "program": random.choices(programs, weights=program_weights)[0],
                "review_date": _rand_date(2024, 2026).strftime("%Y-%m-%d"),
            } for i in range(batch_start, batch_end)])
        conn.commit()

        # Case events
        for batch_start in range(0, num_events, batch_size):
            batch_end = min(batch_start + batch_size, num_events)
            _pg_insert_batch(conn, "sled_case_events", [{
                "event_id": str(uuid.uuid4()),
                "client_id": f"CLT-{random.randint(1, num_clients):05d}",
                "case_id": f"CASE-{random.randint(1, num_cases):05d}",
                "caseworker_id": f"CW-{random.randint(1, 1500):04d}",
                "event_type": random.choices(event_types, weights=event_weights)[0],
                "program": random.choices(programs, weights=program_weights)[0],
                "agency_id": f"HHS-{random.randint(1, 30):03d}",
                "benefit_amount": round(random.uniform(0, 15000), 2),
                "household_size": random.choices([1,2,3,4,5,6,7,8], weights=[15,25,20,20,10,5,3,2])[0],
                "income_bracket": random.choices(["below_poverty", "low_income", "moderate_income"], weights=[4, 4, 2])[0],
                "county": f"{random.choice(CITIES)} County",
                "determination": random.choices(determinations, weights=det_weights)[0],
                "referral_source": random.choices(referrals, weights=ref_weights)[0],
                "priority": random.choices(priorities, weights=pri_weights)[0],
                "event_timestamp": _rand_date(2023, 2025).isoformat(),
            } for i in range(batch_start, batch_end)])
        conn.commit()

    logger.info(f"PG case management: {num_clients} clients, {num_cases} cases, {num_events} events")


_PG_POPULATORS = {
    SledUseCase.student_enrollment: _pg_populate_student_enrollment,
    SledUseCase.grant_budget: _pg_populate_grant_budget,
    SledUseCase.citizen_services: _pg_populate_citizen_services,
    SledUseCase.k12_early_warning: _pg_populate_k12_early_warning,
    SledUseCase.procurement: _pg_populate_procurement,
    SledUseCase.case_management: _pg_populate_case_management,
}


# ==================== NEO4J ENDPOINTS (under /data-sources/neo4j/sled) ====================

@neo4j_router.post("/{use_case}/populate", response_model=PopulateResponse)
async def populate_neo4j(use_case: SledUseCase, request: PopulateRequest = PopulateRequest()):
    """Populate Neo4j with mock graph data for a SLED use case. Runs in background for large datasets."""
    job_id = str(uuid.uuid4())[:8]

    if use_case not in _NEO4J_POPULATORS:
        raise HTTPException(status_code=400, detail=f"Unknown use case: {use_case}")

    state = {"job_id": job_id, "use_case": use_case.value, "target": "neo4j",
             "status": "running", "num_records": request.num_records}
    _active_jobs[job_id] = state

    async def _run():
        try:
            populator = _NEO4J_POPULATORS[use_case]
            await asyncio.get_event_loop().run_in_executor(None, populator, request.num_records)
            state["status"] = "completed"
        except Exception as e:
            logger.error(f"Neo4j populate error for {use_case}: {e}", exc_info=True)
            state["status"] = "error"
            state["error"] = str(e)

    asyncio.create_task(_run())

    return PopulateResponse(
        use_case=use_case.value, target="neo4j", status="running",
        job_id=job_id, num_records=request.num_records
    )


@neo4j_router.delete("/{use_case}/clear", response_model=ClearResponse)
async def clear_neo4j(use_case: SledUseCase):
    """Clear all Neo4j nodes and relationships for a SLED use case."""
    labels = _NEO4J_CLEAR_LABELS.get(use_case, [])
    deleted = {}
    with get_neo4j_session() as session:
        for label in labels:
            result = session.run(f"MATCH (n:{label}) DETACH DELETE n RETURN count(n) AS count")
            record = result.single()
            deleted[label] = record["count"] if record else 0
    return ClearResponse(use_case=use_case.value, target="neo4j", status="cleared", details=deleted)


@neo4j_router.get("/{use_case}/status", response_model=StatusResponse)
async def neo4j_status(use_case: SledUseCase):
    """Get node and relationship counts for a SLED use case in Neo4j."""
    labels = _NEO4J_CLEAR_LABELS.get(use_case, [])
    counts = {}
    with get_neo4j_session() as session:
        for label in labels:
            result = session.run(f"MATCH (n:{label}) RETURN count(n) AS count")
            record = result.single()
            counts[label] = record["count"] if record else 0
        result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) AS type, count(r) AS count
        """)
        rel_counts = {record["type"]: record["count"] for record in result}
        counts["_relationships"] = rel_counts
    return StatusResponse(use_case=use_case.value, target="neo4j", counts=counts)


# =================== POSTGRES ENDPOINTS (under /data-sources/sled) ===================

@postgres_router.post("/{use_case}/populate", response_model=PopulateResponse)
async def populate_postgres(use_case: SledUseCase, request: PopulateRequest = PopulateRequest()):
    """Populate PostgreSQL with mock relational data for a SLED use case."""
    job_id = str(uuid.uuid4())[:8]

    if use_case not in _PG_POPULATORS:
        raise HTTPException(status_code=400, detail=f"Unknown use case: {use_case}")

    state = {"job_id": job_id, "use_case": use_case.value, "target": "postgres",
             "status": "running", "num_records": request.num_records}
    _active_jobs[job_id] = state

    async def _run():
        try:
            populator = _PG_POPULATORS[use_case]
            await asyncio.get_event_loop().run_in_executor(None, populator, request.num_records)
            state["status"] = "completed"
        except Exception as e:
            logger.error(f"Postgres populate error for {use_case}: {e}", exc_info=True)
            state["status"] = "error"
            state["error"] = str(e)

    asyncio.create_task(_run())

    return PopulateResponse(
        use_case=use_case.value, target="postgres", status="running",
        job_id=job_id, num_records=request.num_records
    )


@postgres_router.delete("/{use_case}/clear", response_model=ClearResponse)
async def clear_postgres(use_case: SledUseCase):
    """Clear all PostgreSQL tables for a SLED use case (TRUNCATE)."""
    tables = _PG_TABLE_NAMES.get(use_case, [])
    cleared = {}
    with engine.connect() as conn:
        for table in tables:
            try:
                result = conn.execute(text(f"SELECT count(*) FROM {table}"))
                count = result.scalar()
                conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
                cleared[table] = count
            except Exception:
                cleared[table] = "table_not_found"
        conn.commit()
    return ClearResponse(use_case=use_case.value, target="postgres", status="cleared", details=cleared)


@postgres_router.get("/{use_case}/status", response_model=StatusResponse)
async def postgres_status(use_case: SledUseCase):
    """Get row counts for a SLED use case's PostgreSQL tables."""
    tables = _PG_TABLE_NAMES.get(use_case, [])
    counts = {}
    with engine.connect() as conn:
        for table in tables:
            try:
                result = conn.execute(text(f"SELECT count(*) FROM {table}"))
                counts[table] = result.scalar()
            except Exception:
                counts[table] = 0
    return StatusResponse(use_case=use_case.value, target="postgres", counts=counts)


# ======================= SHARED JOB TRACKING =======================

@neo4j_router.get("/jobs")
async def list_neo4j_jobs():
    """List all Neo4j populate jobs and their status."""
    return [j for j in _active_jobs.values() if j.get("target") == "neo4j"]


@postgres_router.get("/jobs")
async def list_postgres_jobs():
    """List all Postgres populate jobs and their status."""
    return [j for j in _active_jobs.values() if j.get("target") == "postgres"]


@neo4j_router.delete("/jobs/cleanup")
async def cleanup_neo4j_jobs():
    """Remove completed/errored Neo4j jobs."""
    to_remove = [jid for jid, s in _active_jobs.items() if s["status"] != "running" and s.get("target") == "neo4j"]
    for jid in to_remove:
        del _active_jobs[jid]
    return {"removed": len(to_remove), "active": sum(1 for s in _active_jobs.values() if s.get("target") == "neo4j")}


@postgres_router.delete("/jobs/cleanup")
async def cleanup_postgres_jobs():
    """Remove completed/errored Postgres jobs."""
    to_remove = [jid for jid, s in _active_jobs.items() if s["status"] != "running" and s.get("target") == "postgres"]
    for jid in to_remove:
        del _active_jobs[jid]
    return {"removed": len(to_remove), "active": sum(1 for s in _active_jobs.values() if s.get("target") == "postgres")}
