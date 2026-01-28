#!/usr/bin/env python3
"""
Linker Mind Web Interface
Provides a web UI to visualize extracted content
"""
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from flask import Flask, render_template, request, jsonify
    from main import LinkerMind
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

app = Flask(__name__)
app.jinja_env.globals.update(len=len)

# Initialize Linker Mind
linker_app = LinkerMind(enable_ai=True)


def load_all_content():
    """Load all stored content from linker_data.json"""
    try:
        with open('linker_data.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def get_content_by_id(content_id: str):
    """Get specific content by ID"""
    all_content = load_all_content()
    for item in all_content:
        if item.get('id') == content_id:
            return item
    return None


@app.route('/')
def index():
    """Home page - list all extracted content"""
    all_content = load_all_content()
    # Sort by timestamp, newest first
    all_content.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

    # Calculate stats
    total = len(all_content)
    with_images = sum(1 for item in all_content if item.get('media', {}).get('images'))
    with_screenshots = sum(1 for item in all_content if item.get('media', {}).get('screenshots'))

    return render_template('index.html', items=all_content, stats={
        'total': total,
        'with_images': with_images,
        'with_screenshots': with_screenshots
    })


@app.route('/content/<content_id>')
def view_content(content_id: str):
    """View specific content details"""
    item = get_content_by_id(content_id)
    if not item:
        return "Content not found", 404
    return render_template('detail.html', item=item)


@app.route('/api/process', methods=['POST'])
def process_url():
    """API endpoint to process a URL"""
    data = request.json
    url = data.get('url')
    enable_ai = data.get('enable_ai', True)

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    try:
        content = linker_app.process(url)
        if content:
            return jsonify({
                'success': True,
                'id': content.id,
                'message': 'Content processed successfully'
            })
        else:
            return jsonify({'error': 'Processing failed'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/content')
def api_content():
    """API endpoint to get all content"""
    all_content = load_all_content()
    all_content.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    return jsonify(all_content)


@app.template_filter('format_timestamp')
def format_timestamp(timestamp_str):
    """Format timestamp for display"""
    if not timestamp_str:
        return 'N/A'
    try:
        dt = datetime.fromisoformat(str(timestamp_str))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return str(timestamp_str)


@app.template_filter('truncate')
def truncate_text(text: str, length: int = 200) -> str:
    """Truncate text to specified length"""
    if not text:
        return ''
    if len(text) <= length:
        return text
    return text[:length] + '...'


@app.template_filter('format_number')
def format_number(num: int) -> str:
    """Format large numbers with commas"""
    if num is None:
        return 'N/A'
    return f"{num:,}"


if __name__ == '__main__':
    if not FLASK_AVAILABLE:
        print("❌ Flask is not installed. Install with: pip install flask")
        print("   Then run: python3 web_interface.py")
        sys.exit(1)

    port = 5001  # Use 5001 to avoid conflict with AirPlay on macOS

    print("🌐 Linker Mind Web Interface")
    print("=" * 50)
    print(f"   Server: http://localhost:{port}")
    print("   Press Ctrl+C to stop")
    print("=" * 50 + "\n")

    app.run(debug=True, host='0.0.0.0', port=port)
