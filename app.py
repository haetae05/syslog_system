from flask import Flask, render_template, jsonify, request
from syslog_analyzer import SyslogAnalyzer
from lstm_model import LogLSTMModel
import threading
import os
import json

app = Flask(__name__)

# Global instances
analyzer = SyslogAnalyzer()
lstm = LogLSTMModel()

# Training status globally for simple polling
training_progress = {
    'status': 'idle', # idle, running, completed, error
    'logs': [],
    'progress': 0
}

# Cache analysis result
# analysis_cache = {} -> Disabled to force reload for demo

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/train')
def train_page():
    return render_template('train.html')

@app.route('/predict')
def predict_page():
    return render_template('predict.html')

# API Endpoints
@app.route('/api/analyze')
def api_analyze():
    # Force reload logic
    print("API Analyze called. Reloading stats.json...")
    
    # Check if stats.json exists
    import os, json
    stats_path = "c:/syslog/stats.json"
    
    chart_labels = []
    monthly_totals = []
    monthly_ratios = []
    top_5 = []
    top_5_counts = []
    
    if os.path.exists(stats_path):
        with open(stats_path, 'r', encoding='utf-8') as f:
            stats_data = json.load(f)
            
        # Parse Monthly Data (12 Months)
        for m_data in stats_data.get('monthly', []):
            chart_labels.append(f"{m_data['month']}월")
            monthly_totals.append(m_data.get('errors', 0))
            monthly_ratios.append(m_data.get('percentage', 0))
            
        top_5 = stats_data.get('top_5_global', [])
        top_5_counts = stats_data.get('top_5_counts', []) # Restored for Pie Chart
            
    else:
        print("stats.json not found!")
    
    response_data = {
        'labels': chart_labels,
        'monthly_totals': monthly_totals,
        'monthly_ratios': monthly_ratios,
        'top_5': top_5,
        'top_5_counts': top_5_counts
    }
    
    return jsonify(response_data)

@app.route('/api/train', methods=['POST'])
def api_train():
    global training_progress
    
    # Check if analysis is done, if not, try loading from disk
    if not analyzer.top_5_types:
        analyzer.load_stats_from_json()
        
    if not analyzer.top_5_types:
        return jsonify({'status': 'error', 'message': 'Please visit Dashboard to analyze data first (stats.json missing).'})
    
    # Run in background thread to not block response
    def run_training():
        global training_progress
        training_progress['status'] = 'running'
        training_progress['logs'] = ["Initializing...", "Loading Data (Months: 05 - 11)..."]
        
        # Optimized: Load the 5-11 month data from the analyzer
        training_months = [f"{m:02d}" for m in range(5, 12)]
        training_texts = analyzer.get_training_data(target_months=training_months)
        
        if not training_texts:
            training_progress['status'] = 'error'
            training_progress['logs'].append("Error: No training data found for May-Nov.")
            return

        training_progress['logs'].append(f"Data Loaded. {len(training_texts)} samples from May-Nov range.")
        training_progress['progress'] = 0
        
        # Simulated Epochs for the demo UI
        epochs = 2
        for epoch in range(epochs):
            msg = f"Epoch {epoch+1}/{epochs} started..."
            print(msg)
            training_progress['logs'].append(msg)
            training_progress['progress'] = int(((epoch) / epochs) * 100)
            
            # Use actual training logic
            lstm.train(training_texts, epochs=1) # Train 1 epoch at a time
            
            msg = f"Epoch {epoch+1}/{epochs} completed."
            training_progress['logs'].append(msg)
            training_progress['progress'] = int(((epoch+1) / epochs) * 100)
            
        training_progress['status'] = 'completed'
        training_progress['logs'].append("Training Finished Successfully.")
        training_progress['progress'] = 100
        
    if training_progress['status'] == 'running':
         return jsonify({'status': 'success', 'message': 'Training is already running.'})

    thread = threading.Thread(target=run_training)
    thread.start()
    
    return jsonify({'status': 'success', 'message': 'Training started. Data loading in background.'})

@app.route('/api/train/status')
def api_train_status():
    return jsonify(training_progress)



@app.route('/api/forecast', methods=['GET'])
def api_forecast():
    import json
    import os
    from datetime import datetime, timedelta
    
    stats_path = "c:/syslog/stats.json"
    if not os.path.exists(stats_path):
        return jsonify({'status': 'error', 'message': 'Stats not found'})
        
    with open(stats_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    # NEW LOGIC: Use pre-calculated global top types for May-Nov
    top_types_list = data.get('top_types_summary', [])
    target_types = top_types_list[:15]
    
    forecast_results = []
    
    # Logic: Forecast Timeline Generation (7-Month focused: 5-11)
    # Total Time Window = 214 days * 24 = 5136 hours
    # (May:31, Jun:30, Jul:31, Aug:31, Sep:30, Oct:31, Nov:30 = 214 days)    
    total_hours = 214 * 24 
    
    # Consistency Fix: Use "Start of Today" as an anchor so times don't drift on every click
    current_time = datetime.now()
    anchor_time = datetime(current_time.year, current_time.month, current_time.day)
    
    forecast_timeline = []
    
    horizon_days = 30 # Look ahead 1 month
    max_events_per_type = 10 # More events for the timeline
    
    for error_type, count in target_types:
        if count <= 0: continue
        
        mtbf_hours = total_hours / count
        
        # Risk Level Logic
        if mtbf_hours < 24:
            risk = "CRITICAL (Daily)"
            risk_color = "text-danger"
        elif mtbf_hours < 168: # 7 days
            risk = "HIGH (Weekly)"
            risk_color = "text-warning"
        else:
            risk = "MEDIUM (Monthly+)"
            risk_color = "text-success"
            
        import math
        prob_24h_val = 1 - math.exp(-24 / mtbf_hours) if mtbf_hours > 0 else 0
        prob_text = f"{prob_24h_val * 100:.1f}%"

        # Generate occurrences cycling from the anchor
        # Find the first occurrence AFTER current_time
        # (Start + MTBF * N) > Now
        elapsed_since_anchor = (current_time - anchor_time).total_seconds() / 3600
        n_start = int(elapsed_since_anchor / mtbf_hours) + 1
        
        for n in range(n_start, n_start + max_events_per_type):
            event_time = anchor_time + timedelta(hours=n * mtbf_hours)
            
            # Stop if beyond horizon
            if event_time > current_time + timedelta(days=horizon_days):
                break
            
            forecast_timeline.append({
                'timestamp_iso': event_time.isoformat(), # Raw format for JS countdown
                'type': error_type,
                'count': count,
                'mtbf': f"{mtbf_hours:.1f}h",
                'next_est': event_time.strftime('%Y-%m-%d %H:%M'),
                'risk': risk,
                'risk_color': risk_color,
                'prob_24h': prob_text,
                'occurrence_index': n # Absolute sequence number
            })
            
    # Sort prediction by timestamp (Chronological Order)
    forecast_timeline.sort(key=lambda x: x['timestamp_iso'])
    
    return jsonify({'status': 'success', 'data': forecast_timeline})

if __name__ == '__main__':
    # Use Waitress for Production Stability
    from waitress import serve
    import os
    
    # Port configuration for Cloud Hosting (Render, etc.)
    port = int(os.environ.get("PORT", 5000))
    
    print(f"Starting Production Server on http://0.0.0.0:{port}")
    serve(app, host='0.0.0.0', port=port, threads=6)

