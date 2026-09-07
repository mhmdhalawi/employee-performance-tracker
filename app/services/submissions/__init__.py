from app.services.submissions.dashboard import get_aggregated_dashboard
from app.services.submissions.json_ingestion import analyze_and_store_tables
from app.services.submissions.upload_ingestion import analyze_and_store_upload

__all__ = [
    "analyze_and_store_tables",
    "analyze_and_store_upload",
    "get_aggregated_dashboard",
]

