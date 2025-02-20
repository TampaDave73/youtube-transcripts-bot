def get_all_docs_from_folder(folder_id):
    """Retrieve all Google Docs from a specific Google Drive folder."""
    try:
        print(f"INFO: Fetching all documents from folder: {folder_id}")

        # Query all files in the folder, not just Google Docs
        query = f"'{folder_id}' in parents"
        results = drive_service.files().list(q=query, fields="files(id, name, mimeType)").execute()
        files = results.get("files", [])

        if not files:
            print("WARNING: No files found in the specified folder.")
            return {"message": "No files found in this folder."}

        print(f"INFO: Found {len(files)} files in the folder.")
        for file in files:
            print(f"DEBUG: File Found - Name: {file['name']}, Type: {file['mimeType']}")

        # Filter only Google Docs (remove PDFs, Sheets, etc.)
        google_docs = [f for f in files if f["mimeType"] == "application/vnd.google-apps.document"]

        if not google_docs:
            print("WARNING: No Google Docs found in the folder.")
            return {"message": "No Google Docs found in this folder."}

        docs_data = []
        for file in google_docs:
            doc_id = file["id"]
            doc_name = file["name"]
            doc_content = get_google_doc_content(doc_id)
            docs_data.append({
                "document_id": doc_id,
                "document_name": doc_name,
                "content": doc_content
            })

        print(f"INFO: Returning {len(docs_data)} Google Docs.")
        return docs_data

    except Exception as e:
        print(f"ERROR: Failed to retrieve documents from folder: {str(e)}")
        return {"error": f"Failed to retrieve documents from folder: {str(e)}"}
