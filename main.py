#!/usr/bin/env python3
"""
This script reads a Google Sheet for new YouTube URLs, retrieves the video transcript,
title, and channel name, creates a Google Doc for each video, and then marks the URL as processed.
"""

import os
import json
import re
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from pytube import YouTube
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable

# Set up logging for progress and errors
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ---------------------------
# Configuration Constants
# ---------------------------

# Replace with your actual Google Sheet ID
SPREADSHEET_ID = '1KoOcdDRp1vSDaPhOlw9MJxBe44-6vjFcCP3ZJ8qtw8k'
# Replace with your actual sheet name (e.g., "Sheet1")
SHEET_NAME = 'URL'
# Column indices (0-indexed): Column A = URL, Column B = Processed marker
URL_COLUMN_INDEX = 0
PROCESSED_COLUMN_INDEX = 1

# Replace with your Google Drive folder ID where new Docs should be stored.
DOCS_FOLDER_ID = '16ZJiuP2PFNn8qeZ9wgscBP9PGh0j2xfo'

# ---------------------------
# Google API Authentication
# ---------------------------

# Define the scopes required for Sheets, Docs, and Drive
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive"
]

# Try to load credentials from the SERVICE_ACCOUNT_JSON environment variable.
# This is used when running on Render or GitHub Actions.
service_account_json = os.environ.get("SERVICE_ACCOUNT_JSON")
if service_account_json:
    creds = service_account.Credentials.from_service_account_info(
        json.loads(service_account_json), scopes=SCOPES
    )
else:
    # Fallback for local testing: read the JSON file from disk.
    SERVICE_ACCOUNT_FILE = 'service_account.json'
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )

# ---------------------------
# Setup Google API Clients
# ---------------------------

# Build service objects for Sheets, Docs, and Drive
sheets_service = build('sheets', 'v4', credentials=creds)
docs_service = build('docs', 'v1', credentials=creds)
drive_service = build('drive', 'v3', credentials=creds)

# ---------------------------
# Helper Functions
# ---------------------------

def extract_video_id(url):
    """
    Extract the YouTube video ID from a URL.
    Supports typical YouTube URL formats.
    """
    pattern = r"(?:v=|\/)([0-9A-Za-z_-]{11}).*"
    match = re.search(pattern, url)
    if match:
        video_id = match.group(1)
        logging.info(f"Extracted video ID: {video_id}")
        return video_id
    else:
        logging.error(f"Could not extract video ID from URL: {url}")
        return None

def get_video_info(url):
    """
    Use pytube to get video title and channel (author) name.
    """
    try:
        yt = YouTube(url)
        title = yt.title
        channel = yt.author
        logging.info(f"Retrieved video info - Title: {title}, Channel: {channel}")
        return title, channel
    except Exception as e:
        logging.error(f"Error retrieving video info for {url}: {e}")
        return None, None

def get_transcript(video_id):
    """
    Retrieve the transcript text for the given YouTube video ID.
    Combines transcript parts into one string.
    """
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        transcript = "\n".join([item['text'] for item in transcript_list])
        logging.info("Transcript successfully retrieved.")
        return transcript
    except TranscriptsDisabled:
        logging.error("Transcripts are disabled for this video.")
    except NoTranscriptFound:
        logging.error("No transcript found for this video.")
    except VideoUnavailable:
        logging.error("The video is unavailable.")
    except Exception as e:
        logging.error(f"Unexpected error retrieving transcript: {e}")
    return None

def create_google_doc(doc_title, content):
    """
    Create a new Google Doc with the provided title and content.
    Then move the document into the designated folder.
    """
    try:
        # Create a new document with the title
        doc_body = {'title': doc_title}
        doc = docs_service.documents().create(body=doc_body).execute()
        doc_id = doc.get('documentId')
        logging.info(f"Created Google Doc with ID: {doc_id}")

        # Insert the content into the document
        requests = [
            {
                'insertText': {
                    'location': {'index': 1},
                    'text': content
                }
            }
        ]
        docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()
        logging.info("Content inserted into the document.")

        # Move the document into the designated folder
        file = drive_service.files().get(fileId=doc_id, fields='parents').execute()
        previous_parents = ",".join(file.get('parents'))
        drive_service.files().update(
            fileId=doc_id,
            addParents=DOCS_FOLDER_ID,
            removeParents=previous_parents,
            fields='id, parents'
        ).execute()
        logging.info("Document moved to designated Drive folder.")
        return doc_id
    except Exception as e:
        logging.error(f"Error creating or moving Google Doc: {e}")
        return None

def update_sheet_row(row_index, status):
    """
    Update a specific row in the Google Sheet to mark it as processed.
    'row_index' is 0-indexed for our local list; the Sheets API uses 1-indexing including header.
    """
    try:
        cell = f"{chr(ord('A') + PROCESSED_COLUMN_INDEX)}{row_index + 2}"
        body = {"values": [[status]]}
        sheets_service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=cell,
            valueInputOption="RAW",
            body=body
        ).execute()
        logging.info(f"Marked row {row_index + 2} as processed.")
    except Exception as e:
        logging.error(f"Error updating sheet row: {e}")

def process_sheet():
    """
    Main function to process the Google Sheet.
    Reads all rows, checks for unprocessed URLs, processes them, and updates the sheet.
    """
    try:
        range_name = f"{SHEET_NAME}!A:B"
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=range_name
        ).execute()
        values = result.get('values', [])
        if not values or len(values) < 2:
            logging.info("No data found or only header present.")
            return

        header = values[0]
        rows = values[1:]
        logging.info(f"Found {len(rows)} data rows.")

        for index, row in enumerate(rows):
            if len(row) > PROCESSED_COLUMN_INDEX and row[PROCESSED_COLUMN_INDEX].strip():
                logging.info(f"Row {index + 2} already processed; skipping.")
                continue

            url = row[URL_COLUMN_INDEX].strip() if len(row) > URL_COLUMN_INDEX else None
            if not url:
                logging.warning(f"Row {index + 2} does not contain a URL; skipping.")
                continue

            logging.info(f"Processing row {index + 2}: {url}")
            video_id = extract_video_id(url)
            if not video_id:
                update_sheet_row(index, "Error: Invalid URL")
                continue

            title, channel = get_video_info(url)
            if not title or not channel:
                update_sheet_row(index, "Error: Unable to retrieve video info")
                continue

            transcript = get_transcript(video_id)
            if not transcript:
                update_sheet_row(index, "Error: No transcript found")
                continue

            doc_content = f"Title: {title}\nChannel: {channel}\n\nTranscript:\n{transcript}"
            doc_id = create_google_doc(title, doc_content)
            if doc_id:
                update_sheet_row(index, "Processed")
            else:
                update_sheet_row(index, "Error: Doc creation failed")
    except Exception as e:
        logging.error(f"Error processing sheet: {e}")

# ---------------------------
# Main Execution
# ---------------------------

if __name__ == "__main__":
    logging.info("Starting processing of Google Sheet...")
    process_sheet()
    logging.info("Processing complete.")
