"""Owned committed-file selectors; filesystem paths are never wire selectors."""
from pydantic import Field
from .base import ContractModel
from .plan_operations import PlanLookupControl, PlanPageQuery


class PlanArtifactFilesQuery(PlanPageQuery):
    artifact_id: str = Field(min_length=1, max_length=200, pattern=r'^[A-Za-z0-9_.:-]+$')
    after: str = Field(default='', max_length=64, pattern=r'^[a-f0-9]*$')


class PlanArtifactFileQuery(ContractModel):
    artifact_id: str = Field(min_length=1, max_length=200, pattern=r'^[A-Za-z0-9_.:-]+$')
    file_id: str = Field(pattern=r'^[a-f0-9]{64}$')


class PlanArtifactPreviewQuery(PlanArtifactFileQuery):
    max_bytes: int = Field(default=16384, ge=1, le=65536)
    max_rows: int = Field(default=100, ge=1, le=1000)


class PlanArtifactFilesControl(PlanLookupControl, PlanArtifactFilesQuery):
    pass


class PlanArtifactFileControl(PlanLookupControl, PlanArtifactFileQuery):
    pass


class PlanArtifactPreviewControl(PlanLookupControl, PlanArtifactPreviewQuery):
    pass
