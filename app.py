from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import base64
import requests
from datetime import datetime

app = Flask(__name__)
CORS(app)

# GitHub configuration from environment variables
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_REPO = os.environ.get('GITHUB_REPO')
DATA_FILE = 'kanban-data.json'

# Fallback to local file if GitHub not configured
LOCAL_DB_FILE = 'database.json'

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

def is_github_configured():
    """Check if GitHub is properly configured"""
    return bool(GITHUB_TOKEN and GITHUB_REPO)

def get_github_file():
    """Get file from GitHub"""
    if not is_github_configured():
        return None, None
    
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DATA_FILE}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"GitHub GET status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            content = base64.b64decode(data['content']).decode('utf-8')
            return json.loads(content), data['sha']
        elif response.status_code == 404:
            print("File not found on GitHub, will create new")
            return None, None
        else:
            print(f"GitHub error response: {response.text}")
            return None, None
    except Exception as e:
        print(f"Error fetching from GitHub: {e}")
        return None, None

def save_to_github(data, sha=None):
    """Save file to GitHub"""
    if not is_github_configured():
        print("GitHub not configured")
        return False
    
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DATA_FILE}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    content = json.dumps(data, indent=2)
    encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    
    payload = {
        "message": f"Update kanban data - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "content": encoded_content,
        "branch": "main"
    }
    
    if sha:
        payload["sha"] = sha
    
    try:
        response = requests.put(url, headers=headers, json=payload, timeout=10)
        print(f"GitHub PUT status: {response.status_code}")
        
        if response.status_code not in [200, 201]:
            print(f"GitHub save error: {response.text}")
            return False
        return True
    except Exception as e:
        print(f"Error saving to GitHub: {e}")
        return False

def load_from_local():
    """Load data from local file"""
    if not os.path.exists(LOCAL_DB_FILE):
        save_to_local(DEFAULT_DATA)
        return DEFAULT_DATA
    
    try:
        with open(LOCAL_DB_FILE, 'r') as f:
            data = json.load(f)
            if not data or 'columns' not in data:
                return DEFAULT_DATA
            return data
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading local file: {e}")
        return DEFAULT_DATA

def save_to_local(data):
    """Save data to local file"""
    try:
        with open(LOCAL_DB_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except IOError as e:
        print(f"Error saving to local file: {e}")
        return False

def load_data():
    """Load data from GitHub or fallback to local"""
    if is_github_configured():
        data, sha = get_github_file()
        if data:
            print("Loaded data from GitHub")
            return data, sha, 'github'
        print("GitHub failed, trying local file")
    
    data = load_from_local()
    print("Loaded data from local file")
    return data, None, 'local'

def save_data(data, sha=None):
    """Save data to GitHub and local backup"""
    github_success = False
    local_success = False
    
    # Try GitHub first if configured
    if is_github_configured():
        github_success = save_to_github(data, sha)
        if github_success:
            print("Saved to GitHub successfully")
    
    # Always save to local as backup
    local_success = save_to_local(data)
    if local_success:
        print("Saved to local file successfully")
    
    return github_success or local_success

@app.route('/')
def index():
    """Health check"""
    storage_type = "GitHub + Local Backup" if is_github_configured() else "Local File Only"
    github_status = "✓ Connected" if is_github_configured() else "✗ Not configured"
    
    return jsonify({
        "status": "ok",
        "message": "KanBan API is running",
        "storage": storage_type,
        "github_configured": is_github_configured(),
        "github_status": github_status,
        "github_repo": GITHUB_REPO if GITHUB_REPO else "Not set",
        "github_token": "Set" if GITHUB_TOKEN else "Not set"
    })

@app.route('/api/data', methods=['GET'])
def get_data():
    """Get all kanban data"""
    data, sha, source = load_data()
    response = jsonify(data)
    response.headers['X-Data-Source'] = source
    return response

@app.route('/api/data', methods=['POST'])
def update_data():
    """Update all kanban data"""
    try:
        data = request.get_json()
        if not data:
            print("No data provided in request")
            return jsonify({"error": "No data provided"}), 400
        
        print(f"Received data with {len(data.get('columns', []))} columns")
        
        # Get latest SHA if using GitHub
        sha = None
        if is_github_configured():
            _, sha = get_github_file()
            print(f"Current SHA: {sha}")
        
        if save_data(data, sha):
            return jsonify({
                "success": True,
                "message": "Data saved successfully",
                "storage": "github" if is_github_configured() else "local"
            })
        else:
            print("Save failed")
            return jsonify({"error": "Failed to save data"}), 500
    except Exception as e:
        print(f"Error in update_data: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/reset', methods=['POST'])
def reset_data():
    """Reset to default data"""
    sha = None
    if is_github_configured():
        _, sha = get_github_file()
    
    if save_data(DEFAULT_DATA, sha):
        return jsonify({"success": True, "message": "Data reset to defaults"})
    else:
        return jsonify({"error": "Failed to reset data"}), 500

@app.route('/api/backup', methods=['GET'])
def backup_data():
    """Get backup of all data as JSON download"""
    data, _, _ = load_data()
    return jsonify(data), 200, {
        'Content-Disposition': 'attachment; filename=kanban_backup.json'
    }

@app.route('/api/test-github', methods=['GET'])
def test_github():
    """Test GitHub connection"""
    if not is_github_configured():
        return jsonify({
            "configured": False,
            "error": "GITHUB_TOKEN or GITHUB_REPO not set"
        })
    
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return jsonify({
                "configured": True,
                "connected": True,
                "repo": GITHUB_REPO,
                "message": "GitHub connection successful"
            })
        else:
            return jsonify({
                "configured": True,
                "connected": False,
                "error": f"Status {response.status_code}: {response.text}"
            })
    except Exception as e:
        return jsonify({
            "configured": True,
            "connected": False,
            "error": str(e)
        })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
