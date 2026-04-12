"""Generate deterministic large-scale fixtures for pagination soak testing.

Uses a fixed seed for reproducibility — running this script multiple times
produces byte-identical output.  Generated fixtures mirror the structure
of existing examples exactly.

Usage:
    python benchmarks/gen_large_fixtures.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path

SEED = 42
EXAMPLES = Path(__file__).parent.parent / "examples"

# --- Invoice descriptions (same 20 used in invoice_long_data.json) ----------

INVOICE_DESCRIPTIONS = [
    "Website redesign \u2014 full responsive layout",
    "API integration with payment gateway",
    "Cloud infrastructure setup (AWS)",
    "Database migration and optimization",
    "Custom reporting dashboard",
    "Mobile app UI/UX design",
    "Security audit and penetration testing",
    "CI/CD pipeline configuration",
    "Load testing and performance tuning",
    "Technical documentation package",
    "Email notification system",
    "User authentication module",
    "Data export and reporting tools",
    "Third-party SSO integration",
    "Automated backup system",
    "Monitoring and alerting setup",
    "Frontend component library",
    "Search and filtering engine",
    "Webhook integration layer",
    "Admin dashboard development",
]

INVOICE_UNIT_PRICES = [250, 500, 750, 1200, 1500, 2000, 3500]


def generate_invoice_1000() -> dict:
    """Generate a 1000-item invoice mirroring invoice_long_data.json structure."""
    rng = random.Random(SEED)
    items = []
    subtotal = 0

    for i in range(1, 1001):
        desc = INVOICE_DESCRIPTIONS[(i - 1) % len(INVOICE_DESCRIPTIONS)]
        qty = rng.randint(1, 10)
        unit_price = rng.choice(INVOICE_UNIT_PRICES)
        amount = qty * unit_price
        subtotal += amount
        items.append({
            "num": i,
            "description": desc,
            "qty": qty,
            "unit_price": f"${unit_price:,.2f}",
            "amount": f"${amount:,.2f}",
        })

    tax_amount = round(subtotal * 0.085)
    total = subtotal + tax_amount

    return {
        "invoice_number": "INV-2026-1000",
        "invoice_date": "April 11, 2026",
        "due_date": "May 11, 2026",
        "payment_terms": "Net 30",
        "sender": {
            "name": "Acme Corporation",
            "address": "123 Business Ave, Suite 400, San Francisco, CA 94105",
            "email": "billing@acme.com",
        },
        "recipient": {
            "name": "Contoso Ltd.",
            "address": "456 Enterprise Blvd, New York, NY 10001",
            "email": "accounts@contoso.com",
        },
        "items": items,
        "subtotal": f"${subtotal:,.2f}",
        "tax_rate": "8.5%",
        "tax_amount": f"${tax_amount:,.2f}",
        "total": f"${total:,.2f}",
        "notes": "Payment is due within 30 days of invoice date. "
                 "Please include the invoice number with your payment.",
    }


# --- Statement descriptions (same patterns as statement_long_data.json) -----

STATEMENT_DESCRIPTIONS = [
    "Monthly hosting fee",
    "Payment received \u2014 thank you",
    "Professional services \u2014 consulting",
    "Software license renewal",
    "Data storage overage charge",
    "Support ticket resolution \u2014 Priority 1",
    "API usage \u2014 metered billing",
    "Infrastructure maintenance",
    "SSL certificate renewal",
    "Domain registration fee",
    "Bandwidth overage charge",
    "Cloud compute \u2014 on-demand",
    "Database backup service",
    "CDN usage fee",
    "Security scanning service",
    "Email delivery service",
    "Load balancer fee",
    "Container orchestration",
    "Log management service",
    "Compliance audit fee",
]

STATEMENT_REF_PREFIXES = ["ADJ", "FEE", "PMT", "CR", "INV", "REF"]
STATEMENT_AMOUNTS = [150, 250, 500, 750, 1200, 1500, 2000, 3500]
MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def generate_statement_1000() -> dict:
    """Generate a 1000-row statement mirroring statement_long_data.json."""
    rng = random.Random(SEED)
    transactions = []
    balance = 12450  # opening balance in cents-like units

    # Opening row
    transactions.append({
        "date": "Jan 01",
        "reference": "",
        "description": "Opening Balance",
        "amount": "",
        "balance": f"${balance:,.2f}",
    })

    charges = 0
    payments = 0

    for i in range(1, 1000):
        month_idx = (i - 1) % 12
        day = ((i - 1) % 28) + 1
        date = f"{MONTHS[month_idx]} {day:02d}"
        prefix = rng.choice(STATEMENT_REF_PREFIXES)
        ref = f"{prefix}-{rng.randint(1000, 9999)}"
        desc = STATEMENT_DESCRIPTIONS[i % len(STATEMENT_DESCRIPTIONS)]
        raw_amount = rng.choice(STATEMENT_AMOUNTS)

        # ~30% are payments (negative), rest are charges
        if rng.random() < 0.3:
            amount = -raw_amount
            payments += 1
        else:
            amount = raw_amount
            charges += 1

        balance += amount
        amount_str = f"${amount:,.2f}" if amount >= 0 else f"-${abs(amount):,.2f}"
        transactions.append({
            "date": date,
            "reference": ref,
            "description": desc,
            "amount": amount_str,
            "balance": f"${balance:,.2f}",
        })

    return {
        "company": {
            "name": "Acme Corporation",
            "address": "123 Business Ave, Suite 400, San Francisco, CA 94105",
            "email": "billing@acme.com",
            "phone": "(415) 555-0142",
        },
        "customer": {
            "name": "Contoso Ltd.",
            "account_number": "ACCT-78291",
            "address": "456 Enterprise Blvd, New York, NY 10001",
        },
        "statement_date": "December 31, 2026",
        "period": "January 1 - December 31, 2026",
        "opening_balance": "$12,450.00",
        "closing_balance": f"${balance:,.2f}",
        "total_charges": f"{charges} charges",
        "total_payments": f"{payments} payments",
        "transactions": transactions,
        "aging": {
            "current": "$18,500.00",
            "days_30": "$8,200.00",
            "days_60": "$3,800.00",
            "days_90": "$1,950.00",
            "total": "$32,450.00",
        },
        "notes": "This statement covers a 12-month period. "
                 "Please review all transactions and contact us "
                 "within 30 days if you have questions.",
    }


# --- Report data (dense version) -------------------------------------------

METRIC_LABELS = [
    "Uptime", "P1 Incidents", "Mean Time to Resolve", "Cloud Spend",
    "Deployments", "Change Failure Rate", "Error Rate", "Latency P99",
    "Throughput", "Cache Hit Rate", "CPU Utilization", "Memory Utilization",
    "Disk I/O", "Network Throughput", "Container Restarts", "Pod Count",
    "Node Count", "Failed Deployments", "Rollback Rate", "Test Coverage",
    "Build Time", "Deploy Frequency", "Lead Time", "MTTR",
    "Availability SLA", "Customer Tickets", "Alert Noise Ratio",
    "On-Call Pages", "Postmortem Count", "Runbook Coverage",
    "DNS Resolution Time", "TLS Handshake Time", "CDN Hit Rate",
    "Origin Latency", "Database Connections", "Query P95",
    "Replication Lag", "Backup Success Rate", "Recovery Point",
    "Recovery Time", "Security Patches", "Vulnerability Count",
    "Compliance Score", "Audit Findings", "Cost Per Transaction",
    "Revenue Impact", "User Sessions", "API Calls", "Webhook Deliveries",
    "Queue Depth",
]

SERVICE_NAMES = [
    "Compute (EC2/ECS)", "Database (RDS/DynamoDB)", "Storage (S3/EBS)",
    "Networking (CloudFront/ALB)", "Lambda Functions", "SQS/SNS",
    "ElastiCache", "Elasticsearch", "CloudWatch", "Secrets Manager",
    "KMS", "IAM", "Route 53", "WAF/Shield", "API Gateway",
    "Step Functions", "EventBridge", "Kinesis", "Glue",
    "Athena", "Redshift", "SageMaker", "CodePipeline",
    "CodeBuild", "ECR", "EKS", "App Mesh", "X-Ray",
    "CloudFormation", "Systems Manager",
]


def generate_report_long() -> dict:
    """Generate a dense report with 50 metrics, 20 incidents, 30 services."""
    rng = random.Random(SEED)

    metrics = []
    for label in METRIC_LABELS[:50]:
        value = f"{rng.uniform(0.5, 99.9):.1f}%" if "Rate" in label or "Utilization" in label or "Coverage" in label else f"{rng.randint(1, 9999)}"
        target = f"{rng.uniform(0.5, 99.9):.1f}%" if "%" in value else f"<{rng.randint(1, 100)}"
        status = rng.choice(["above", "met", "below"])
        metrics.append({"label": label, "value": value, "target": target, "status": status})

    incidents = []
    for j in range(20):
        severity = rng.choice(["P1", "P2", "P3"])
        duration = f"{rng.randint(5, 120)} min"
        incidents.append({
            "id": f"INC-2026-{j + 1:04d}",
            "date": f"{MONTHS[j % 12]} {rng.randint(1, 28)}",
            "severity": severity,
            "duration": duration,
            "description": f"Service degradation in {rng.choice(SERVICE_NAMES[:15])} caused elevated error rates for approximately {rng.randint(100, 5000)} users.",
            "root_cause": f"Resource contention triggered by {rng.choice(['traffic spike', 'deployment', 'dependency failure', 'configuration drift', 'capacity limit'])}.",
            "resolution": f"Mitigated via {rng.choice(['hotfix', 'rollback', 'scaling', 'failover', 'configuration update'])}. Postmortem completed.",
        })

    spend = []
    for svc in SERVICE_NAMES[:30]:
        q1 = rng.randint(5000, 60000)
        q4 = rng.randint(5000, 60000)
        change = ((q1 - q4) / q4) * 100
        spend.append({
            "service": svc,
            "q1_spend": f"${q1:,}",
            "q4_spend": f"${q4:,}",
            "change": f"{change:+.1f}%",
        })

    recommendations = [
        f"Recommendation {i + 1}: {rng.choice(['Optimize', 'Migrate', 'Consolidate', 'Automate', 'Review', 'Upgrade', 'Replace', 'Monitor', 'Scale', 'Deprecate', 'Implement', 'Evaluate', 'Standardize', 'Document', 'Audit'])} {rng.choice(SERVICE_NAMES[:15])} to reduce cost and improve reliability."
        for i in range(15)
    ]

    return {
        "company": {
            "name": "Acme Corporation",
            "department": "Engineering Operations",
        },
        "title": "FY2026 Comprehensive Infrastructure Review",
        "subtitle": "Annual Performance, Incident, and Spend Analysis",
        "date": "April 11, 2026",
        "prepared_by": "Sarah Kim, VP of Engineering",
        "period": "January 1 - December 31, 2026",
        "executive_summary": "This annual review covers 50 operational metrics across all production services. Infrastructure availability remained above target at 99.94%. Twenty incidents were logged, with root causes spanning traffic spikes, deployment issues, and dependency failures. Cloud spend totaled $1.2M across 30 service categories. Fifteen recommendations are provided for the next fiscal year.",
        "metrics": metrics,
        "incidents": incidents,
        "spend_by_service": spend,
        "recommendations": recommendations,
    }


def main():
    # Invoice 1000
    invoice = generate_invoice_1000()
    path = EXAMPLES / "invoice_1000_data.json"
    path.write_text(json.dumps(invoice, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  {path.name}: {len(invoice['items'])} items")

    # Statement 1000
    statement = generate_statement_1000()
    path = EXAMPLES / "statement_1000_data.json"
    path.write_text(json.dumps(statement, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  {path.name}: {len(statement['transactions'])} transactions")

    # Report long
    report = generate_report_long()
    path = EXAMPLES / "report_long_data.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  {path.name}: {len(report['metrics'])} metrics, {len(report['incidents'])} incidents, {len(report['spend_by_service'])} services")


if __name__ == "__main__":
    print("Generating large fixtures...")
    main()
    print("Done.")
