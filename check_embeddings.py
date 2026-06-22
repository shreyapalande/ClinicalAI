from db.database import SessionLocal
from db.models import Visit

db = SessionLocal()
visits = db.query(Visit).all()
for v in visits:
    dims = len(v.embedding) if v.embedding else 0
    status = str(dims) + " dims" if dims else "MISSING"
    print(f"Visit {v.id} | Patient {v.patient_id} | Embedding: {status}")
db.close()
