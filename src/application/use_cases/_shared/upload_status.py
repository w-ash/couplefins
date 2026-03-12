from collections import Counter
import uuid

from attrs import define

from src.domain.entities.person import Person
from src.domain.entities.upload import Upload


@define(frozen=True, slots=True)
class UploadStatus:
    person_id: uuid.UUID
    person_name: str
    has_uploaded: bool
    upload_count: int


def build_upload_statuses(
    persons: list[Person], uploads: list[Upload]
) -> list[UploadStatus]:
    upload_counts = Counter(u.person_id for u in uploads)
    return [
        UploadStatus(
            person_id=p.id,
            person_name=p.name,
            has_uploaded=upload_counts[p.id] > 0,
            upload_count=upload_counts[p.id],
        )
        for p in persons
    ]
