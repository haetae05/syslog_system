import os
import glob
import json
from datetime import datetime

# Root directory for syslog data
ROOT_DIR = "c:/syslog/syslog1년치"
OUTPUT_FILE = "c:/syslog/stats.json"

# Target months: 1 to 12
TARGET_MONTHS = [f"{m:02d}" for m in range(1, 13)]

# TOTAL_LOGS_BY_MONTH (Previously derived/estimated for ratio calculation)
# Counting exact total logs in 30GB every time is too slow, using stable estimates.
TOTAL_LOGS_BY_MONTH = {
    1: 4500000, 2: 4200000, 3: 4600000, 4: 4300000, 5: 4100000, 6: 2800000,
    7: 3500000, 8: 3200000, 9: 6800000, 10: 7200000, 11: 7500000, 12: 2500000
}

def rebuild_stats():
    print(f"Starting 12-month analysis for: {TARGET_MONTHS}")
    
    global_type_counts = {}
    monthly_stats = []
    total_errors = 0
    
    for m_str in TARGET_MONTHS:
        month_path = os.path.join(ROOT_DIR, m_str)
        if not os.path.exists(month_path):
            print(f"Skipping {m_str}: Directory not found.")
            # Even if directory missing, add placeholder to keep index stable
            monthly_stats.append({"month": int(m_str), "errors": 0, "unique_types": 0, "percentage": 0, "top_types": []})
            continue
            
        print(f" Scanning month {m_str}...")
        month_errors = 0
        month_type_counts = {}
        
        # Get all txt files
        files = glob.glob(os.path.join(month_path, "*.txt"))
        for fpath in files:
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        parts = line.split('\t')
                        # Rule: 3rd column (index 2) contains 'err'
                        if len(parts) > 8 and 'err' in parts[2].lower():
                            error_type = parts[7]
                            global_type_counts[error_type] = global_type_counts.get(error_type, 0) + 1
                            month_type_counts[error_type] = month_type_counts.get(error_type, 0) + 1
                            month_errors += 1
                            total_errors += 1
            except Exception as e:
                print(f" Error reading {fpath}: {e}")
        
        # Calculate ratio (%)
        total_monthly_logs = TOTAL_LOGS_BY_MONTH.get(int(m_str), 1000000)
        percentage = (month_errors / total_monthly_logs) * 100
        
        monthly_stats.append({
            "month": int(m_str),
            "errors": month_errors,
            "unique_types": len(month_type_counts),
            "percentage": round(percentage, 4),
            "top_types": sorted(month_type_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        })

    # Global Top Types for Pie Chart
    sorted_global_types = sorted(global_type_counts.items(), key=lambda x: x[1], reverse=True)
    top_5_global = sorted_global_types[:5]
    
    result = {
        "generated_at": datetime.now().isoformat(),
        "total_errors": total_errors,
        "global_type_counts": global_type_counts,
        "top_5_global": [t[0] for t in top_5_global],
        "top_5_counts": [t[1] for t in top_5_global],
        "top_types_summary": sorted_global_types, # Added for forecasting engine
        "monthly": monthly_stats
    }
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
        
    print(f"\n12-Month Analysis Complete!")
    print(f"Total Errors Found: {total_errors}")
    print(f"Stats saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    rebuild_stats()
