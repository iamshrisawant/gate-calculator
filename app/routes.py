from flask import Blueprint, request, jsonify, render_template, send_file, current_app
import os
import io
from .services import extraction, scoring, email_service

main_bp = Blueprint('main', __name__)

ADMIN_PIN = os.getenv("ADMIN_PIN")

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/admin')
def admin():
    return render_template('admin.html')

@main_bp.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@main_bp.route('/contribute')
def contribute():
    return render_template('contribute.html')

@main_bp.route('/api/detect_metadata', methods=['POST'])
def detect_meta():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    # Read file into memory
    file_bytes = file.read()
    file_stream = io.BytesIO(file_bytes)
    
    try:
        # extraction.detect_metadata now supports streams
        meta = extraction.detect_metadata(file_stream, filename=file.filename)
        return jsonify(meta)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@main_bp.route('/api/upload_paper', methods=['POST'])
def upload_paper():
    storage = current_app.storage
    
    if 'answer_key' not in request.files:
        return jsonify({"error": "Answer Key file is required"}), 400
        
    key_file = request.files['answer_key']
    paper_file = request.files.get('question_paper')
    
    year = request.form.get('year', '2025')
    code = request.form.get('paper_code', '').upper()
    mode = request.form.get('mode', 'staging')
    admin_pin = request.headers.get('X-Admin-Pin', '')
    
    if not code:
        return jsonify({"error": "Paper Code is required"}), 400
        
    if mode == 'live':
        if admin_pin != ADMIN_PIN:
            return jsonify({"error": "Invalid Admin PIN for Live Upload"}), 403
        target_root = "live"
    else:
        target_root = "staging"

    # Define paths
    base_dir = f"{target_root}/{year}/{code}"
    key_path = f"{base_dir}/answer_key.pdf"
    paper_path = f"{base_dir}/question_paper.pdf"
    
    # Read files to memory
    key_bytes = key_file.read()
    paper_bytes = None
    if paper_file:
        paper_bytes = paper_file.read()

    try:
        # 1. Save Files via Storage
        storage.save(key_path, key_bytes)
        if paper_bytes:
            storage.save(paper_path, paper_bytes)
        
        # 2. Extract Key from Memory Stream
        key_stream = io.BytesIO(key_bytes)
        paper_stream = io.BytesIO(paper_bytes) if paper_bytes else None
        schema = extraction.extract_answer_key(key_stream, paper_code=code, paper_source=paper_stream)
        
        # 3. Save Schema
        schema_path = f"{base_dir}/schema.json"
        storage.save_json(schema_path, schema)
        
        if mode == 'live':
             return jsonify({"message": f"Successfully published {code} ({year}) to LIVE!"})
        else:
            # Prepare attachments for email (bytes)
            # No attachments sent to save memory on free tier
            email_service.send_approval_email_async(year, code, attachments=None)
            return jsonify({"message": f"Submitted {code} ({year}) for review!"})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@main_bp.route('/api/papers', methods=['GET'])
def list_papers():
    storage = current_app.storage
    tree = {}
    
    # List Years in 'live'
    years = storage.list("live")
    for year in years:
        tree[year] = []
        # List Codes in 'live/year'
        codes = storage.list(f"live/{year}")
        for code in codes:
            # Check if schema exists
            if storage.exists(f"live/{year}/{code}/schema.json"):
                tree[year].append(code)
    
    return jsonify(tree)

@main_bp.route('/api/calculate', methods=['POST'])
def calculate():
    storage = current_app.storage
    data = request.json
    url = data.get('url')
    year = data.get('year')
    code = data.get('paper_code')
    
    if not all([url, year, code]):
        return jsonify({"error": "Missing required fields (url, year, code)"}), 400
    
    schema_path = f"live/{year}/{code}/schema.json"
    
    if not storage.exists(schema_path):
        return jsonify({"error": "Paper not found on server."}), 404
        
    try:
        print(f"[DEBUG] Reading schema from: {schema_path}")
        schema = storage.read_json(schema_path)
        if not schema:
             print("[ERROR] Schema not found or empty.")
             return jsonify({"error": "Failed to read schema."}), 500
        
        print(f"[DEBUG] Schema keys count: {len(schema)}")
        print(f"[DEBUG] Calculating score for URL: {url}")
        
        report = scoring.calculate_score(url, schema)
        if "error" in report:
            print(f"[ERROR] Calculation failed: {report['error']}")
            return jsonify(report), 500
            
        print(f"[DEBUG] Calculation success. Score: {report['summary']['total_score']}")
        return jsonify(report)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@main_bp.route('/api/check_paper_exists', methods=['GET'])
def check_paper_exists():
    storage = current_app.storage
    year = request.args.get('year')
    code = request.args.get('code')
    if not year or not code:
        return jsonify({"exists": False})
    
    path = f"live/{year}/{code.upper()}/schema.json"
    return jsonify({"exists": storage.exists(path)})

@main_bp.route('/api/staging_file')
def staging_file():
    storage = current_app.storage
    year = request.args.get('year')
    code = request.args.get('code')
    filename = request.args.get('file')
    
    if not (year and code and filename):
        return "Missing parameters", 400
        
    path = f"staging/{year}/{code}/{filename}"
    data = storage.read(path)
    
    if not data:
        return "File not found", 404
        
    return send_file(
        io.BytesIO(data),
        download_name=filename,
        as_attachment=False # Inline view
    )

@main_bp.route('/api/approve_token/<token>', methods=['GET'])
def approve_token(token):
    storage = current_app.storage
    try:
        data = email_service.serializer.loads(token, salt="approve-paper", max_age=86400)
        year = data['year']
        code = data['code']
        
        src = f"staging/{year}/{code}"
        dst = f"live/{year}/{code}"
        
        # Check if src exists (by checking schema)
        if not storage.exists(f"{src}/schema.json"):
             return "Error: Paper not found in staging", 404

        storage.move(src, dst)
        return f"<h1>Success!</h1><p>Paper {code} ({year}) has been approved and is now LIVE.</p><a href='/'>Go to App</a>"
    except Exception as e:
        return f"Invalid or Expired Token: {str(e)}", 400

@main_bp.route('/api/staging_queue', methods=['GET'])
def staging_queue():
    storage = current_app.storage
    queue = []
    
    years = storage.list("staging")
    for year in years:
        codes = storage.list(f"staging/{year}")
        for code in codes:
             queue.append({"year": year, "code": code})
             
    return jsonify(queue)

def verify_request_pin(req):
    pin = req.headers.get('X-Admin-Pin')
    if pin and pin == ADMIN_PIN: return True
    if req.is_json:
        data = req.json
        if data and data.get('pin') == ADMIN_PIN: return True
    return False

@main_bp.route('/api/verify_pin', methods=['POST'])
def verify_pin_route():
    data = request.json
    if data.get('pin') == ADMIN_PIN: return jsonify({"success": True})
    return jsonify({"success": False, "error": "Incorrect PIN"}), 401

@main_bp.route('/api/approve_paper', methods=['POST'])
def approve_paper():
    storage = current_app.storage
    if not verify_request_pin(request): return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    year = data.get('year')
    code = data.get('code')
    
    src = f"staging/{year}/{code}"
    dst = f"live/{year}/{code}"
    
    if not storage.exists(f"{src}/schema.json"):
        return jsonify({"error": "Not found"}), 404
        
    storage.move(src, dst)
    return jsonify({"message": "Approved"})

@main_bp.route('/api/reject_paper', methods=['POST'])
def reject_paper():
    storage = current_app.storage
    if not verify_request_pin(request): return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    year = data.get('year')
    code = data.get('code')
    
    src = f"staging/{year}/{code}"
    
    # storage.delete removes files/folders
    # We should delete the folder
    storage.delete(src)
    return jsonify({"message": "Rejected"})

@main_bp.route('/api/live_papers', methods=['GET'])
def live_papers():
    storage = current_app.storage
    papers = []
    
    years = storage.list("live")
    for year in years:
        codes = storage.list(f"live/{year}")
        for code in codes:
            papers.append({"year": year, "code": code})
            
    papers.sort(key=lambda x: (x['year'], x['code']), reverse=True)
    return jsonify(papers)

@main_bp.route('/api/delete_live_paper', methods=['POST'])
def delete_live_paper():
    storage = current_app.storage
    if not verify_request_pin(request): return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    year = data.get('year')
    code = data.get('code')
    
    target = f"live/{year}/{code}"
    try:
        storage.delete(target)
        return jsonify({"message": f"Deleted {code} ({year}) from Live."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
