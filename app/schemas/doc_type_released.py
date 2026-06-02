from pydantic import BaseModel, Field


class YearSummaryResponse(BaseModel):
    year: str = Field(..., description="Release year e.g. '2024'")
    total: int = Field(..., description="Total documents released this year")
    by_doc_type: dict[str, int] = Field(
        ...,
        description="Count per doc type e.g. {'CPR': 2147, 'LOD': 1119}"
    )
    rate: float = Field(..., description="CPR / total * 100")


class DocTypeReleasedResponse(BaseModel):
    doc_types: list[str] = Field(
        ...,
        description="All unique doc types for dynamic columns"
    )
    data: list[YearSummaryResponse]