import pytest
import pandas as pd
import numpy as np
import json
import os
from audit_engine import (
    load_data, 
    validate_purchase_orders, 
    calculate_vendor_spend_and_risk, 
    generate_audit_report,
    run_procurement_audit
)

@pytest.fixture
def sample_vendors():
    return pd.DataFrame([
        {"vendor_id": "V001", "vendor_name": "Vendor_1", "category": "OFFICE", "status": "ACTIVE"},
        {"vendor_id": "V002", "vendor_name": "Vendor_2", "category": "IT", "status": "ACTIVE"},
        {"vendor_id": "V003", "vendor_name": "Vendor_3", "category": "FACILITY", "status": "BLACKLISTED"},
    ])

def test_invalid_vendor_rejected(sample_vendors):
    # PO has vendor_id V999 which does not exist in sample_vendors
    pos = pd.DataFrame([
        {"po_id": "PO0001", "vendor_id": "V999", "order_amount": 5000, "order_date": "2025-10-01", "order_status": "APPROVED"}
    ])
    
    validated_pos = validate_purchase_orders(sample_vendors, pos)
    
    assert len(validated_pos) == 1
    assert validated_pos.loc[0, 'is_valid'] == False
    assert "Vendor ID does not exist in master data" in validated_pos.loc[0, 'rejection_reason']
    assert validated_pos.loc[0, 'risk_level'] == "HIGH"

def test_blacklisted_vendor_rejected(sample_vendors):
    # PO has vendor_id V003 which is blacklisted in sample_vendors
    pos = pd.DataFrame([
        {"po_id": "PO0001", "vendor_id": "V003", "order_amount": 5000, "order_date": "2025-10-01", "order_status": "APPROVED"}
    ])
    
    validated_pos = validate_purchase_orders(sample_vendors, pos)
    
    assert len(validated_pos) == 1
    assert validated_pos.loc[0, 'is_valid'] == False
    assert "Vendor is blacklisted" in validated_pos.loc[0, 'rejection_reason']
    assert validated_pos.loc[0, 'risk_level'] == "CRITICAL"

def test_invalid_date_rejected(sample_vendors):
    # PO has invalid date format
    pos = pd.DataFrame([
        {"po_id": "PO0001", "vendor_id": "V001", "order_amount": 5000, "order_date": "invalid_date", "order_status": "APPROVED"},
        {"po_id": "PO0002", "vendor_id": "V001", "order_amount": 5000, "order_date": "", "order_status": "APPROVED"}
    ])
    
    validated_pos = validate_purchase_orders(sample_vendors, pos)
    
    assert validated_pos.loc[0, 'is_valid'] == False
    assert "Invalid order date format" in validated_pos.loc[0, 'rejection_reason']
    
    assert validated_pos.loc[1, 'is_valid'] == False
    assert "Missing order date" in validated_pos.loc[1, 'rejection_reason']

def test_negative_order_amount_rejected(sample_vendors):
    # POs have negative, zero, or non-numeric order amounts
    pos = pd.DataFrame([
        {"po_id": "PO0001", "vendor_id": "V001", "order_amount": -500, "order_date": "2025-10-01", "order_status": "APPROVED"},
        {"po_id": "PO0002", "vendor_id": "V001", "order_amount": 0, "order_date": "2025-10-01", "order_status": "APPROVED"},
        {"po_id": "PO0003", "vendor_id": "V001", "order_amount": "not_a_number", "order_date": "2025-10-01", "order_status": "APPROVED"}
    ])
    
    validated_pos = validate_purchase_orders(sample_vendors, pos)
    
    assert validated_pos.loc[0, 'is_valid'] == False
    assert "Order amount must be positive" in validated_pos.loc[0, 'rejection_reason']
    
    assert validated_pos.loc[1, 'is_valid'] == False
    assert "Order amount must be positive" in validated_pos.loc[1, 'rejection_reason']
    
    assert validated_pos.loc[2, 'is_valid'] == False
    assert "Order amount must be positive" in validated_pos.loc[2, 'rejection_reason']

def test_high_value_order_flagged(sample_vendors):
    # PO amounts: one below threshold, one above 100,000 threshold
    pos = pd.DataFrame([
        {"po_id": "PO0001", "vendor_id": "V001", "order_amount": 90000, "order_date": "2025-10-01", "order_status": "APPROVED"},
        {"po_id": "PO0002", "vendor_id": "V002", "order_amount": 150000, "order_date": "2025-10-02", "order_status": "APPROVED"}
    ])
    
    validated_pos = validate_purchase_orders(sample_vendors, pos)
    
    assert validated_pos.loc[0, 'is_valid'] == True
    assert validated_pos.loc[0, 'is_high_value'] == False
    assert validated_pos.loc[0, 'risk_level'] == "MEDIUM"  # Over 50,000
    
    assert validated_pos.loc[1, 'is_valid'] == True
    assert validated_pos.loc[1, 'is_high_value'] == True
    assert validated_pos.loc[1, 'risk_level'] == "HIGH"  # Over 100,000

def test_vendor_spend_calculation(sample_vendors):
    pos = pd.DataFrame([
        {"po_id": "PO0001", "vendor_id": "V001", "order_amount": 5000, "order_date": "2025-10-01", "order_status": "APPROVED"},
        {"po_id": "PO0002", "vendor_id": "V001", "order_amount": 15000, "order_date": "2025-10-02", "order_status": "APPROVED"},
        {"po_id": "PO0003", "vendor_id": "V001", "order_amount": -100, "order_date": "2025-10-03", "order_status": "APPROVED"}, # Invalid order
        {"po_id": "PO0004", "vendor_id": "V002", "order_amount": 120000, "order_date": "2025-10-04", "order_status": "APPROVED"} # High value
    ])
    
    validated_pos = validate_purchase_orders(sample_vendors, pos)
    vendor_summary = calculate_vendor_spend_and_risk(sample_vendors, validated_pos)
    
    v001_row = vendor_summary[vendor_summary['vendor_id'] == 'V001'].iloc[0]
    assert v001_row['total_orders'] == 2  # Only count valid POs
    assert v001_row['total_spend'] == 20000.0
    assert v001_row['average_order_value'] == 10000.0
    assert v001_row['high_value_orders_count'] == 0
    assert v001_row['risk_score'] == 20
    assert v001_row['risk_level'] == "LOW"
    
    v002_row = vendor_summary[vendor_summary['vendor_id'] == 'V002'].iloc[0]
    assert v002_row['total_orders'] == 1
    assert v002_row['total_spend'] == 120000.0
    assert v002_row['average_order_value'] == 120000.0
    assert v002_row['high_value_orders_count'] == 1
    # Risk score: Base 10 + 1 high_value * 15 = 25 -> Risk Level LOW (< 35)
    assert v002_row['risk_score'] == 25
    assert v002_row['risk_level'] == "LOW"

def test_duplicate_purchase_order_detection(sample_vendors):
    # POs share same po_id
    pos = pd.DataFrame([
        {"po_id": "PO0001", "vendor_id": "V001", "order_amount": 5000, "order_date": "2025-10-01", "order_status": "APPROVED"},
        {"po_id": "PO0001", "vendor_id": "V002", "order_amount": 6000, "order_date": "2025-10-02", "order_status": "APPROVED"}
    ])
    
    validated_pos = validate_purchase_orders(sample_vendors, pos)
    
    assert len(validated_pos) == 2
    assert validated_pos.loc[0, 'is_valid'] == True
    assert validated_pos.loc[1, 'is_valid'] == False
    assert "Duplicate purchase order ID" in validated_pos.loc[1, 'rejection_reason']

def test_audit_report_generation(sample_vendors):
    pos = pd.DataFrame([
        {"po_id": "PO0001", "vendor_id": "V001", "order_amount": 5000, "order_date": "2025-10-01", "order_status": "APPROVED"},
        {"po_id": "PO0002", "vendor_id": "V003", "order_amount": 6000, "order_date": "2025-10-02", "order_status": "APPROVED"} # Blacklisted
    ])
    
    validated_pos = validate_purchase_orders(sample_vendors, pos)
    vendor_summary = calculate_vendor_spend_and_risk(sample_vendors, validated_pos)
    report = generate_audit_report(validated_pos, vendor_summary)
    
    assert report['audit_summary']['total_orders_processed'] == 2
    assert report['audit_summary']['valid_orders'] == 1
    assert report['audit_summary']['invalid_orders'] == 1
    assert report['audit_summary']['blacklisted_vendor_attempts'] == 1
    assert report['audit_summary']['total_procurement_spend'] == 5000.0
    assert report['vendor_risk_distribution']['CRITICAL'] == 1 # Vendor_3 is blacklisted, so risk level critical

def test_missing_and_malformed_columns(sample_vendors):
    pos_missing = pd.DataFrame([
        {"po_id": "PO0001", "order_amount": 5000} # missing columns
    ])
    with pytest.raises(ValueError):
        validate_purchase_orders(sample_vendors, pos_missing)
        
    vendors_missing = pd.DataFrame([
        {"vendor_id": "V001", "vendor_name": "Vendor_1"}
    ])
    with pytest.raises(ValueError):
        validate_purchase_orders(vendors_missing, pd.DataFrame([
            {"po_id": "PO0001", "vendor_id": "V001", "order_amount": 5000, "order_date": "2025-10-01"}
        ]))

def test_run_procurement_audit_execution(tmp_path):
    # Set up temp workspace files
    vendors = pd.DataFrame([
        {"vendor_id": "V001", "vendor_name": "Vendor_1", "category": "OFFICE", "status": "ACTIVE"}
    ])
    pos = pd.DataFrame([
        {"po_id": "PO0001", "vendor_id": "V001", "order_amount": 5000, "order_date": "2025-10-01", "order_status": "APPROVED"}
    ])
    
    vendors.to_csv(os.path.join(tmp_path, "vendor_master.csv"), index=False)
    pos.to_csv(os.path.join(tmp_path, "purchase_orders.csv"), index=False)
    
    val_pos, v_sum, rpt = run_procurement_audit(workspace_dir=str(tmp_path))
    
    assert os.path.exists(os.path.join(tmp_path, "validated_purchase_orders.csv"))
    assert os.path.exists(os.path.join(tmp_path, "vendor_spend_summary.csv"))
    assert os.path.exists(os.path.join(tmp_path, "procurement_audit_report.json"))
    
    # Missing files check
    with pytest.raises(FileNotFoundError):
        load_data("non_existent_vendors.csv", "non_existent_pos.csv")
