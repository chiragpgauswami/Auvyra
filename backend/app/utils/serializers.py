from bson import ObjectId
from datetime import datetime
from typing import Any, Dict, List, Optional

def serialize_doc(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Convert MongoDB document with ObjectId and datetime into JSON-safe dictionary with 'id'."""
    if doc is None:
        return None
    
    res: Dict[str, Any] = {}
    for k, v in doc.items():
        if k == "_id":
            res["id"] = str(v)
        elif isinstance(v, ObjectId):
            res[k] = str(v)
        elif isinstance(v, datetime):
            res[k] = v.isoformat()
        elif isinstance(v, dict):
            res[k] = serialize_doc(v)
        elif isinstance(v, list):
            res[k] = [
                serialize_doc(item) if isinstance(item, dict)
                else str(item) if isinstance(item, ObjectId)
                else item.isoformat() if isinstance(item, datetime)
                else item
                for item in v
            ]
        else:
            res[k] = v
    return res

def serialize_docs(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert a list of MongoDB documents into JSON-safe dictionaries."""
    return [serialize_doc(doc) for doc in docs if doc is not None]

