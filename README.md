# Procurement Audit & Vendor Risk Engine

A Python-based **Procurement Audit & Vendor Risk Engine** that validates purchase orders, detects procurement policy violations, calculates vendor risk scores, and generates comprehensive audit reports. The project also includes a **Streamlit dashboard** for interactive visualization and analysis of procurement data.

---

## Features

* Validate purchase orders against predefined business rules.
* Detect invalid, inactive, and blacklisted vendors.
* Validate order dates and order amounts.
* Detect duplicate purchase order IDs.
* Identify high-value purchase orders (amount > ₹100,000).
* Calculate vendor spend statistics.
* Generate vendor risk scores and risk levels.
* Produce audit reports in JSON format.
* Interactive Streamlit dashboard with analytics and chatbot support.
* Comprehensive unit testing using **pytest**.

---

## Project Structure

```
Procurement-Audit-Engine/
│
├── audit_engine.py                  # Main audit engine
├── dashboard.py                     # Streamlit dashboard
├── test_audit_engine.py             # Unit test cases
│
├── vendor_master.csv                # Vendor master data
├── purchase_orders.csv              # Purchase orders
│
├── validated_purchase_orders.csv    # Generated output
├── vendor_spend_summary.csv         # Generated output
├── procurement_audit_report.json    # Generated output
│
├── requirements.txt
└── README.md
```

---

## Business Rules

The engine validates purchase orders using the following rules:

### Vendor Validation

* Vendor ID must exist in the Vendor Master.
* Vendor status must be **ACTIVE**.
* Reject BLACKLISTED vendors.
* Reject inactive vendors.

### Purchase Order Validation

* Purchase Order ID must not be duplicated.
* Order date must be present and follow **YYYY-MM-DD** format.
* Order amount must be greater than zero.
* Orders above **₹100,000** are marked as **High Value**.

---

## Vendor Risk Scoring

Risk score is calculated as:

### Active Vendors

```
Risk Score =
10
+ (15 × High Value Orders)
+ (25 × Duplicate Orders)
+ (10 × Invalid Orders)
```

Maximum score = **100**

### Blacklisted Vendors

```
Risk Score = 100
```

### Inactive Vendors

```
Risk Score = 40
```

### Risk Levels

| Risk Score | Risk Level |
| ---------- | ---------- |
| < 35       | LOW        |
| 35 – 64    | MEDIUM     |
| 65 – 84    | HIGH       |
| ≥ 85       | CRITICAL   |

---

## Generated Outputs

### 1. validated_purchase_orders.csv

Contains:

* Validation status
* Rejection reason
* Vendor details
* High-value flag
* Purchase order risk level

---

### 2. vendor_spend_summary.csv

Contains:

* Total orders
* Total spend
* Average order value
* High-value order count
* Duplicate order count
* Vendor risk score
* Vendor risk level

---

### 3. procurement_audit_report.json

Contains:

* Audit summary
* Vendor risk distribution
* Rejection reason distribution
* Category-wise spend
* Monthly spend trend
* Timestamp

---

## Dashboard Features

The Streamlit dashboard includes:

* Executive Dashboard
* Purchase Order Search
* Vendor Search
* Spend Analytics
* Risk & Audit Center
* Vendor Performance Dashboard
* Procurement Trends
* Interactive Data Explorer
* AI Procurement Assistant (Ollama Llama 3 with fallback)
* Report Download Center

Run the dashboard using:

```bash
streamlit run dashboard.py
```

---

## Installation

Clone the repository

```bash
git clone <repository-url>
cd Procurement-Audit-Engine
```

Install dependencies

```bash
pip install -r requirements.txt
```

---

## Running the Audit Engine

Execute the audit engine:

```bash
python audit_engine.py
```

The following files will be generated automatically:

```
validated_purchase_orders.csv

vendor_spend_summary.csv

procurement_audit_report.json
```

---

## Running Unit Tests

Execute all test cases:

```bash
pytest test_audit_engine.py
```

or simply

```bash
pytest
```

---

## Test Coverage

The project includes unit tests for:

* Invalid vendor rejection
* Blacklisted vendor rejection
* Invalid order date detection
* Negative and invalid order amount validation
* High-value purchase order detection
* Vendor spend calculation
* Duplicate purchase order detection
* Audit report generation
* Missing required columns
* Complete pipeline execution
* Missing input file handling

---

## Technologies Used

* Python 3.x
* Pandas
* NumPy
* Streamlit
* Plotly
* Pytest
* JSON
* CSV

---

## Sample Workflow

```
Vendor Master CSV
          │
          ▼
Purchase Orders CSV
          │
          ▼
Validation Engine
          │
          ├── Vendor Validation
          ├── Date Validation
          ├── Amount Validation
          ├── Duplicate Detection
          └── High Value Detection
          │
          ▼
Vendor Spend Calculation
          │
          ▼
Risk Score Calculation
          │
          ▼
Audit Report Generation
          │
          ▼
CSV + JSON Outputs
          │
          ▼
Interactive Streamlit Dashboard
```

---

## Future Enhancements

* Database integration (MySQL/PostgreSQL)
* Role-based authentication
* Email alerts for high-risk vendors
* Machine learning-based fraud detection
* REST API integration
* Real-time procurement monitoring

---


