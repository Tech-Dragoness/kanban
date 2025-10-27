from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os

app = Flask(__name__)
CORS(app)

# Database file path
DB_FILE = 'database.json'

# Default data structure
DEFAULT_DATA = {
    "columns": [
        {"id": 1, "name": "To Do", "tasks": {"major": [], "minor": []}},
        {"id": 2, "name": "In Progress", "tasks": {"major": [], "minor": []}},
        {"id": 3, "name": "Done", "tasks": {"major": [], "minor": []}}
    ],
    "nextColumnId": 4,
    "nextTaskId": 1,
    "dropdownStates": {}
}

def load_data():
    """Load data from JSON file or create default if doesn't exist"""
    if not os.path.exists(DB_FILE):
        save_data(DEFAULT_DATA)
        return DEFAULT_DATA
    
    try:
        with open(DB_FILE, 'r') as f:
            data = json.load(f)
            # Validate data structure
            if not data or 'columns' not in data:
                return DEFAULT_DATA
            return data
    except (json.JSONDecodeError, IOError):
        return DEFAULT_DATA

def save_data(data):
    """Save data to JSON file"""
    try:
        with open(DB_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except IOError as e:
        print(f"Error saving data: {e}")
        return False

@app.route('/')
def index():
    """Serve the HTML file"""
    return send_from_directory('.', 'kanban.html')

@app.route('/api/data', methods=['GET'])
def get_data():
    """Get all kanban data"""
    data = load_data()
    return jsonify(data)

@app.route('/api/data', methods=['POST'])
def update_data():
    """Update all kanban data"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        if save_data(data):
            return jsonify({"success": True, "message": "Data saved successfully"})
        else:
            return jsonify({"error": "Failed to save data"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/reset', methods=['POST'])
def reset_data():
    """Reset to default data"""
    if save_data(DEFAULT_DATA):
        return jsonify({"success": True, "message": "Data reset to defaults"})
    else:
        return jsonify({"error": "Failed to reset data"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
