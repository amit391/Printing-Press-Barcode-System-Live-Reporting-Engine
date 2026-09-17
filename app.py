# -*- coding: utf-8 -*-
import os
import csv
import datetime
import barcode
from barcode.writer import SVGWriter
from flask import Flask, render_template, request, jsonify, send_from_directory

app = Flask(__name__)

# --- FIX: RELATIVE PATHING FOR RENDER PERSISTENT DISKS ---
IS_RENDER = "RENDER" in os.environ
# Use "data" instead of "/app/data" to bypass container root permission locks
BASE_DATA_DIR = "data" if IS_RENDER else "."

BARCODE_DIR = os.path.join(BASE_DATA_DIR, "barcodes")
EXPORT_DIR = os.path.join(BASE_DATA_DIR, "exports")
LOG_FILE = os.path.join(BASE_DATA_DIR, "production_scan_logs.csv")

# Safely create storage folders inside the accessible working directory context
os.makedirs(BARCODE_DIR, exist_ok=True)
os.makedirs(EXPORT_DIR, exist_ok=True)

# ==============================================================================
# CORE ENGINE FUNCTIONS
# ==============================================================================

def generate_vector_barcode(symbology, data):
    symbology_clean = symbology.upper().replace("-", "")
    if symbology_clean not in ["CODE128", "EAN13"]:
        raise ValueError("Unsupported symbology. Use 'CODE128' or 'EAN13'.")
    
    options = {
        'module_width': 0.3,
        'module_height': 15.0,
        'quiet_zone': 6.5,
        'write_text': True,
        'font_size': 10
    }
    
    barcode_class = barcode.get_barcode_class(symbology_clean)
    file_prefix = os.path.join(BARCODE_DIR, "barcode")
    output_filename = f"{file_prefix}_{symbology_clean.lower()}"
    
    with open(f"{output_filename}.svg", "wb") as f:
        barcode_class(data, writer=SVGWriter()).write(f, options=options)
        
    return f"barcode_{symbology_clean.lower()}.svg"

def log_scan_event(barcode_data, operator_id, session_id):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_exists = os.path.isfile(LOG_FILE)
    
    with open(LOG_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Session_ID", "Operator_ID", "Barcode_Data", "Status"])
        writer.writerow([timestamp, session_id, operator_id, barcode_data, "VERIFIED"])

def read_scan_logs():
    if not os.path.isfile(LOG_FILE):
        return []
    with open(LOG_FILE, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)[::-1]  # Newest records first

def export_session_to_excel():
    try:
        import pandas as pd
    except ImportError:
        return None

    if not os.path.isfile(LOG_FILE):
        return None

    df = pd.read_csv(LOG_FILE)
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_filename = os.path.join(EXPORT_DIR, f"Supervisor_Report_{timestamp_str}.xlsx")

    with pd.ExcelWriter(excel_filename, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="All_Sessions_Master", index=False)
        
        unique_sessions = df["Session_ID"].dropna().unique()
        for session in unique_sessions:
            session_df = df[df["Session_ID"] == session]
            safe_tab_name = f"Session_{str(session)[:20]}"
            session_df.to_excel(writer, sheet_name=safe_tab_name, index=False)
            
    return excel_filename

# ==============================================================================
# WEB APP ROUTING PANELS (AUTHENTICATION STRIPPED)
# ==============================================================================

@app.route("/", methods=["GET"])
def dashboard():
    """Main route showing the industrial press live logging UI."""
    logs = read_scan_logs()
    return render_template("dashboard.html", logs=logs)

@app.route("/api/scan", methods=["POST"])
def api_scan():
    """Asynchronous pipeline handling hardware inputs & real-time log returns."""
    data = request.get_json() or {}
    barcode_data = data.get("barcode_data", "").strip()
    operator_id = data.get("operator_id", "").strip()
    session_id = data.get("session_id", "").strip()
    symbology = data.get("symbology", "CODE128")
    generate_svg = data.get("generate_svg", False)

    if not barcode_data or not operator_id or not session_id:
        return jsonify({"success": False, "error": "Missing required fields."}), 400

    if symbology == "EAN13" and (len(barcode_data) != 13 or not barcode_data.isdigit()):
        return jsonify({"success": False, "error": "EAN-13 must be exactly 13 numeric digits."}), 400

    try:
        log_scan_event(barcode_data, operator_id, session_id)
        if generate_svg:
            generate_vector_barcode(symbology, barcode_data)
            
        return jsonify({
            "success": True, 
            "message": "Scan logged successfully.", 
            "logs": read_scan_logs()
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/export", methods=["POST"])
def export_excel():
    """Compiles local CSV states into multi-tab supervisor excel sheets."""
    excel_path = export_session_to_excel()
    if excel_path:
        directory, filename = os.path.split(excel_path)
        return send_from_directory(directory, filename, as_attachment=True)
    return "Export Failed. No data logs found or dependencies missing.", 400

@app.route("/barcodes/<filename>")
def download_barcode(filename):
    """Retrieves plate-ready vector graphics on demand."""
    return send_from_directory(BARCODE_DIR, filename, as_attachment=True)

if __name__ == "__main__":
    # Seed mock entry row if starting completely fresh
    if not os.path.exists(LOG_FILE):
        log_scan_event("JOB-101A-REV3", "OP-042", "SESS-2026-AM")
        generate_vector_barcode("code128", "JOB-101A-REV3")

    # Set host context to listen broadly across production subnets
    app.run(debug=True, host="0.0.0.0", port=5000)
