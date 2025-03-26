from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import exists, delete, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.movies import CommentModel, MovieVoteModel, MoviesFavoritesModel
from database.models.orders import OrderItemModel
from database.models.users import UserModel

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
from schemas.movies import MovieCommentBaseSchema, MovieCommentDetailSchema, VoteSchema

from services import user_staff
from routes.users import get_current_user  # noqa: F811


router = APIRouter()


@router.get(
    "/movies/",
    response_model=MovieListResponseSchema,
    summary="Get list of movies",
    description=(
        "Returns a list of movies with pagination, filtering, sorting, and search. "
        "Parameters: page, per_page, search, year, genre, sort_by, order."
    ),
    responses={
        404: {
            "description": "No movies found",
            "content": {"application/json": {"example": {"detail": "No movies found"}}},
        }
    },
)
async def get_movie_list(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=20, description="Items per page"),
    search: Optional[str] = Query(None, description="Search movie title"),
    year: Optional[int] = Query(None, description="Release year"),
    genre: Optional[str] = Query(None, description="Filter by genre"),
    sort_by: Optional[str] = Query("id", description="Field to sort by"),
    order: Optional[str] = Query("desc", description="Sort order: 'asc' or 'desc'"),
    db: AsyncSession = Depends(get_db),
) -> MovieListResponseSchema:
    if order not in ("asc", "desc"):
        raise HTTPException(
            status_code=400, detail="Invalid order value. Must be 'asc' or 'desc'."
        )
    if not hasattr(MovieModel, sort_by):
        raise HTTPException(status_code=400, detail=f"Invalid sort_by field: {sort_by}")

    offset = (page - 1) * per_page
    count_stmt = select(func.count(MovieModel.id))
    stmt = select(MovieModel)

    if search:
        stmt = stmt.where(MovieModel.name.ilike(f"%{search}%"))
        count_stmt = count_stmt.where(MovieModel.name.ilike(f"%{search}%"))
    if year:
        stmt = stmt.where(MovieModel.year == year)
        count_stmt = count_stmt.where(MovieModel.year == year)
    if genre:
        stmt = stmt.where(MovieModel.genres.any(GenreModel.name.ilike(f"%{genre}%")))
        count_stmt = count_stmt.where(
            MovieModel.genres.any(GenreModel.name.ilike(f"%{genre}%"))
        )

    result_count = await db.execute(count_stmt)
    total_items = result_count.scalar() or 0
    if total_items == 0:
        raise HTTPException(status_code=404, detail="No movies found")

    order_column = getattr(MovieModel, sort_by)
    stmt = stmt.order_by(order_column.desc() if order == "desc" else order_column.asc())
    stmt = stmt.offset(offset).limit(per_page)
    result_movies = await db.execute(stmt)
    movies = result_movies.scalars().all()
    if not movies:
        raise HTTPException(status_code=404, detail="No movies found")

    movie_list = [MovieListItemSchema.model_validate(movie) for movie in movies]
    total_pages = (total_items + per_page - 1) // per_page

    response = MovieListResponseSchema(
        movies=movie_list,
        prev_page=(
            (
                f"/movies/?page={page-1}&per_page={per_page}"
                f"&search={search or ''}&year={year or ''}&genre={genre or ''}&sort_by={sort_by}&order={order}"
            )
            if page > 1
            else None
        ),
        next_page=(
            (
                f"/movies/?page={page+1}&per_page={per_page}"
                f"&search={search or ''}&year={year or ''}&genre={genre or ''}&sort_by={sort_by}&order={order}"
            )
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
            votes_imdb=movie_data.votes_imdb,
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
        await db.refresh(
            movie, ["genres", "directors", "certification", "stars", "comments"]
        )

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


@router.post(
    "/movies/{movie_id}/votes/",
    dependencies=[Depends(get_current_user)],
    summary="Like/Dislike a movie by ID",
    description="<h3>Vote for a movie either like or dislike</h3>",
    responses={
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with the given ID was not found."}
                }
            },
        },
        200: {
            "description": "Movie vote updated",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie vote updated successfully."}
                }
            },
        },
    },
)
async def vote_movie(
    movie_id: int,
    vote: VoteSchema,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    movies_stmt = select(MovieModel).where(MovieModel.id == movie_id)
    result = await db.execute(movies_stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    vote_stmt = select(MovieVoteModel).where(
        MovieVoteModel.movie_id == movie_id,
        MovieVoteModel.user_id == user.id,
    )
    result = await db.execute(vote_stmt)
    user_vote = result.scalars().first()

    if user_vote:
        user_vote.is_like = vote.is_like
    else:
        user_vote = MovieVoteModel(
            movie_id=movie_id,
            user_id=user.id,
            is_like=vote.is_like,
        )
        db.add(user_vote)

    await db.commit()
    return {"detail": "Vote updated successfully"}


@router.delete(
    "/movies/{movie_id}/votes/",
    dependencies=[Depends(get_current_user)],
    summary="Remove your vote from a movie by ID",
    description=("<h3>Remove your vote from a movie by ID.</h3>"),
    responses={
        404: {
            "description": (
                "Not Found. Either the movie with the given ID was not found "
                "or the vote was not found."
            ),
            "content": {
                "application/json": {
                    "examples": {
                        "movieNotFound": {
                            "summary": "Movie Not Found",
                            "value": {
                                "detail": "Movie with the given ID was not found."
                            },
                        },
                        "voteNotFound": {
                            "summary": "Vote Not Found",
                            "value": {"detail": "Vote for the movie was not found."},
                        },
                    }
                }
            },
        },
        200: {
            "description": "Movie vote updated",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie vote updated successfully."}
                }
            },
        },
    },
)
async def delete_vote(
    movie_id: int,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(MovieVoteModel).where(
        MovieVoteModel.movie_id == movie_id,
        MovieVoteModel.user_id == user.id,
    )
    result = await db.execute(stmt)
    voted = result.scalars().first()

    if not voted:
        raise HTTPException(status_code=404, detail="Vote didnt found")

    await db.delete(voted)
    await db.commit()

    return {"detail": "Movie vote deleted successfully"}


@router.get(
    "/movies/favorites",
    dependencies=[Depends(get_current_user)],
    summary="Get your favorite movies",
    response_model=MovieListResponseSchema,
    responses={
        404: {
            "description": "Movies not found",
            "content": {
                "application/json": {
                    "example": {"detail": "You dont have your favorite movies"}
                }
            },
        }
    },
)
async def get_favorites(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=20, description="Items per page"),
    search: Optional[str] = Query(None, description="Search movie title"),
    year: Optional[int] = Query(None, description="Release year"),
    genre: Optional[str] = Query(None, description="Filter by genre"),
    sort_by: Optional[str] = Query("id", description="Field to sort by"),
    order: Optional[str] = Query("desc", description="Sort order: 'asc' or 'desc'"),
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MovieListResponseSchema:
    if order not in ("asc", "desc"):
        raise HTTPException(
            status_code=400, detail="Invalid order value. Must be 'asc' or 'desc'."
        )
    if not hasattr(MovieModel, sort_by):
        raise HTTPException(status_code=400, detail=f"Invalid sort_by field: {sort_by}")

    offset = (page - 1) * per_page

    count_stmt = (
        select(func.count())
        .select_from(MovieModel)
        .join(MoviesFavoritesModel, MoviesFavoritesModel.c.movie_id == MovieModel.id)
        .where(MoviesFavoritesModel.c.user_id == user.id)
    )

    stmt = (
        select(MovieModel)
        .join(MoviesFavoritesModel, MoviesFavoritesModel.c.movie_id == MovieModel.id)
        .where(MoviesFavoritesModel.c.user_id == user.id)
    )

    if search:
        stmt = stmt.where(MovieModel.name.ilike(f"%{search}%"))
        count_stmt = count_stmt.where(MovieModel.name.ilike(f"%{search}%"))
    if year:
        stmt = stmt.where(MovieModel.year == year)
        count_stmt = count_stmt.where(MovieModel.year == year)
    if genre:
        stmt = stmt.where(MovieModel.genres.any(GenreModel.name.ilike(f"%{genre}%")))
        count_stmt = count_stmt.where(
            MovieModel.genres.any(GenreModel.name.ilike(f"%{genre}%"))
        )

    result_count = await db.execute(count_stmt)
    total_items = result_count.scalar() or 0
    if total_items == 0:
        raise HTTPException(status_code=404, detail="No favorite movies found")

    order_column = getattr(MovieModel, sort_by)
    stmt = stmt.order_by(order_column.desc() if order == "desc" else order_column.asc())
    stmt = stmt.offset(offset).limit(per_page)
    result_movies = await db.execute(stmt)
    movies = result_movies.scalars().all()
    if not movies:
        raise HTTPException(status_code=404, detail="No favorite movies found")

    movie_list = [MovieListItemSchema.model_validate(movie) for movie in movies]
    total_pages = (total_items + per_page - 1) // per_page

    response = MovieListResponseSchema(
        movies=movie_list,
        prev_page=(
            (
                f"/favorites/?page={page-1}&per_page={per_page}"
                f"&search={search or ''}&year={year or ''}&genre={genre or ''}&sort_by={sort_by}&order={order}"
            )
            if page > 1
            else None
        ),
        next_page=(
            (
                f"/favorites/?page={page+1}&per_page={per_page}"
                f"&search={search or ''}&year={year or ''}&genre={genre or ''}&sort_by={sort_by}&order={order}"
            )
            if page < total_pages
            else None
        ),
        total_pages=total_pages,
        total_items=total_items,
    )
    return response


@router.post(
    "/movies/{movie_id}/favorites/",
    dependencies=[Depends(get_current_user)],
    summary="Add your favorite movie to your favorite list",
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
)
async def add_to_favorites(
    movie_id: int,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_stmt = (
        select(UserModel)
        .where(UserModel.id == user.id)
        .options(joinedload(UserModel.favorite_movies))
    )
    user_result = await db.execute(user_stmt)
    user = user_result.scalars().first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    movie_stmt = select(MovieModel).where(MovieModel.id == movie_id)
    result = await db.execute(movie_stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    check_stmt = select(MoviesFavoritesModel).where(
        MoviesFavoritesModel.c.user_id == user.id,
        MoviesFavoritesModel.c.movie_id == movie_id,
    )
    existing_favorite = await db.execute(check_stmt)

    if existing_favorite.first():
        raise HTTPException(status_code=400, detail="Movie already favorited")

    user.favorite_movies.append(movie)
    await db.commit()

    return {"detail": "Movie favorited successfully"}


@router.delete(
    "/movies/{movie_id}/favorites/",
    dependencies=[Depends(get_current_user)],
    summary="Remove movie from your favorite list",
    responses={
        404: {
            "description": "Movie not found or not in favorites.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Movie with the given ID was not found or not favorited."
                    }
                }
            },
        }
    },
)
async def remove_from_favorites(
    movie_id: int,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    movie_stmt = select(MovieModel).where(MovieModel.id == movie_id)
    result = await db.execute(movie_stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    favorites_stmt = select(MoviesFavoritesModel).where(
        MoviesFavoritesModel.c.movie_id == movie_id,
        MoviesFavoritesModel.c.user_id == user.id,
    )
    favorite_record = await db.execute(favorites_stmt)
    favorite = favorite_record.scalars().first()

    if not favorite:
        raise HTTPException(status_code=404, detail="Movie not favorited")

    # Удаляем запись из избранного
    delete_stmt = delete(MoviesFavoritesModel).where(
        MoviesFavoritesModel.c.movie_id == movie_id,
        MoviesFavoritesModel.c.user_id == user.id,
    )
    await db.execute(delete_stmt)
    await db.commit()

    return {"detail": "Movie removed from favorites successfully"}
