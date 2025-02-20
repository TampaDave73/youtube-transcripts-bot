import os
import json
from flask import Flask, request, jsonify, Response
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__)

# Load credentials from environment variable
SERVICE_ACCOUNT_INFO = os.getenv("SERVICE_ACCOUNT_JSON")

if not SERVICE_ACCOUNT_INFO:
    raise ValueError("Missing Google Service Account JSON in environment variables")

credentials = service_account.Credentials.from_service_account_info(json.loads(SERVICE_ACCOUNT_INFO), scopes=[
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents"
])

# Initialize Google APIs
drive_service = build("drive", "v3", credentials=credentials)
docs_service = build("docs", "v1", credentials=credentials)

def get_google_doc_content(doc_id):
    """Retrieve the content of a Google Doc."""
    try:
        doc = docs_service.documents().get(documentId=doc_id).execute()
        content = "\n".join([element["paragraph"]["elements"][0]["textRun"]["content"]
                             for element in doc.get("body", {}).get("content", [])
                             if "paragraph" in element and "elements" in element["paragraph"]])
        return content
    except Exception as e:
        print(f"ERROR: Retrieving document {doc_id} failed: {str(e)}")
        return f"Error retrieving document {doc_id}: {str(e)}"

def get_all_docs_from_folder(folder_id):
    """Retrieve all Google Docs from a specific Google Drive folder."""
    try:
        print(f"INFO: Fetching all documents from folder: {folder_id}")
        query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.document'"
        results = drive_service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get("files", [])

        if not files:
            print("WARNING: No Google Docs found in the specified folder.")
            return {"message": "No Google Docs found in this folder."}

        docs_data = []
        for file in files:
            doc_id = file["id"]
            doc_name = file["name"]
            doc_content = get_google_doc_content(doc_id)
            docs_data.append({
                "document_id": doc_id,
                "document_name": doc_name,
                "content": doc_content
            })

        print(f"INFO: Returning {len(docs_data)} documents.")
        return docs_data

    except Exception as e:
        print(f"ERROR: Failed to retrieve documents from folder: {str(e)}")
        return {"error": f"Failed to retrieve documents from folder: {str(e)}"}

@app.route("/fetch_transcripts", methods=["GET"])
def fetch_transcripts():
    """API endpoint to get all Google Docs from a folder for CustomGPT."""
    folder_id = request.args.get("folder_id")

    # **Explicit Debugging Logs**
    print(f"DEBUG: Received request for folder ID: {folder_id}")

    if not folder_id:
        print("ERROR: Missing folder ID in request.")
        return Response(json.dumps({"error": "Missing folder ID"}), mimetype="application/json"), 400

    docs = get_all_docs_from_folder(folder_id)

    # **Log response count**
    print(f"DEBUG: Returning {len(docs)} transcripts.")

    return Response(json.dumps(docs), mimetype="application/json")

@app.route("/")
def home():
    return "CustomGPT YouTube Transcripts API is running!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
