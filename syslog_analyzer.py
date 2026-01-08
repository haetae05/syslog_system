import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

import json

SYSLOG_DIR = "c:/syslog/syslog1년치"
STATS_FILE = "c:/syslog/stats.json"

class SyslogAnalyzer:
    def __init__(self, root_dir=SYSLOG_DIR):
        self.root_dir = root_dir
        self.top_5_types = []
        self.daily_counts = {} # Used if full scan
        self.monthly_counts = {} # Used if loaded from json
        self.july_messages = []
        self.use_json = False

    def load_stats_from_json(self):
        if os.path.exists(STATS_FILE):
            print(f"Loading pre-calculated stats from {STATS_FILE}...")
            try:
                with open(STATS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                full_type_counter = {}
                
                # Parse monthly data
                for m_data in data.get('monthly', []):
                    month = m_data['month']
                    self.monthly_counts[month] = {}
                    
                    for t_name, t_count in m_data.get('top_types', []):
                        full_type_counter[t_name] = full_type_counter.get(t_name, 0) + t_count
                        self.monthly_counts[month][t_name] = t_count

                # Identify Top 5
                # Use global top 5 if available, else calculate
                if 'top_5_global' in data:
                    self.top_5_types = data['top_5_global']
                else:
                    sorted_types = sorted(full_type_counter.items(), key=lambda x: x[1], reverse=True)
                    self.top_5_types = [t[0] for t in sorted_types[:5]]
                    
                self.use_json = True
                print(f"Loaded Top 5 from JSON: {self.top_5_types}")
                return True
            except Exception as e:
                print(f"Failed to load JSON: {e}")
                return False
        return False

    def analyze_12_months(self):
        # Try loading from stats.json first
        if self.load_stats_from_json():
            return self.top_5_types

        print("Analyzing 12 months of data... this may take a moment.")
        
        type_counter = {}
        
        # Iterate through all months 01-12
        for month in range(1, 13):
            month_str = f"{month:02d}"
            month_path = os.path.join(self.root_dir, month_str)
            if not os.path.exists(month_path):
                continue
                
            files = glob.glob(os.path.join(month_path, "*.txt"))
            for fpath in files:
                try:
                    # OPTIMIZATION: Read only first 2000 lines per file to reduce lag
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                        line_count = 0
                        for line in f:
                            if line_count > 2000: break 
                            line_count += 1
                            
                            parts = line.split('\t')
                            if len(parts) > 8:
                                # Col 2 (index 2) is Severity, check for 'err'
                                if 'err' in parts[2]:
                                    error_type = parts[7]
                                    
                                    # Count for Top 5
                                    type_counter[error_type] = type_counter.get(error_type, 0) + 1
                                    
                                    # Date for Daily Ratio (Col 5 is Date "2025-01-01 00:00:00")
                                    # We just need the date part
                                    try:
                                        date_str = parts[5].split()[0]
                                        if date_str not in self.daily_counts:
                                            self.daily_counts[date_str] = {}
                                        self.daily_counts[date_str][error_type] = self.daily_counts[date_str].get(error_type, 0) + 1
                                    except:
                                        pass
                                    
                                    if month == 7:
                                        self.july_messages.append((error_type, parts[8]))

                except Exception as e:
                    print(f"Error reading {fpath}: {e}")

        # Identify Top 5
        sorted_types = sorted(type_counter.items(), key=lambda x: x[1], reverse=True)
        self.top_5_types = [t[0] for t in sorted_types[:5]]
        
        print(f"Top 5 Error Types: {self.top_5_types}")
        return self.top_5_types

    def get_training_data(self, target_months=['07']):
        self.july_messages = [] # Reset/Reuse variable (naming legacy but logic updated)
        
        print(f"Loading training data for months: {target_months}...")
        
        for m_str in target_months:
            month_path = os.path.join(self.root_dir, m_str)
            if os.path.exists(month_path):
                print(f" Scanning {month_path}...")
                files = glob.glob(os.path.join(month_path, "*.txt"))
                for fpath in files:
                    try:
                        # Sample 2000 lines for training speed too
                        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                            for line in f:
                                parts = line.split('\t')
                                if len(parts) > 8 and 'err' in parts[2].lower():
                                    self.july_messages.append((parts[7], parts[8]))
                    except: pass
            else:
                print(f"Warning: Data for month {m_str} not found.")

        # Return all error messages found (matching the 948 count from total analysis)
        training_messages = [msg for r_type, msg in self.july_messages]
        return training_messages

