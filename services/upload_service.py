import os
import uuid
from fastapi import UploadFile
from typing import Dict, Any, Optional
import database

UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

async def save_pdf_report(file: UploadFile) -> Dict[str, Any]:
    """Saves uploaded PDF report to uploads/ directory and stores metadata in SQLite."""
    report_id = str(uuid.uuid4())
    filename = file.filename or f"report_{report_id[:8]}.pdf"
    
    # Secure target filepath
    safe_filename = f"{report_id}_{filename.replace(' ', '_')}"
    file_path = os.path.join(UPLOADS_DIR, safe_filename)
    
    content = await file.read()
    file_size = len(content)
    
    with open(file_path, "wb") as f:
        f.write(content)
        
    database.save_report_meta(report_id, filename, file_path, file_size)
    
    return {
        "id": report_id,
        "filename": filename,
        "file_path": file_path,
        "file_size_bytes": file_size,
        "status": "stored",
        "message": "PDF financial report uploaded and index metadata stored successfully."
    }

async def save_dataset_reference(dataset_url: Optional[str] = None, file: Optional[UploadFile] = None) -> Dict[str, Any]:
    """Stores a dataset URL reference or uploads a dataset file."""
    dataset_id = str(uuid.uuid4())
    
    if file:
        filename = file.filename or f"dataset_{dataset_id[:8]}.csv"
        file_path = os.path.join(UPLOADS_DIR, f"{dataset_id}_{filename}")
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        database.save_dataset_meta(dataset_id, filename, is_file=True, file_path=file_path)
        return {
            "id": dataset_id,
            "type": "file",
            "name": filename,
            "file_path": file_path,
            "status": "linked",
            "message": "Dataset file uploaded and referenced."
        }
    elif dataset_url:
        database.save_dataset_meta(dataset_id, dataset_url, is_file=False)
        return {
            "id": dataset_id,
            "type": "url",
            "url": dataset_url,
            "status": "linked",
            "message": "External dataset URL linked successfully."
        }
    else:
        raise ValueError("Either dataset_url or file must be provided.")
