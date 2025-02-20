import os
import json
from flask import Flask, request, jsonify
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

# Initialize Google Docs API
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
        return f"Error retrieving document: {str(e)}"

@app.route("/read_doc", methods=["GET"])
def read_google_doc():
    """API endpoint to fetch Google Docs content."""
    doc_id = request.args.get("doc_id")
    if not doc_id:
        return jsonify({"error": "Missing document ID"}), 400
    
    content = get_google_doc_content(doc_id)
    return jsonify({"document_id": doc_id, "content": content})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
