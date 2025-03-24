from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import select, func

from schemas import MovieListResponseSchema, MovieListItemSchema
from database import get_db, MovieModel
from schemas.movies import MovieDetailSchema

router = APIRouter()


@router.get(
    "/movies/",
    response_model=MovieListResponseSchema,
    summary="Get a list of movies",
    description=(
        "<h3>This endpoint retrieves a paginated list of movies from the database. "
        "Clients can specify the `page` number and the number of items per page using `per_page`. "
        "The response includes details about the movies, total pages, and total items, "
        "along with links to the previous and next pages if applicable.</h3>"
    ),
    responses={
        404: {
            "description": "No movies found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "No movies found",
                    }
                }
            }
        }
    }
)
async def get_movie_list(
    page: int = Query(1, ge=1, description="The page number"),
    per_page: int = Query(10, ge=1, le=20, description="The number of items per page"),
    db: AsyncSession = Depends(get_db),
) -> MovieListResponseSchema:
    offset = (page - 1) * per_page
    
    count_stmt = select(func.count(MovieModel.id))
    result_count = await db.execute(count_stmt)
    total_items = result_count.scalar() or 0
    
    if not total_items:
        raise HTTPException(status_code=404, detail="No movies found")
    
    order_by = MovieModel.default_order_by()
    stmt = select(MovieModel)
    if order_by:
        stmt = stmt.order_by(*order_by)
    
    stmt = stmt.offset(offset).limit(per_page)
    
    result_movies = await db.execute(stmt)
    movies = result_movies.scalars().all()
    
    if not movies:
        raise HTTPException(status_code=404, detail="No movies found")
    
    movie_list = [MovieListItemSchema.model_validate(movie) for movie in movies]
    
    total_pages = (total_items + per_page - 1) // per_page
    
    response = MovieListResponseSchema(
        movies=movie_list,
        prev_page=f"/movies/?page={page-1}&per_page={per_page}" if page > 1 else None,
        next_page=f"/movies/?page={page+1}&per_page={per_page}" if page < total_pages else None,
        total_pages=total_pages,
        total_items=total_items,
    )
    return response

@router.get(
    "/movies/{movie_id}/",
    response_model=MovieDetailSchema,
    summary="Get a movie detail",
    description=(
            "<h3>Fetch detailed information about a specific movie by its unique ID. "
            "This endpoint retrieves all available details for the movie, such as "
            "its name, genre, crew, budget, and revenue. If the movie with the given "
            "ID is not found, a 404 error will be returned.</h3>"
    ),
    responses={
        404: {
            "description": "Movie not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Movie with given id not found",
                    }
                }
            }
        }
    }
)
async def get_movie_by_id(
        movie_id: int,
        db: AsyncSession = Depends(get_db)
) -> MovieDetailSchema:
    stmt = (
        select(MovieModel)
        .options(
            joinedload(MovieModel.genres),
            joinedload(MovieModel.stars),
            joinedload(MovieModel.directors),
            joinedload(MovieModel.certification)
        )
        .where(MovieModel.id == movie_id)
    )

    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    return MovieDetailSchema.model_validate(movie)
