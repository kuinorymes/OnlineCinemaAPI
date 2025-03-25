from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, UUID4


class GenreSchema(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class StarSchema(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class DirectorSchema(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class CertificationSchema(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class MovieBaseSchema(BaseModel):
    name: str = Field(..., max_length=255)
    year: int = Field(..., ge=0)
    time: int = Field(..., ge=0)
    meta_score: float = Field(..., ge=0, le=100)
    imdb: float = Field(..., ge=0, le=10)
    votes: int = Field(..., ge=0)
    gross: Optional[float] = Field(..., ge=0)
    price: Optional[float] = Field(..., ge=0)
    certification: CertificationSchema
    description: str

    model_config = ConfigDict(from_attributes=True)


class MovieDetailSchema(MovieBaseSchema):
    id: int
    uuid: UUID4
    stars: List[StarSchema]
    directors: List[DirectorSchema]
    genres: List[GenreSchema]

    model_config = ConfigDict(from_attributes=True)


class MovieListItemSchema(BaseModel):
    id: int
    name: str
    year: int
    meta_score: float
    description: str

    model_config = ConfigDict(from_attributes=True)


class MovieListResponseSchema(BaseModel):
    movies: List[MovieListItemSchema]
    prev_page: Optional[str]  # no need for = None cuz we send None if no result anyways
    next_page: Optional[str]
    total_pages: int
    total_items: int

    model_config = ConfigDict(from_attributes=True)


class MovieCreateSchema(BaseModel):
    name: str = Field(..., max_length=255)
    year: int = Field(..., ge=0)
    time: int = Field(..., ge=0)
    meta_score: float = Field(..., ge=0, le=100)
    imdb: float = Field(..., ge=0, le=10)
    votes: int = Field(..., ge=0)
    gross: Optional[float] = Field(..., ge=0)
    price: Optional[float] = Field(..., ge=0)
    certification: str
    description: str
    stars: List[str]
    directors: List[str]
    genres: List[str]

    model_config = ConfigDict(from_attributes=True)


class MovieUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    year: Optional[int] = Field(None, ge=0)
    time: Optional[int] = Field(None, ge=0)
    meta_score: Optional[float] = Field(None, ge=0, le=100)
    imdb: Optional[float] = Field(None, ge=0, le=10)
    description: Optional[str] = Field(None, max_length=255)
    gross: Optional[float] = Field(None, ge=0)
    price: Optional[float] = Field(None, ge=0)
