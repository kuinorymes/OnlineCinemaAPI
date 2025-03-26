from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import exists
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import select, func

from database.models.movies import CommentModel
from database.models.orders import OrderItemModel
from routes.users import get_current_user
from schemas import (
    MovieListResponseSchema,
    MovieListItemSchema,
    MovieDetailSchema,
    MovieCreateSchema,
    MovieUpdateSchema,
)
from database import (
    get_db,
    MovieModel,
    GenreModel,
    StarModel,
    DirectorModel,
    CertificationModel,
)
from schemas.movies import MovieCommentBaseSchema, MovieCommentDetailSchema
from services import user_staff


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
            },
        }
    },
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
        next_page=(
            f"/movies/?page={page+1}&per_page={per_page}"
            if page < total_pages
            else None
        ),
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
            },
        }
    },
)
async def get_movie_by_id(
    movie_id: int, db: AsyncSession = Depends(get_db)
) -> MovieDetailSchema:
    stmt = (
        select(MovieModel)
        .options(
            joinedload(MovieModel.genres),
            joinedload(MovieModel.stars),
            joinedload(MovieModel.directors),
            joinedload(MovieModel.certification),
            joinedload(MovieModel.comments),
        )
        .where(MovieModel.id == movie_id)
    )

    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    return MovieDetailSchema.model_validate(movie)


@router.post(
    "/movies/",
    dependencies=[Depends(user_staff)],
    response_model=MovieDetailSchema,
    summary="Create a new movie",
    description=(
        "<h3>This endpoint allows clients to add a new movie to the database. "
        "It accepts details such as name, date, genres, actors, languages, and "
        "other attributes. The associated country, genres, actors, and languages "
        "will be created or linked automatically.</h3>"
    ),
    responses={
        201: {
            "description": "Movie created successfully",
        },
        400: {
            "description": "Invalid input",
            "content": {
                "application/json": {"example": {"detail": "Invalid input data"}}
            },
        },
    },
    status_code=201,
)
async def create_movie(
    movie_data: MovieCreateSchema, db: AsyncSession = Depends(get_db)
) -> MovieDetailSchema:
    exists_stmt = select(MovieModel).where(
        (MovieModel.name == movie_data.name),
        (MovieModel.year == movie_data.year),
    )
    exists_result = await db.execute(exists_stmt)
    exists_movie = exists_result.scalars().first()

    if exists_movie:
        raise HTTPException(
            status_code=409,
            detail=f"A movie with name {movie_data.name} and year {movie_data.year} already exists",
        )

    try:
        certification_stmt = select(CertificationModel).where(
            CertificationModel.name == movie_data.certification
        )
        certification_result = await db.execute(certification_stmt)
        certification = certification_result.scalars().first()

        if not certification:
            certification = CertificationModel(name=movie_data.certification)
            db.add(certification)
            await db.flush()

        genres = []
        for genre_name in movie_data.genres:
            genre_stmt = select(GenreModel).where(GenreModel.name == genre_name)
            genre_result = await db.execute(genre_stmt)
            genre = genre_result.scalars().first()

            if not genre:
                genre = GenreModel(name=genre_name)
                db.add(genre)
                await db.flush()
            genres.append(genre)

        stars = []
        for star_name in movie_data.stars:
            star_stmt = select(StarModel).where(StarModel.name == star_name)
            star_result = await db.execute(star_stmt)
            star = star_result.scalars().first()

            if not star:
                star = StarModel(name=star_name)
                db.add(star)
                await db.flush()
            stars.append(star)

        directors = []
        for director_name in movie_data.directors:
            director_stmt = select(DirectorModel).where(
                DirectorModel.name == director_name
            )
            director_result = await db.execute(director_stmt)
            director = director_result.scalars().first()

            if not director:
                director = DirectorModel(name=director_name)
                db.add(director)
                await db.flush()
            directors.append(director)

        movie = MovieModel(
            name=movie_data.name,
            year=movie_data.year,
            time=movie_data.time,
            imdb=movie_data.imdb,
            votes=movie_data.votes,
            meta_score=movie_data.meta_score,
            gross=movie_data.gross,
            description=movie_data.description,
            price=movie_data.price,
            genres=genres,
            stars=stars,
            directors=directors,
            certification=certification,
        )
        db.add(movie)
        await db.commit()
        await db.refresh(movie, ["genres", "directors", "certification", "stars"])

        return MovieDetailSchema.model_validate(movie)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data")


@router.delete(
    "/movies/{movie_id}/",
    dependencies=[Depends(user_staff)],
    summary="Delete a movie by ID",
    description=(
        "<h3>Delete a specific movie from the database by its unique ID.</h3>"
        "<p>If the movie exists, it will be deleted. If it does not exist, "
        "a 404 error will be returned.</p>"
    ),
    responses={
        204: {"description": "Movie deleted successfully."},
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with the given ID was not found."}
                }
            },
        },
    },
    status_code=204,
)
async def delete_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(MovieModel).where(MovieModel.id == movie_id)
    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    order_stmt = select(exists().where(OrderItemModel.movie_id == movie_id))
    order_result = await db.execute(order_stmt)
    is_purchased = order_result.scalar()

    if is_purchased:
        raise HTTPException(
            status_code=403,
            detail="You cant delete this movie because someone purchased it",
        )

    await db.delete(movie)
    await db.commit()

    return {"detail": "Movie deleted successfully"}


@router.patch(
    "/movies/{movie_id}/",
    dependencies=[Depends(user_staff)],
    summary="Update a movie by ID",
    description=(
        "<h3>Update details of a specific movie by its unique ID.</h3>"
        "<p>This endpoint updates the details of an existing movie. If the movie with "
        "the given ID does not exist, a 404 error is returned.</p>"
    ),
    responses={
        200: {
            "description": "Movie updated successfully.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie updated successfully."}
                }
            },
        },
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with the given ID was not found."}
                }
            },
        },
    },
)
async def update_movie(
    movie_id: int,
    movie_data: MovieUpdateSchema,
    db: AsyncSession = Depends(get_db),
):

    stmt = select(MovieModel).where(MovieModel.id == movie_id)
    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    for field, value in movie_data.model_dump(exclude_unset=True).items():
        setattr(movie, field, value)

    try:
        await db.commit()
        await db.refresh(movie)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data")

    return {"detail": "Movie updated successfully"}


@router.post(
    "/movies/{movie_id}/comments/",
    dependencies=[Depends(get_current_user)],
    summary="Add comment to a movie",
    description=("<h3>Put your thoughts in the comment section</h3>"),
    responses={
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with the given ID was not found."}
                }
            },
        }
    },
    response_model=MovieCommentDetailSchema,
)
async def add_comment(
    movie_id: int,
    comment: MovieCommentBaseSchema,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MovieCommentDetailSchema:
    stmt = select(MovieModel).where(MovieModel.id == movie_id)
    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    comment = CommentModel(
        content=comment.content,
        movie_id=movie_id,
        user_id=user.id,
    )
    db.add(comment)
    await db.commit()

    return MovieCommentDetailSchema.model_validate(comment)


@router.delete(
    "/movies/{movie_id}/comments/{comment_id}/",
    dependencies=[Depends(get_current_user)],
    summary="Remove a comment from a movie",
    description=("<h3>Remove a comment from a movie.</h3>"),
    responses={
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Movie or Comment with the given ID was not found."
                    }
                }
            },
        },
        403: {
            "description": "You are not the author of this comment.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "You cannot delete a comment you did not create."
                    }
                }
            },
        },
    },
)
async def delete_comment(
    movie_id: int,
    comment_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt_movie = select(MovieModel).where(MovieModel.id == movie_id)
    result_movie = await db.execute(stmt_movie)
    movie = result_movie.scalars().first()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    stmt_comment = select(CommentModel).where(
        CommentModel.id == comment_id, CommentModel.movie_id == movie_id
    )
    result_comment = await db.execute(stmt_comment)
    comment = result_comment.scalars().first()

    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if comment.user_id != user.id:
        raise HTTPException(
            status_code=403, detail="You cannot delete a comment you did not create"
        )

    await db.delete(comment)
    await db.commit()

    return {"detail": "Comment deleted successfully"}
