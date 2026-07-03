import os
import json
import pandas as pd
import numpy as np
from datetime import datetime

def load_data(vendor_path, po_path):
    """
    Loads vendor master and purchase orders from CSV files.
    """
    if not os.path.exists(vendor_path):
        raise FileNotFoundError(f"Vendor master file not found at: {vendor_path}")
    if not os.path.exists(po_path):
        raise FileNotFoundError(f"Purchase orders file not found at: {po_path}")
        
    vendors_df = pd.read_csv(vendor_path)
    pos_df = pd.read_csv(po_path)
    
    # Strip whitespace from string columns to avoid matching issues
    for col in vendors_df.select_dtypes(include=['object']).columns:
        vendors_df[col] = vendors_df[col].astype(str).str.strip()
    for col in pos_df.select_dtypes(include=['object']).columns:
        pos_df[col] = pos_df[col].astype(str).str.strip()
        
    return vendors_df, pos_df

def validate_purchase_orders(vendors_df, pos_df):
    """
    Validates each purchase order against business rules:
    - Vendor must exist and be ACTIVE (reject if BLACKLISTED)
    - Valid order date format (YYYY-MM-DD)
    - Positive order amount (> 0)
    - Reject duplicate PO IDs (subsequent occurrences are rejected)
    - Flags high-value orders (> 100,000)
    """
    # Create copies to avoid modifying original DataFrames
    pos = pos_df.copy()
    vendors = vendors_df.copy()
    
    # Ensure columns exist
    required_po_cols = ['po_id', 'vendor_id', 'order_amount', 'order_date']
    for col in required_po_cols:
        if col not in pos.columns:
            raise ValueError(f"Missing required column in purchase orders: {col}")
            
    required_vendor_cols = ['vendor_id', 'vendor_name', 'category', 'status']
    for col in required_vendor_cols:
        if col not in vendors.columns:
            raise ValueError(f"Missing required column in vendor master: {col}")

    # Build vendor dictionary for fast lookup
    vendor_dict = vendors.set_index('vendor_id').to_dict(orient='index')
    
    # Validation results lists
    is_valid_list = []
    rejection_reason_list = []
    is_high_value_list = []
    vendor_name_list = []
    category_list = []
    risk_level_list = []
    
    # Tracks seen PO IDs for duplicate detection
    seen_po_ids = set()
    
    # Vectorized duplicate flag check to know if the ID is duplicated in the dataset
    # We reject subsequent occurrences of a duplicate
    for idx, row in pos.iterrows():
        po_id = str(row['po_id']).strip() if not pd.isna(row['po_id']) else ""
        vendor_id = str(row['vendor_id']).strip() if not pd.isna(row['vendor_id']) else ""
        amount_val = row['order_amount']
        date_val = str(row['order_date']).strip() if not pd.isna(row['order_date']) else ""
        
        reasons = []
        vendor_info = vendor_dict.get(vendor_id)
        
        # 1. Duplicate check
        if po_id == "":
            reasons.append("Missing Purchase Order ID")
        elif po_id in seen_po_ids:
            reasons.append("Duplicate purchase order ID")
        else:
            seen_po_ids.add(po_id)
            
        # 2. Vendor existence check
        if vendor_id == "":
            reasons.append("Missing Vendor ID")
            vendor_name = "Unknown Vendor"
            vendor_category = "Unknown"
            vendor_status = "UNKNOWN"
        elif not vendor_info:
            reasons.append("Vendor ID does not exist in master data")
            vendor_name = "Unknown Vendor"
            vendor_category = "Unknown"
            vendor_status = "UNKNOWN"
        else:
            vendor_name = vendor_info['vendor_name']
            vendor_category = vendor_info['category']
            vendor_status = vendor_info['status']
            
            # 3. Vendor active check
            if vendor_status == "BLACKLISTED":
                reasons.append("Vendor is blacklisted")
            elif vendor_status != "ACTIVE":
                reasons.append("Vendor is inactive")
                
        # 4. Date validation check
        if date_val == "":
            reasons.append("Missing order date")
        else:
            try:
                # Attempt to parse date in YYYY-MM-DD format
                datetime.strptime(date_val, "%Y-%m-%d")
            except ValueError:
                reasons.append("Invalid order date format")
                
        # 5. Order amount validation check
        try:
            amount = float(amount_val)
            if pd.isna(amount_val) or amount <= 0:
                reasons.append("Order amount must be positive")
        except (ValueError, TypeError):
            reasons.append("Order amount must be positive")
            amount = 0.0

        # High value check
        is_high_value = amount > 100000.0
        
        # Set validation status
        if len(reasons) > 0:
            is_valid = False
            rejection_reason = "; ".join(reasons)
        else:
            is_valid = True
            rejection_reason = ""
            
        # Determine PO level risk:
        # If rejected due to blacklisted vendor: CRITICAL
        # If invalid vendor ID: HIGH
        # If valid and amount > 100,000: HIGH
        # If valid and amount > 50,000: MEDIUM
        # If other invalid: MEDIUM
        # Else: LOW
        if "Vendor is blacklisted" in reasons:
            po_risk = "CRITICAL"
        elif any("Vendor ID does not exist" in r for r in reasons):
            po_risk = "HIGH"
        elif is_valid:
            if amount > 100000.0:
                po_risk = "HIGH"
            elif amount > 50000.0:
                po_risk = "MEDIUM"
            else:
                po_risk = "LOW"
        else:
            po_risk = "MEDIUM"
            
        is_valid_list.append(is_valid)
        rejection_reason_list.append(rejection_reason)
        is_high_value_list.append(is_high_value)
        vendor_name_list.append(vendor_name)
        category_list.append(vendor_category)
        risk_level_list.append(po_risk)
        
    pos['vendor_name'] = vendor_name_list
    pos['category'] = category_list
    pos['is_valid'] = is_valid_list
    pos['rejection_reason'] = rejection_reason_list
    pos['is_high_value'] = is_high_value_list
    pos['risk_level'] = risk_level_list
    
    return pos

def calculate_vendor_spend_and_risk(vendors_df, validated_pos_df):
    """
    Computes spend metrics and risk scores for each vendor.
    Vendor Risk Score formula (capped at 100):
    - Blacklisted: 100 (CRITICAL)
    - Active: 10 + (high_value_count * 15) + (duplicate_count * 25) + (invalid_count * 10)
    - Inactive (non-blacklisted but not active): 40 (MEDIUM)
    """
    vendors = vendors_df.copy()
    pos = validated_pos_df.copy()
    
    summary_data = []
    
    for idx, row in vendors.iterrows():
        v_id = row['vendor_id']
        v_name = row['vendor_name']
        category = row['category']
        status = row['status']
        
        # Filter POs for this vendor
        v_pos = pos[pos['vendor_id'] == v_id]
        
        # Spend metrics (only count VALID orders for spend)
        valid_pos = v_pos[v_pos['is_valid'] == True]
        total_orders = len(valid_pos)
        total_spend = float(valid_pos['order_amount'].sum()) if total_orders > 0 else 0.0
        average_order_value = float(valid_pos['order_amount'].mean()) if total_orders > 0 else 0.0
        
        # Flag counts (count across ALL POs submitted, valid or invalid)
        high_value_count = int(v_pos['is_high_value'].sum())
        
        # Duplicates of this vendor (rejection reason contains "Duplicate purchase order ID")
        duplicate_count = int(v_pos['rejection_reason'].fillna("").str.contains("Duplicate purchase order ID").sum())
        
        # Invalid attempts (excluding duplicates if they are already flagged)
        invalid_count = int((v_pos['is_valid'] == False).sum())
        
        # Calculate Risk Score
        if status == "BLACKLISTED":
            risk_score = 100
        elif status == "ACTIVE":
            # Risk formula
            risk_score = 10 + (high_value_count * 15) + (duplicate_count * 25) + ((invalid_count - duplicate_count) * 10)
            risk_score = min(100, max(10, risk_score))
        else:
            risk_score = 40  # Inactive or other status
            
        # Determine Risk Level
        if risk_score < 35:
            risk_level = "LOW"
        elif risk_score < 65:
            risk_level = "MEDIUM"
        elif risk_score < 85:
            risk_level = "HIGH"
        else:
            risk_level = "CRITICAL"
            
        summary_data.append({
            'vendor_id': v_id,
            'vendor_name': v_name,
            'category': category,
            'status': status,
            'total_orders': total_orders,
            'total_spend': total_spend,
            'average_order_value': average_order_value,
            'high_value_orders_count': high_value_count,
            'duplicate_orders_count': duplicate_count,
            'risk_score': int(risk_score),
            'risk_level': risk_level
        })
        
    return pd.DataFrame(summary_data)

def generate_audit_report(validated_pos_df, vendor_summary_df):
    """
    Creates a comprehensive JSON audit report summarising findings.
    """
    pos = validated_pos_df
    vendors = vendor_summary_df
    
    total_orders = len(pos)
    valid_orders = int((pos['is_valid'] == True).sum())
    invalid_orders = int((pos['is_valid'] == False).sum())
    high_value_orders = int(pos['is_high_value'].sum())
    
    # Counts based on rejection reasons
    reasons = pos['rejection_reason'].fillna("").values
    duplicate_orders = int(sum("Duplicate purchase order ID" in r for r in reasons))
    blacklisted_attempts = int(sum("Vendor is blacklisted" in r for r in reasons))
    
    # Total Procurement Spend (sum of valid orders)
    total_spend = float(pos[pos['is_valid'] == True]['order_amount'].sum())
    
    # Vendor Risk Distribution
    risk_dist = vendors['risk_level'].value_counts().to_dict()
    # Ensure all risk categories are present
    for r in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
        if r not in risk_dist:
            risk_dist[r] = 0
            
    # Rejection Reasons Distribution
    all_reasons = []
    for r in reasons:
        if r != "":
            # Split combined reasons if any
            for part in r.split("; "):
                all_reasons.append(part)
    rejection_dist = {}
    for r in all_reasons:
        rejection_dist[r] = rejection_dist.get(r, 0) + 1
        
    # Spend by Category
    valid_pos = pos[pos['is_valid'] == True]
    cat_spend = {}
    if not valid_pos.empty:
        cat_spend = valid_pos.groupby('category')['order_amount'].sum().to_dict()
    
    # Monthly Spend Trend
    # Parse dates to get Month-Year
    monthly_spend = {}
    valid_dates = valid_pos.copy()
    if not valid_dates.empty:
        try:
            valid_dates['order_month'] = pd.to_datetime(valid_dates['order_date']).dt.strftime('%Y-%m')
            monthly_spend = valid_dates.groupby('order_month')['order_amount'].sum().to_dict()
        except Exception:
            pass # Fallback if dates are not parseable
        
    report = {
        "audit_summary": {
            "total_orders_processed": total_orders,
            "valid_orders": valid_orders,
            "invalid_orders": invalid_orders,
            "high_value_orders": high_value_orders,
            "duplicate_orders": duplicate_orders,
            "blacklisted_vendor_attempts": blacklisted_attempts,
            "total_procurement_spend": total_spend
        },
        "vendor_risk_distribution": risk_dist,
        "rejection_reasons_distribution": rejection_dist,
        "category_spend_distribution": cat_spend,
        "monthly_spend_trend": monthly_spend,
        "timestamp": datetime.now().isoformat()
    }
    
    return report

def run_procurement_audit(workspace_dir="."):
    """
    Main pipeline execution:
    - Loads vendor_master.csv and purchase_orders.csv
    - Validates orders
    - Calculates spend and risk summaries
    - Generates and writes outputs
    """
    vendor_path = os.path.join(workspace_dir, "vendor_master.csv")
    po_path = os.path.join(workspace_dir, "purchase_orders.csv")
    
    # Load input data
    vendors_df, pos_df = load_data(vendor_path, po_path)
    
    # Validate POs
    validated_pos = validate_purchase_orders(vendors_df, pos_df)
    
    # Compute vendor summaries
    vendor_summary = calculate_vendor_spend_and_risk(vendors_df, validated_pos)
    
    # Generate JSON report
    report = generate_audit_report(validated_pos, vendor_summary)
    
    # Paths for outputs
    validated_po_out = os.path.join(workspace_dir, "validated_purchase_orders.csv")
    vendor_summary_out = os.path.join(workspace_dir, "vendor_spend_summary.csv")
    report_json_out = os.path.join(workspace_dir, "procurement_audit_report.json")
    
    # Write to CSV and JSON
    validated_pos.to_csv(validated_po_out, index=False)
    vendor_summary.to_csv(vendor_summary_out, index=False)
    
    with open(report_json_out, 'w') as f:
        json.dump(report, f, indent=4)
        
    print("Procurement Audit engine completed successfully!")
    print(f"Validated POs saved to: {validated_po_out}")
    print(f"Vendor Spend Summary saved to: {vendor_summary_out}")
    print(f"Procurement Audit Report saved to: {report_json_out}")
    
    return validated_pos, vendor_summary, report

if __name__ == "__main__":
    # If run directly, execute the audit in the current working directory
    run_procurement_audit()
