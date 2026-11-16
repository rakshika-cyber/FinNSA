from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Dict, Any, Optional
from services.upload_service import save_pdf_report, save_dataset_reference

router = APIRouter(prefix="/upload", tags=["File & Dataset Uploads"])

@router.post("/report", response_model=Dict[str, Any])
async def upload_pdf_report(file: UploadFile = File(...)):
    """
    Accepts a financial PDF report file, saves it to disk, records metadata in SQLite,
    and returns a unique report ID.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files (.pdf) are accepted for financial reports.")

    try:
        result = await save_pdf_report(file)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF upload: {str(e)}")

@router.post("/dataset", response_model=Dict[str, Any])
async def upload_dataset(
    dataset_url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    """
    Accepts a dataset URL or uploaded dataset file (CSV/Parquet/JSON),
    stores reference, and returns a dataset reference ID.
    """
    if not dataset_url and not file:
        raise HTTPException(status_code=400, detail="Please provide either a dataset_url or upload a dataset file.")

    try:
        result = await save_dataset_reference(dataset_url=dataset_url, file=file)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process dataset reference: {str(e)}")
