---
paths:
  - "**/*.py"
  - "**/*.sql"
---
## Database & API conventions

- **Entity-specific primary keys**, never bare `id`:

```sql
sessions.session_id   UUID PRIMARY KEY
leads.lead_id         UUID PRIMARY KEY
messages.message_id   UUID PRIMARY KEY
```

- Field naming: FKs `{referenced_entity}_id` · timestamps `{action}_at` (`created_at`,
  `expires_at`) · booleans `is_{state}` (`is_active`) · counts `{entity}_count` ·
  durations `{property}_{unit}` (`timeout_minutes`).
- Pydantic models mirror database fields exactly — no field-mapping layers; repositories
  derive table/PK names from the entity by convention.
- Stack: FastAPI for APIs · SQLAlchemy or SQLModel for ORM · **PostgreSQL preferred** over
  other SQL engines · **Redis caching whenever SQL is in play**.
- RESTful routes with consistent parameter naming:

```python
router = APIRouter(prefix="/api/v1/leads", tags=["leads"])

@router.get("/{lead_id}")              # GET    /api/v1/leads/{lead_id}
@router.put("/{lead_id}")              # PUT    /api/v1/leads/{lead_id}
@router.delete("/{lead_id}")           # DELETE /api/v1/leads/{lead_id}
@router.get("/{lead_id}/messages")     # sub-resource
```

- API endpoints carry `summary`/`description` and parameter docs — FastAPI's OpenAPI
  output is part of the documentation surface.
