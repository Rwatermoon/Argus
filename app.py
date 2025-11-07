
import os
import subprocess
from flask import Flask, render_template, send_from_directory, Response, request
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Get API keys from environment variables
GOOGLE_API_KEY = os.getenv("GOOGLE_ROADS_API_KEY")
HERE_API_KEY = os.getenv("HERE_MAP_DATA_API_KEY")
MAPBOX_TOKEN = os.getenv("MAPBOX_ACCESS_TOKEN")

process = None

@app.route('/')
def index():
    return render_template('index.html', mapbox_token=MAPBOX_TOKEN)

@app.route('/compare', methods=['POST'])
def compare():
    """Run the data processing script."""
    global process
    if process and process.poll() is None:
        return {"status": "error", "output": "A comparison is already in progress."}

    data = request.get_json()
    bbox = data.get('bbox')
    strategy = data.get('strategy', 'shortest') # Default to 'shortest' if not provided

    if not bbox or len(bbox) != 4:
        return {"status": "error", "output": "Invalid BBOX provided."}

    # This is not recommended for production environments.
    # A better approach would be to use a task queue like Celery.
    cmd = ['python', '-u', 'data_processing.py'] + [str(c) for c in bbox] + [strategy]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return {"status": "success"}

@app.route('/progress')
def progress():
    """Stream the output of the data processing script."""
    def generate():
        global process
        if not process:
            return
        for line in iter(process.stdout.readline, ''):
            yield f"data: {line}\n\n"
        process.stdout.close()
        process.wait()
        process = None

    return Response(generate(), mimetype='text/event-stream')

@app.route('/data/<path:filename>')
def serve_data(filename):
    """Serve data files."""
    return send_from_directory('data', filename)

if __name__ == '__main__':
    app.run(debug=True)
