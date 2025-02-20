#!/usr/bin/env python3
"""
This Flask app serves transcript data from Google Docs stored in a specific Google Drive folder.
It uses the Google Docs and Drive APIs to extract text from each document.
The app exposes two endpoints:
  • GET /transcripts – Returns a list of all transcript documents.
  • GET /transcript/<doc_id> – Returns the transcript for a specific document.
"""

import os
import json
import logging
from flask import Flask, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# ---------------------------
# Configuration & Credentials
# ---------------------------

# The Google Drive folder ID where your transcript Google Docs are stored.
# For local testing you can set a default value here; in production, set DOCS_FOLDER_ID as an environment variable.
DOCS_FOLDER_ID = os.environ.get("DOCS_FOLDER_ID", "YOUR_DOCS_FOLDER_ID_HERE")

# Google API scopes required to access Docs and Drive.
SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive"
]

# Load service account credentials.
# When deploying on Render, set an environment variable named SERVICE_ACCOUNT_JSON with the full JSON contents.
service_account_json = os.environ.get("SERVICE_ACCOUNT_JSON")
if service_account_json:
    creds = service_account.Credentials.from_service_account_info(
        json.loads(service_account_json), scopes=SCOPES
    )
else:
    # For local testing, ensure a file named "service_account.json" exists in the project folder.
    SERVICE_ACCOUNT_FILE = 'service_account.json'
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )

# Build Google API clients for Docs and Drive.
docs_service = build('docs', 'v1', credentials=creds)
drive_service = build('drive', 'v3', credentials=creds)

# ---------------------------
# Helper Functions
# ---------------------------
def get_text_from_doc(doc_id):
    """
    Retrieves the full text from a Google Doc using the Docs API.
    """
    try:
        doc = docs_service.documents().get(documentId=doc_id).execute()
        content = doc.get('body', {}).get('content', [])
        full_text = ""
        for element in content:
            if 'paragraph' in element:
                elements = element['paragraph'].get('elements', [])
                for elem in elements:
                    if 'textRun' in elem:
                        full_text += elem['textRun'].get('content', '')
        return full_text.strip()
    except Exception as e:
        logging.error(f"Error retrieving document {doc_id}: {e}")
        return None

def list_docs_in_folder(folder_id):
    """
    Lists all Google Docs (file ID and name) in the given Drive folder.
    """
    try:
        # Query to list only Google Docs in the specified folder.
        query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.document'"
        response = drive_service.files().list(q=query, fields="files(id, name)").execute()
        return response.get('files', [])
    except Exception as e:
        logging.error(f"Error listing docs in folder {folder_id}: {e}")
        return []

# ---------------------------
# API Endpoints
# ---------------------------
@app.route('/')
def index():
    return "Transcript API is running."

@app.route('/transcripts', methods=['GET'])
def get_transcripts():
    """
    Returns a JSON list of transcripts from all Google Docs in the designated folder.
    Each transcript includes its document ID, title, and full content.
    """
    docs = list_docs_in_folder(DOCS_FOLDER_ID)
    transcripts = []
    for doc in docs:
        doc_id = doc['id']
        title = doc['name']
        content = get_text_from_doc(doc_id)
        if content:
            transcripts.append({
                "doc_id": doc_id,
                "title": title,
                "content": content
            })
    return jsonify(transcripts)

@app.route('/transcript/<doc_id>', methods=['GET'])
def get_single_transcript(doc_id):
    """
    Returns the transcript of a specific Google Doc identified by doc_id.
    """
    try:
        # Retrieve the document name from Drive.
        file_info = drive_service.files().get(fileId=doc_id, fields="name").execute()
        title = file_info.get('name', 'Unknown')
    except Exception as e:
        logging.error(f"Error retrieving file info for {doc_id}: {e}")
        title = "Unknown"
    content = get_text_from_doc(doc_id)
    if content:
        return jsonify({
            "doc_id": doc_id,
            "title": title,
            "content": content
        })
    else:
        return jsonify({"error": "Transcript not found"}), 404

# ---------------------------
# Main Execution
# ---------------------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
