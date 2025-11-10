
import os
import subprocess
import json
from datetime import datetime
from flask import Flask, render_template, send_from_directory, Response, request, jsonify
from dotenv import load_dotenv
from osm_routing import get_graphhopper_usage

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
    strategy = data.get('strategy', 'shortest')
    osm_provider = data.get('osm_provider', 'osrm') # Get the OSM provider

    if not bbox or len(bbox) != 4:
        return {"status": "error", "output": "Invalid BBOX provided."}

    cmd = [
        'python', '-u', 'data_processing.py',
        *map(str, bbox), # Unpack bbox elements
        strategy,
        osm_provider # Add osm_provider to the command
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return {"status": "success"}

@app.route('/progress')
def progress():
    """Stream the output of the data processing script."""
    def generate():
        global process
        if not process:
            return
        # Stream output line by line
        with process.stdout:
            for line in iter(process.stdout.readline, ''):
                yield f"data: {line}\n\n"
        process.wait() # Wait for the process to finish
        yield 'event: close\ndata: Connection closed by server\n\n'
        process = None

    return Response(generate(), mimetype='text/event-stream')

@app.route('/graphhopper-usage')
def graphhopper_usage():
    """Return the GraphHopper API usage for the current day."""
    count = get_graphhopper_usage()
    return jsonify({'count': count})


@app.route('/data/<path:filename>')
def serve_data(filename):
    """Serve data files."""
    return send_from_directory('data', filename)

if __name__ == '__main__':
    app.run(debug=True)
