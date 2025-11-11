
import os
import subprocess
import json
from datetime import datetime
from flask import Flask, render_template, send_from_directory, Response, request, jsonify
from dotenv import load_dotenv
from osm_routing import get_graphhopper_usage
from gemini_client import stream_gemini_evaluation, stream_openai_compatible_evaluation
from data_processing import calculate_single_route_comparison

load_dotenv()

app = Flask(__name__)

# Get API keys from environment variables
GOOGLE_API_KEY = os.getenv("GOOGLE_ROADS_API_KEY")
HERE_API_KEY = os.getenv("HERE_MAP_DATA_API_KEY")
MAPBOX_TOKEN = os.getenv("MAPBOX_ACCESS_TOKEN")

process = None
ai_stream_generator = None

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

@app.route('/compare-places', methods=['POST'])
def compare_places():
    """Run the data processing script using Google Places POIs."""
    global process
    if process and process.poll() is None:
        return {"status": "error", "output": "A comparison is already in progress."}

    data = request.get_json()
    bbox = data.get('bbox')
    strategy = data.get('strategy', 'shortest')
    osm_provider = data.get('osm_provider', 'osrm')

    if not bbox or len(bbox) != 4:
        return {"status": "error", "output": "Invalid BBOX provided."}

    cmd = ['python', '-u', 'data_processing.py', '--places', *map(str, bbox), strategy, osm_provider]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return {"status": "success"}

@app.route('/calculate-single-route', methods=['POST'])
def calculate_single():
    """Calculate and return a single route comparison."""
    global process
    if process and process.poll() is None:
        return jsonify({"status": "error", "output": "A comparison is already in progress."}), 400

    data = request.get_json()
    origin = data.get('origin')
    destination = data.get('destination')
    strategy = data.get('strategy', 'shortest')
    osm_provider = data.get('osm_provider', 'osrm')

    if not origin or not destination or len(origin) != 2 or len(destination) != 2:
        return jsonify({"status": "error", "output": "Origin or destination missing."}), 400

    cmd = [
        'python', '-u', 'data_processing.py', '--manual',
        str(origin[0]), str(origin[1]),
        str(destination[0]), str(destination[1]),
        strategy, osm_provider
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return jsonify({"status": "success"})

@app.route('/evaluate-with-ai', methods=['POST'])
def evaluate_with_ai():
    """
    Starts a streaming AI evaluation for a given route pair.
    """
    global ai_stream_generator
    data = request.get_json()
    user_prompt = data.get('prompt')
    route_id = data.get('route_id')
    ai_provider = data.get('ai_provider', 'deepseek') # Default to deepseek

    if not user_prompt or route_id is None:
        return jsonify({"status": "error", "output": "Prompt or route_id missing."}), 400

    try:
        with open('data/stats.json', 'r') as f:
            all_stats = json.load(f)
        
        route_stats = all_stats.get(str(route_id))
        if not route_stats:
            return jsonify({"status": "error", "output": f"No data found for route ID {route_id}."}), 404

        # Choose the correct generator based on the provider
        if ai_provider == 'gemini':
            ai_stream_generator = stream_gemini_evaluation(route_stats, user_prompt)
        else:
            ai_stream_generator = stream_openai_compatible_evaluation(ai_provider, route_stats, user_prompt)
            
        return jsonify({"status": "success"})

    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({"status": "error", "output": "Statistics data not found. Please run a comparison first."}), 404
    except Exception as e:
        return jsonify({"status": "error", "output": str(e)}), 500

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

@app.route('/ai-stream')
def ai_stream():
    """Streams the AI evaluation response."""
    def generate_ai_response():
        global ai_stream_generator
        if not ai_stream_generator:
            return
        
        for chunk in ai_stream_generator:
            yield f"data: {json.dumps({'text': chunk})}\n\n"
        ai_stream_generator = None # Clear after use

    return Response(generate_ai_response(), mimetype='text/event-stream')

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
