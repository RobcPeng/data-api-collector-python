import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from confluent_kafka import Producer
from fastapi import FastAPI
from pydantic import BaseModel, Field
from pyspark.sql import SparkSession

import dbldatagen as dg

app = FastAPI(title="Spark Generator Service", version="0.1.0")

KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------
_active_generators: dict[str, dict] = {}
_spark: SparkSession | None = None


def _get_spark() -> SparkSession:
    global _spark
    if _spark is None or _spark._jsc.sc().isStopped():
        _spark = (
            SparkSession.builder
            .master("local[2]")
            .appName("spark-generator-service")
            .config("spark.sql.shuffle.partitions", "2")
            .config("spark.ui.enabled", "false")
            .config("spark.driver.memory", "512m")
            .getOrCreate()
        )
    return _spark


def _get_producer() -> Producer:
    return Producer({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})


# ---------------------------------------------------------------------------
# Use-case definitions (dbldatagen DataGenerators)
# ---------------------------------------------------------------------------
class UseCase(str, Enum):
    fraud_detection = "fraud_detection"
    telemetry = "telemetry"
    web_traffic = "web_traffic"
    student_enrollment = "student_enrollment"
    grant_budget = "grant_budget"
    citizen_services = "citizen_services"
    k12_early_warning = "k12_early_warning"
    procurement = "procurement"
    case_management = "case_management"


def _build_fraud_spec(spark: SparkSession, rows: int, num_users: int = 5000, num_merchants: int = 500) -> dg.DataGenerator:
    return (
        dg.DataGenerator(spark, name="fraud_transactions", rows=rows, partitions=2)
        .withColumn("transaction_id", "string", expr="uuid()")
        .withColumn("user_id", "integer", minValue=1, maxValue=num_users)
        .withColumn("merchant_id", "integer", minValue=1, maxValue=num_merchants)
        .withColumn("amount", "decimal(10,2)", minValue=0.50, maxValue=15000.00, random=True)
        .withColumn("currency", "string", values=["USD", "EUR", "GBP", "CAD", "AUD"], random=True, weights=[5, 2, 1, 1, 1])
        .withColumn("merchant_category", "string",
                    values=["grocery", "electronics", "gas_station", "restaurant",
                            "online_retail", "travel", "entertainment", "healthcare",
                            "atm_withdrawal", "money_transfer"],
                    random=True)
        .withColumn("payment_method", "string",
                    values=["chip", "contactless", "online", "swipe", "mobile_wallet"],
                    random=True, weights=[3, 3, 3, 1, 2])
        .withColumn("ip_address", "string",
                    expr="concat(int(rand()*223+1), '.', int(rand()*256), '.', int(rand()*256), '.', int(rand()*256))")
        .withColumn("device_id", "string",
                    expr="concat('dev-', lpad(cast(int(rand()*10000) as string), 4, '0'), '-', lpad(cast(int(rand()*10000) as string), 4, '0'))")
        .withColumn("latitude", "decimal(8,5)", minValue=-90.0, maxValue=90.0, random=True)
        .withColumn("longitude", "decimal(9,5)", minValue=-180.0, maxValue=180.0, random=True)
        .withColumn("card_type", "string", values=["visa", "mastercard", "amex", "discover"], random=True, weights=[4, 3, 2, 1])
    )


def _build_telemetry_spec(spark: SparkSession, rows: int, num_devices: int = 1000) -> dg.DataGenerator:
    return (
        dg.DataGenerator(spark, name="device_telemetry", rows=rows, partitions=2)
        .withColumn("event_id", "string", expr="uuid()")
        .withColumn("device_id", "string",
                    expr="concat('iot-', lpad(cast(int(rand()*10000) as string), 4, '0'), '-', lpad(cast(int(rand()*10000) as string), 4, '0'))")
        .withColumn("device_type", "string",
                    values=["temperature_sensor", "pressure_sensor", "humidity_sensor",
                            "motion_detector", "air_quality", "vibration_sensor",
                            "light_sensor", "flow_meter"],
                    random=True)
        .withColumn("reading_value", "decimal(10,4)", minValue=-50.0, maxValue=500.0, random=True)
        .withColumn("unit", "string",
                    values=["celsius", "psi", "percent", "boolean", "ppm", "mm_s", "lux", "l_min"],
                    random=True)
        .withColumn("battery_level", "decimal(5,2)", minValue=0.0, maxValue=100.0, random=True)
        .withColumn("signal_strength_dbm", "integer", minValue=-120, maxValue=-30, random=True)
        .withColumn("firmware_version", "string", values=["1.0.0", "1.1.0", "1.2.3", "2.0.0", "2.1.0"], random=True)
        .withColumn("facility_id", "integer", minValue=1, maxValue=50, random=True)
        .withColumn("latitude", "decimal(8,5)", minValue=25.0, maxValue=48.0, random=True)
        .withColumn("longitude", "decimal(9,5)", minValue=-125.0, maxValue=-70.0, random=True)
        .withColumn("anomaly_flag", "boolean", expr="rand() < 0.05")
    )


def _build_web_traffic_spec(spark: SparkSession, rows: int, num_users: int = 10000) -> dg.DataGenerator:
    return (
        dg.DataGenerator(spark, name="web_traffic", rows=rows, partitions=2)
        .withColumn("event_id", "string", expr="uuid()")
        .withColumn("session_id", "string",
                    expr="concat('sess-', lpad(cast(int(rand()*10000) as string), 4, '0'), '-', lpad(cast(int(rand()*10000) as string), 4, '0'), '-', lpad(cast(int(rand()*10000) as string), 4, '0'))")
        .withColumn("user_id", "integer", minValue=1, maxValue=num_users)
        .withColumn("page_url", "string",
                    values=["/home", "/products", "/products/detail", "/cart",
                            "/checkout", "/account", "/search", "/blog",
                            "/support", "/api/v1/data"],
                    random=True, weights=[5, 4, 3, 2, 1, 2, 3, 2, 1, 1])
        .withColumn("referrer", "string",
                    values=["direct", "google", "bing", "facebook", "twitter",
                            "linkedin", "email_campaign", "affiliate", "internal"],
                    random=True, weights=[3, 4, 1, 2, 1, 1, 2, 1, 3])
        .withColumn("user_agent", "string",
                    values=["Chrome/125", "Firefox/130", "Safari/18", "Edge/125",
                            "Mobile-Chrome/125", "Mobile-Safari/18", "Bot/1.0"],
                    random=True, weights=[4, 2, 2, 1, 3, 2, 1])
        .withColumn("ip_address", "string",
                    expr="concat(int(rand()*223+1), '.', int(rand()*256), '.', int(rand()*256), '.', int(rand()*256))")
        .withColumn("country", "string",
                    values=["US", "UK", "DE", "FR", "CA", "AU", "JP", "BR", "IN", "MX"],
                    random=True, weights=[5, 2, 2, 2, 1, 1, 1, 1, 1, 1])
        .withColumn("device_type", "string",
                    values=["desktop", "mobile", "tablet"],
                    random=True, weights=[4, 5, 1])
        .withColumn("action", "string",
                    values=["page_view", "click", "scroll", "form_submit",
                            "add_to_cart", "purchase", "search", "logout"],
                    random=True, weights=[5, 3, 2, 1, 1, 1, 2, 1])
        .withColumn("duration_ms", "integer", minValue=100, maxValue=30000, random=True)
        .withColumn("http_status", "integer", values=[200, 301, 304, 400, 403, 404, 500], random=True, weights=[20, 2, 3, 1, 1, 2, 1])
    )


def _build_student_enrollment_spec(spark: SparkSession, rows: int, num_students: int = 15000, num_courses: int = 2000) -> dg.DataGenerator:
    return (
        dg.DataGenerator(spark, name="student_enrollment", rows=rows, partitions=2)
        .withColumn("event_id", "string", expr="uuid()")
        .withColumn("student_id", "string",
                    expr="concat('STU-', lpad(cast(int(rand()*15000+1) as string), 5, '0'))")
        .withColumn("course_id", "string",
                    expr="concat('CRS-', lpad(cast(int(rand()*2000+1) as string), 4, '0'))")
        .withColumn("action", "string",
                    values=["enroll", "drop", "transfer", "grade_posted", "waitlist"],
                    random=True, weights=[5, 2, 1, 3, 1])
        .withColumn("semester", "string",
                    values=["Fall 2024", "Spring 2025", "Summer 2025", "Fall 2025"],
                    random=True)
        .withColumn("department", "string",
                    values=["Computer Science", "Mathematics", "English", "Biology",
                            "Chemistry", "Physics", "History", "Psychology",
                            "Business", "Engineering", "Nursing", "Education",
                            "Art", "Music", "Philosophy", "Political Science",
                            "Sociology", "Economics"],
                    random=True)
        .withColumn("grade", "string",
                    values=["A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "F", "W", "IP"],
                    random=True, weights=[2, 2, 2, 3, 2, 2, 2, 1, 1, 1, 1, 5])
        .withColumn("credits", "integer", minValue=1, maxValue=4, random=True)
        .withColumn("campus", "string",
                    values=["Main", "North", "Online", "Downtown", "West"],
                    random=True, weights=[4, 2, 3, 2, 1])
        .withColumn("gpa_impact", "decimal(3,1)", minValue=-4.0, maxValue=4.0, random=True)
    )


def _build_grant_budget_spec(spark: SparkSession, rows: int, num_funds: int = 200, num_vendors: int = 2000) -> dg.DataGenerator:
    return (
        dg.DataGenerator(spark, name="grant_budget", rows=rows, partitions=2)
        .withColumn("transaction_id", "string", expr="uuid()")
        .withColumn("fund_source_id", "string",
                    expr="concat('FUND-', lpad(cast(int(rand()*200+1) as string), 3, '0'))")
        .withColumn("agency_id", "string",
                    expr="concat('AGY-', lpad(cast(int(rand()*50+1) as string), 3, '0'))")
        .withColumn("program_id", "string",
                    expr="concat('PGM-', lpad(cast(int(rand()*500+1) as string), 4, '0'))")
        .withColumn("vendor_id", "string",
                    expr="concat('VND-', lpad(cast(int(rand()*2000+1) as string), 4, '0'))")
        .withColumn("transaction_type", "string",
                    values=["allocation", "expenditure", "transfer", "encumbrance",
                            "reimbursement", "adjustment"],
                    random=True, weights=[2, 5, 2, 2, 1, 1])
        .withColumn("amount", "decimal(10,2)", minValue=100.0, maxValue=5000000.0, random=True)
        .withColumn("fund_category", "string",
                    values=["federal_grant", "state_appropriation", "local_revenue",
                            "bond_proceeds", "tuition_fees", "endowment", "auxiliary"],
                    random=True, weights=[4, 3, 2, 1, 3, 1, 1])
        .withColumn("fiscal_year", "string",
                    values=["2023", "2024", "2025", "2026"],
                    random=True, weights=[1, 3, 4, 2])
        .withColumn("quarter", "string",
                    values=["Q1", "Q2", "Q3", "Q4"],
                    random=True)
        .withColumn("cost_center", "string",
                    expr="concat('CC-', lpad(cast(int(rand()*300+1) as string), 4, '0'))")
        .withColumn("account_code", "string",
                    expr="lpad(cast(int(rand()*9000+1000) as string), 4, '0')")
        .withColumn("description", "string",
                    values=["Professional services for", "Equipment purchase -",
                            "Personnel costs -", "Travel and training -",
                            "Facilities maintenance -", "Software licensing -",
                            "Consulting fees for", "Capital improvement -"],
                    random=True)
    )


def _build_citizen_services_spec(spark: SparkSession, rows: int, num_citizens: int = 50000, num_assets: int = 10000) -> dg.DataGenerator:
    return (
        dg.DataGenerator(spark, name="citizen_services", rows=rows, partitions=2)
        .withColumn("request_id", "string", expr="uuid()")
        .withColumn("citizen_id", "string",
                    expr="concat('CIT-', lpad(cast(int(rand()*50000+1) as string), 5, '0'))")
        .withColumn("request_type", "string",
                    values=["pothole_repair", "streetlight_outage", "water_main_break",
                            "noise_complaint", "illegal_dumping", "graffiti_removal",
                            "tree_trimming", "sidewalk_repair", "traffic_signal",
                            "building_inspection", "permit_application", "animal_control",
                            "park_maintenance", "snow_removal"],
                    random=True, weights=[5, 3, 2, 3, 2, 2, 2, 3, 2, 2, 3, 1, 2, 1])
        .withColumn("department", "string",
                    values=["Public Works", "Transportation", "Water", "Code Enforcement",
                            "Parks", "Building", "Police", "Fire", "Health", "Environmental"],
                    random=True, weights=[4, 3, 2, 2, 2, 2, 1, 1, 1, 1])
        .withColumn("status", "string",
                    values=["opened", "assigned", "in_progress", "pending_review",
                            "resolved", "closed", "reopened"],
                    random=True, weights=[3, 3, 4, 2, 3, 4, 1])
        .withColumn("priority", "string",
                    values=["critical", "high", "medium", "low"],
                    random=True, weights=[1, 2, 4, 3])
        .withColumn("district", "integer", minValue=1, maxValue=15, random=True)
        .withColumn("asset_id", "string",
                    expr="concat('AST-', lpad(cast(int(rand()*10000+1) as string), 5, '0'))")
        .withColumn("latitude", "decimal(8,5)", minValue=38.0, maxValue=42.0, random=True)
        .withColumn("longitude", "decimal(9,5)", minValue=-78.0, maxValue=-73.0, random=True)
        .withColumn("response_time_hours", "integer", minValue=1, maxValue=720, random=True)
        .withColumn("satisfaction_rating", "integer",
                    values=[1, 2, 3, 4, 5], random=True, weights=[1, 1, 2, 3, 3])
    )


def _build_k12_early_warning_spec(spark: SparkSession, rows: int, num_students: int = 25000, num_schools: int = 100) -> dg.DataGenerator:
    return (
        dg.DataGenerator(spark, name="k12_early_warning", rows=rows, partitions=2)
        .withColumn("event_id", "string", expr="uuid()")
        .withColumn("student_id", "string",
                    expr="concat('K12-', lpad(cast(int(rand()*25000+1) as string), 5, '0'))")
        .withColumn("school_id", "string",
                    expr="concat('SCH-', lpad(cast(int(rand()*100+1) as string), 3, '0'))")
        .withColumn("event_type", "string",
                    values=["attendance", "discipline", "assessment", "intervention",
                            "counselor_note", "parent_contact", "iep_review", "health_screening"],
                    random=True, weights=[5, 3, 3, 2, 1, 2, 1, 1])
        .withColumn("grade_level", "integer", minValue=1, maxValue=12, random=True)
        .withColumn("teacher_id", "string",
                    expr="concat('TCH-', lpad(cast(int(rand()*3000+1) as string), 4, '0'))")
        .withColumn("risk_score", "decimal(5,2)", minValue=0.0, maxValue=100.0, random=True)
        .withColumn("attendance_rate", "decimal(5,2)", minValue=50.0, maxValue=100.0, random=True)
        .withColumn("gpa", "decimal(3,2)", minValue=0.0, maxValue=4.0, random=True)
        .withColumn("behavior_incidents_ytd", "integer", minValue=0, maxValue=25, random=True)
        .withColumn("intervention_type", "string",
                    values=["tutoring", "mentoring", "counseling", "parent_conference",
                            "schedule_change", "behavioral_plan", "none"],
                    random=True, weights=[2, 2, 2, 1, 1, 1, 5])
        .withColumn("school_type", "string",
                    values=["elementary", "middle", "high"],
                    random=True, weights=[5, 3, 4])
        .withColumn("free_reduced_lunch", "boolean", expr="rand() < 0.45")
        .withColumn("english_learner", "boolean", expr="rand() < 0.15")
        .withColumn("special_education", "boolean", expr="rand() < 0.13")
    )


def _build_procurement_spec(spark: SparkSession, rows: int, num_vendors: int = 3000, num_contracts: int = 5000) -> dg.DataGenerator:
    return (
        dg.DataGenerator(spark, name="procurement", rows=rows, partitions=2)
        .withColumn("event_id", "string", expr="uuid()")
        .withColumn("agency_id", "string",
                    expr="concat('AGY-', lpad(cast(int(rand()*50+1) as string), 3, '0'))")
        .withColumn("vendor_id", "string",
                    expr="concat('VND-', lpad(cast(int(rand()*3000+1) as string), 4, '0'))")
        .withColumn("event_type", "string",
                    values=["rfp_posted", "bid_submitted", "bid_withdrawn", "contract_awarded",
                            "purchase_order", "invoice_submitted", "invoice_paid",
                            "contract_amended", "contract_terminated"],
                    random=True, weights=[2, 4, 1, 2, 3, 3, 3, 1, 1])
        .withColumn("contract_id", "string",
                    expr="concat('CTR-', lpad(cast(int(rand()*5000+1) as string), 5, '0'))")
        .withColumn("amount", "decimal(12,2)", minValue=500.0, maxValue=25000000.0, random=True)
        .withColumn("procurement_method", "string",
                    values=["competitive_bid", "sole_source", "emergency",
                            "cooperative", "micro_purchase", "rfq"],
                    random=True, weights=[5, 2, 1, 2, 2, 3])
        .withColumn("commodity_code", "string",
                    expr="lpad(cast(int(rand()*900+100) as string), 3, '0')")
        .withColumn("category", "string",
                    values=["construction", "professional_services", "it_services",
                            "equipment", "supplies", "facilities", "consulting",
                            "staffing", "transportation", "utilities"],
                    random=True, weights=[3, 4, 4, 2, 2, 2, 3, 2, 1, 1])
        .withColumn("minority_owned", "boolean", expr="rand() < 0.18")
        .withColumn("small_business", "boolean", expr="rand() < 0.35")
        .withColumn("local_vendor", "boolean", expr="rand() < 0.40")
        .withColumn("contract_duration_months", "integer", minValue=1, maxValue=60, random=True)
        .withColumn("payment_terms", "string",
                    values=["net_30", "net_45", "net_60", "upon_delivery"],
                    random=True, weights=[5, 3, 2, 1])
    )


def _build_case_management_spec(spark: SparkSession, rows: int, num_clients: int = 40000, num_cases: int = 60000) -> dg.DataGenerator:
    return (
        dg.DataGenerator(spark, name="case_management", rows=rows, partitions=2)
        .withColumn("event_id", "string", expr="uuid()")
        .withColumn("client_id", "string",
                    expr="concat('CLT-', lpad(cast(int(rand()*40000+1) as string), 5, '0'))")
        .withColumn("case_id", "string",
                    expr="concat('CASE-', lpad(cast(int(rand()*60000+1) as string), 5, '0'))")
        .withColumn("caseworker_id", "string",
                    expr="concat('CW-', lpad(cast(int(rand()*1500+1) as string), 4, '0'))")
        .withColumn("event_type", "string",
                    values=["intake", "referral", "eligibility_determination",
                            "benefit_disbursement", "review", "closure", "appeal", "transfer"],
                    random=True, weights=[3, 3, 3, 4, 3, 2, 1, 1])
        .withColumn("program", "string",
                    values=["SNAP", "Medicaid", "TANF", "WIC", "CHIP",
                            "housing_assistance", "energy_assistance", "childcare_subsidy",
                            "unemployment", "disability"],
                    random=True, weights=[4, 5, 2, 2, 2, 3, 1, 2, 3, 1])
        .withColumn("agency_id", "string",
                    expr="concat('HHS-', lpad(cast(int(rand()*30+1) as string), 3, '0'))")
        .withColumn("benefit_amount", "decimal(10,2)", minValue=0.0, maxValue=15000.0, random=True)
        .withColumn("household_size", "integer",
                    values=[1, 2, 3, 4, 5, 6, 7, 8],
                    random=True, weights=[2, 4, 4, 3, 2, 1, 1, 1])
        .withColumn("income_bracket", "string",
                    values=["below_poverty", "low_income", "moderate_income"],
                    random=True, weights=[4, 4, 2])
        .withColumn("county", "string",
                    expr="concat('County-', cast(int(rand()*80+1) as string))")
        .withColumn("determination", "string",
                    values=["approved", "denied", "pending", "deferred", "conditional"],
                    random=True, weights=[5, 2, 3, 1, 2])
        .withColumn("referral_source", "string",
                    values=["self", "agency", "community_org", "healthcare", "school", "court"],
                    random=True, weights=[4, 3, 2, 2, 1, 1])
        .withColumn("priority", "string",
                    values=["emergency", "urgent", "standard", "low"],
                    random=True, weights=[1, 2, 5, 2])
    )


_USE_CASE_BUILDERS = {
    UseCase.fraud_detection: _build_fraud_spec,
    UseCase.telemetry: _build_telemetry_spec,
    UseCase.web_traffic: _build_web_traffic_spec,
    UseCase.student_enrollment: _build_student_enrollment_spec,
    UseCase.grant_budget: _build_grant_budget_spec,
    UseCase.citizen_services: _build_citizen_services_spec,
    UseCase.k12_early_warning: _build_k12_early_warning_spec,
    UseCase.procurement: _build_procurement_spec,
    UseCase.case_management: _build_case_management_spec,
}

_DEFAULT_TOPICS = {
    UseCase.fraud_detection: "streaming-fraud-transactions",
    UseCase.telemetry: "streaming-device-telemetry",
    UseCase.web_traffic: "streaming-web-traffic",
    UseCase.student_enrollment: "streaming-student-enrollment",
    UseCase.grant_budget: "streaming-grant-budget",
    UseCase.citizen_services: "streaming-citizen-services",
    UseCase.k12_early_warning: "streaming-k12-early-warning",
    UseCase.procurement: "streaming-procurement",
    UseCase.case_management: "streaming-case-management",
}

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------
class GeneratorStartRequest(BaseModel):
    use_case: UseCase
    topic_name: Optional[str] = Field(None, description="Kafka topic name. Defaults to a use-case-specific topic.")
    rows_per_batch: int = Field(default=100, ge=1, le=10000, description="Rows generated per batch cycle.")
    batch_interval_seconds: float = Field(default=1.0, ge=0.1, le=60.0, description="Seconds between batch cycles.")
    timeout_minutes: float = Field(default=10.0, ge=0.1, le=1440.0, description="Auto-stop after this many minutes.")


class GeneratorStatus(BaseModel):
    generator_id: str
    use_case: str
    topic_name: str
    status: str
    rows_produced: int
    started_at: str
    elapsed_seconds: float
    timeout_minutes: float
    rows_per_batch: int
    batch_interval_seconds: float
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Background producer loop
# ---------------------------------------------------------------------------
def _generate_batch(spark: SparkSession, builder, rows_per_batch: int) -> list[str]:
    """Run dbldatagen + Spark in a synchronous context (thread pool)."""
    spec = builder(spark, rows=rows_per_batch)
    df = spec.build()
    return df.toJSON().collect()


async def _generator_loop(generator_id: str, state: dict):
    loop = asyncio.get_running_loop()

    # Initialise Spark in thread pool (heavy JVM startup)
    spark = await loop.run_in_executor(None, _get_spark)
    producer = _get_producer()
    use_case: UseCase = state["use_case"]
    topic: str = state["topic_name"]
    rows_per_batch: int = state["rows_per_batch"]
    interval: float = state["batch_interval_seconds"]
    timeout_sec: float = state["timeout_minutes"] * 60

    builder = _USE_CASE_BUILDERS[use_case]
    start = time.monotonic()

    try:
        while state["status"] == "running":
            elapsed = time.monotonic() - start
            if elapsed >= timeout_sec:
                state["status"] = "completed"
                break

            # Generate a batch via dbldatagen (offload to thread pool)
            rows = await loop.run_in_executor(
                None, _generate_batch, spark, builder, rows_per_batch
            )

            # Inject timestamp and produce to Kafka
            for row_json in rows:
                record = json.loads(row_json)
                record["event_timestamp"] = datetime.now(timezone.utc).isoformat()
                producer.produce(topic, json.dumps(record).encode("utf-8"))
                state["rows_produced"] += 1

            producer.flush()
            state["elapsed_seconds"] = time.monotonic() - start

            await asyncio.sleep(interval)

    except asyncio.CancelledError:
        state["status"] = "stopped"
    except Exception as e:
        state["status"] = "error"
        state["error"] = str(e)
    finally:
        producer.flush()
        state["elapsed_seconds"] = time.monotonic() - start
        if state["status"] == "running":
            state["status"] = "completed"


def _build_status(state: dict) -> GeneratorStatus:
    return GeneratorStatus(
        generator_id=state["generator_id"],
        use_case=state["use_case"].value if isinstance(state["use_case"], UseCase) else state["use_case"],
        topic_name=state["topic_name"],
        status=state["status"],
        rows_produced=state["rows_produced"],
        started_at=state["started_at"],
        elapsed_seconds=state["elapsed_seconds"],
        timeout_minutes=state["timeout_minutes"],
        rows_per_batch=state["rows_per_batch"],
        batch_interval_seconds=state["batch_interval_seconds"],
        error=state.get("error"),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "service": "spark-generator"}


@app.post("/generators/start", response_model=GeneratorStatus)
async def start_generator(request: GeneratorStartRequest):
    """Start a streaming data generator that produces synthetic data to Kafka."""
    generator_id = str(uuid.uuid4())[:8]
    topic = request.topic_name or _DEFAULT_TOPICS[request.use_case]

    state = {
        "generator_id": generator_id,
        "use_case": request.use_case,
        "topic_name": topic,
        "status": "running",
        "rows_produced": 0,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": 0.0,
        "timeout_minutes": request.timeout_minutes,
        "rows_per_batch": request.rows_per_batch,
        "batch_interval_seconds": request.batch_interval_seconds,
    }

    task = asyncio.create_task(_generator_loop(generator_id, state))
    state["_task"] = task
    _active_generators[generator_id] = state

    return _build_status(state)


@app.post("/generators/{generator_id}/stop", response_model=GeneratorStatus)
async def stop_generator(generator_id: str):
    """Stop a running generator."""
    state = _active_generators.get(generator_id)
    if not state:
        return {"error": f"Generator {generator_id} not found"}

    if state["status"] == "running":
        state["status"] = "stopped"
        task: asyncio.Task = state.get("_task")
        if task and not task.done():
            task.cancel()

    return _build_status(state)


@app.get("/generators", response_model=list[GeneratorStatus])
async def list_generators():
    """List all generators and their status."""
    return [_build_status(s) for s in _active_generators.values()]


@app.get("/generators/{generator_id}", response_model=GeneratorStatus)
async def get_generator(generator_id: str):
    """Get status of a specific generator."""
    state = _active_generators.get(generator_id)
    if not state:
        return {"error": f"Generator {generator_id} not found"}
    return _build_status(state)


@app.delete("/generators/cleanup")
async def cleanup_generators():
    """Remove all completed/stopped/errored generators from the list."""
    to_remove = [gid for gid, s in _active_generators.items() if s["status"] != "running"]
    for gid in to_remove:
        del _active_generators[gid]
    return {"removed": len(to_remove), "active": len(_active_generators)}
