from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import base64
import requests

app = Flask(__name__)
CORS(app)

# GitHub configuration from environment variables
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')  # Your GitHub Personal Access Token
GITHUB_REPO = os.environ.get('GITHUB_REPO')    # Format: "username/repo-name"
DATA_FILE = 'kanban-data.json'  # File in your repo to store data

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

def get_github_file():
    """Get file from GitHub"""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return None, None
    
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DATA_FILE}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            content = base64.b64decode(data['content']).decode('utf-8')
            return json.loads(content), data['sha']
        elif response.status_code == 404:
            return None, None
        else:
            print(f"GitHub API error: {response.status_code}")
            return None, None
    except Exception as e:
        print(f"Error fetching from GitHub: {e}")
        return None, None

def save_to_github(data, sha=None):
    """Save file to GitHub"""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return False
    
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DATA_FILE}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    content = json.dumps(data, indent=2)
    encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    
    payload = {
        "message": "Update kanban data",
        "content": encoded_content,
        "branch": "main"
    }
    
    if sha:
        payload["sha"] = sha
    
    try:
        response = requests.put(url, headers=headers, json=payload)
        return response.status_code in [200, 201]
    except Exception as e:
        print(f"Error saving to GitHub: {e}")
        return False

def load_data():
    """Load data from GitHub or return default"""
    data, sha = get_github_file()
    if data:
        return data, sha
    return DEFAULT_DATA, None

def save_data(data, sha=None):
    """Save data to GitHub"""
    return save_to_github(data, sha)

# Cache for SHA to avoid constant GitHub API calls
current_sha = None

@app.route('/')
def index():
    """Health check"""
    return jsonify({
        "status": "ok", 
        "message": "KanBan API is running",
        "storage": "GitHub" if GITHUB_TOKEN else "Memory (temporary)"
    })

@app.route('/api/data', methods=['GET'])
def get_data():
    """Get all kanban data"""
    global current_sha
    data, current_sha = load_data()
    return jsonify(data)

@app.route('/api/data', methods=['POST'])
def update_data():
    """Update all kanban data"""
    global current_sha
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Get latest SHA before saving
        _, current_sha = get_github_file()
        
        if save_data(data, current_sha):
            # Update SHA after successful save
            _, current_sha = get_github_file()
            return jsonify({"success": True, "message": "Data saved to GitHub"})
        else:
            return jsonify({"error": "Failed to save data to GitHub"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/reset', methods=['POST'])
def reset_data():
    """Reset to default data"""
    global current_sha
    _, current_sha = get_github_file()
    
    if save_data(DEFAULT_DATA, current_sha):
        return jsonify({"success": True, "message": "Data reset to defaults"})
    else:
        return jsonify({"error": "Failed to reset data"}), 500

@app.route('/api/backup', methods=['GET'])
def backup_data():
    """Get backup of all data as JSON download"""
    data, _ = load_data()
    return jsonify(data), 200, {
        'Content-Disposition': 'attachment; filename=kanban_backup.json'
    }

@app.route('/api/history', methods=['GET'])
def get_history():
    """Get commit history for the data file"""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return jsonify({"error": "GitHub not configured"}), 500
    
    url = f"https://api.github.com/repos/{GITHUB_REPO}/commits?path={DATA_FILE}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            commits = response.json()
            history = [{
                "date": commit['commit']['author']['date'],
                "message": commit['commit']['message'],
                "sha": commit['sha'][:7]
            } for commit in commits[:10]]  # Last 10 changes
            return jsonify(history)
        else:
            return jsonify({"error": "Failed to fetch history"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
