# OnlineCinemaAPI

**OnlineCinemaAPI** is a RESTful API for an online cinema, built with FastAPI, which allows users to browse movies, add them to their favorites, register and log in, and also perform administrative actions.

## Technologies

- **FastAPI** – for building fast and efficient APIs.
- **SQLAlchemy** – ORM for working with the database.
- **PostgreSQL** – relational database.
- **Alembic** – for database migrations.
- **Celery** – for background tasks, such as sending emails.
- **Docker** – for containerizing the application.
- **Poetry** – for dependency management.
- **JWT (JSON Web Tokens)** – for user authentication.

## Description

This project implements an online cinema with the following features:

- **User registration and authentication** via JWT.
- **Browse movies** and add them to the favorites list.
- **Administrative features** for adding, editing, and deleting movies.
- **Background tasks** for sending email confirmations to users.

## Installation

### Step 1: Clone the repository

```bash
git clone https://github.com/kuinorymes/OnlineCinemaAPI.git
cd OnlineCinemaAPI
```
### Step 2: Build and Start Docker Containers

To build the Docker images and start the containers, use the following command:

```bash
docker-compose up --build
```
This will start the application along with the database and other necessary services.

### Migrations are running automatically thanks to migrator service in Docker container

Project documentation will be available on **localhost:8000/docs**

### Step 3: Stopping Docker Containers
To stop the containers:

```bash
docker-compose down
```
# Endpoints overview
## User Registration API Endpoint

- **URL**: `/registration/`
- **Method**: `POST`
- **Response Model**: `UserRegistrationResponseSchema`
- **Status Code**: `201 Created` (on success)
- **Purpose**: Registers a new user, assigns them to the `USER` group, generates an activation token, and sends an activation email.

### Request Body
The request body should conform to the `UserRegistrationRequestSchema`. It typically includes:

- `email` (string): The user's email address.
- `password` (string): The user's password.

### Example
```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```
## User Activation API Endpoint
- **URL**: `/registration/{activation_token}/`
- **Method**: `GET`
- **Response Model**: `UserActivation`
- **Status Code**: `200 OK (on success)`
- **Purpose**: `Activates a user account using the provided activation token.`
### Request
- **Path Parameter**: activation_token (string): The activation token sent to the user's email.
### Response
- **Success Response**: Returns a UserActivation object with a message indicating successful activation.

## Resend Activation Email API Endpoint
- **URL**: /registration/resend-email/
- **Method**: POST
- **Response Model**: UserActivation
- **Status Code**: 200 OK (on success)
- **Purpose**: Resends the activation email to a user if their account is not yet activated.
### Request Body
The request body should conform to the UserResendActivationEmail schema, which typically includes:

```json
{
  "email": "user@example.com"
}
```
## User Login API Endpoint

- **URL**: `/login/`
- **Method**: `POST`
- **Response Model**: `UserLoginResponseSchema`
- **Status Code**: `200 OK` (on success)
- **Purpose**: Logs in a user by verifying their email and password. If the credentials are valid, an access token and refresh token are returned.

### Request Body

The request body should conform to the `UserLoginRequestSchema`, which typically includes:

```json
{
  "email": "user@example.com",
  "password": "your_password"
}
```
### Response
```json
{
  "access_token": "jwt_access_token",
  "refresh_token": "jwt_refresh_token"
}
```
## User Logout API Endpoint

- **URL**: `/logout/`
- **Method**: `POST`
- **Response Model**: None (returns a success message)
- **Status Code**: `200 OK` (on success)
- **Purpose**: Logs out the user by deleting their refresh token from the database.

### Request Body

This endpoint does not require a request body.

### Response

- **Status**: `200 OK`
- **Body**:

  ```json
  {
    "message": "You have been successfully logged out."
  }
## Refresh Access Token API Endpoint

- **URL**: `/refresh/`
- **Method**: `POST`
- **Response Model**: `RefreshTokenResponseSchema`
- **Status Code**: `200 OK` (on success)
- **Purpose**: Refreshes the access token using a valid refresh token.

### Request Body

The request body should conform to the `RefreshTokenRequestSchema`, which typically includes:

```json
{
  "refresh_token": "jwt_refresh_token"
}
```
### Response
```json
{
  "access_token": "jwt_access_token"
}

```
## Reset Password API Endpoint

- **URL**: `/reset-password/`
- **Method**: `POST`
- **Response Model**: None (returns a success message)
- **Status Code**: `200 OK` (on success)
- **Purpose**: Initiates the password reset process by sending a reset link to the user's email if their account exists and is active.

### Request Body

The request body should conform to the `ResetPasswordRequestSchema`, which typically includes:

```json
{
  "email": "user@example.com"
}
```
### Response
```json
{
  "message": "If you're registered you will receive an email."
}
```
## Reset Password Check Token API Endpoint

- **URL**: `/reset-password/{token}/`
- **Method**: `GET`
- **Response Model**: `ResetPasswordResponseSchema`
- **Status Code**: `200 OK` (on success)
- **Purpose**: Verifies if the provided reset token is valid, not expired, and associated with an active user.

### Path Parameters

- **token** (string): The password reset token provided by the user.

### Response
```json
{
"valid": true
}
```
## Reset Password Complete API Endpoint

- **URL**: `/reset-password/{token}/`
- **Method**: `POST`
- **Response Model**: None (returns a success message)
- **Status Code**: `200 OK` (on success)
- **Purpose**: Completes the password reset process by allowing the user to set a new password using a valid reset token.

### Path Parameters

- **token** (string): The password reset token provided by the user.

### Request Body

The request body should conform to the `ResetPasswordCompleteRequestSchema`, which typically includes:

```json
{
  "new_password": "new_secure_password"
}
```
## Get User Profile API Endpoint

- **URL**: `/my-profile/`
- **Method**: `GET`
- **Response Model**: `UserProfileResponseSchema`
- **Status Code**: `200 OK` (on success)
- **Purpose**: Retrieves the user's profile information, including their avatar, first name, last name, gender, date of birth, and additional information.

### Response

```json
{
"first_name": "John",
"last_name": "Doe",
"gender": "Male",
"date_of_birth": "1990-01-01",
"info": "Some additional info",
"avatar": "https://example.com/avatar.jpg"
}
```
## Create User Profile API Endpoint

- **URL**: `/create-profile/`
- **Method**: `POST`
- **Response Model**: `ProfileCreateResponseSchema`
- **Status Code**: `201 Created` (on success)
- **Purpose**: Allows the user to create a new profile with their personal details and avatar.

### Request Body

The request body should conform to the `ProfileCreateRequestSchema`, which includes:

```json
{
  "first_name": "John",
  "last_name": "Doe",
  "gender": "Male",
  "date_of_birth": "1990-01-01",
  "info": "Some additional info",
  "avatar": "<file>"
}
```
## Movie endpoints

## Get All Genres API Endpoint

- **URL**: `/api/v1/theater/movies/genres/`
- **Method**: `GET`
- **Response Model**: `Array of GenreListResponseSchema`
- **Status Code**: `200 OK (on success)`
- **Purpose**: `Returns a list of all movie genres available in the system.`

## Get Genre With Related Movies API Endpoint

- **URL**: `/api/v1/theater/movies/genres/{genre_id}/`
- **Method**: `GET`
- **Response Model**: `GenreDetailResponseSchema`
- **Status Code**: `200 OK` (on success), `422 Unprocessable Entity` (validation error)
- **Purpose**: Retrieves details of a specific genre and its related movies.

### Path Parameters
- `genre_id` *(integer)*: The ID of the genre to retrieve.


## Get List of Movies API Endpoint

- **URL**: `/api/v1/theater/movies/`
- **Method**: `GET`
- **Response Model**: `MovieListResponseSchema`
- **Status Code**: `200 OK` (on success), `404 Not Found` (no movies), `422 Unprocessable Entity` (validation error)
- **Purpose**: Returns a paginated list of movies with filtering, sorting, and search options.

### Query Parameters
- `page` *(integer, optional)*: Page number *(default: 1, minimum: 1)*.
- `per_page` *(integer, optional)*: Items per page *(default: 10, maximum: 20, minimum: 1)*.
- `search` *(string, optional)*: Search movie title.
- `year` *(integer, optional)*: Release year.
- `genre` *(string, optional)*: Filter by genre.
- `sort_by` *(string, optional)*: Field to sort by *(default: "id")*.
- `order` *(string, optional)*: Sort order *('asc' or 'desc', default: "desc")*.

## Create a New Movie API Endpoint

- **URL**: `/api/v1/theater/movies/`
- **Method**: `POST`
- **Response Model**: `MovieDetailSchema`
- **Status Code**: `201 Created` (on success), `400 Bad Request` (invalid input), `422 Unprocessable Entity` (validation error)
- **Purpose**: Allows authorized users to add a new movie to the database with details such as name, date, genres, actors, and languages.

### Request Body
- Conforms to `MovieCreateSchema`.

### Security
- Requires `OAuth2PasswordBearer` authentication.

## Get Movie Detail API Endpoint

- **URL**: `/api/v1/theater/movies/{movie_id}/`
- **Method**: `GET`
- **Response Model**: `MovieDetailSchema`
- **Status Code**: `200 OK` (on success), `404 Not Found` (movie not found), `422 Unprocessable Entity` (validation error)
- **Purpose**: Fetches detailed information about a specific movie by its unique ID.

### Path Parameters
- `movie_id` *(integer)*: The ID of the movie to retrieve.

## Delete Movie API Endpoint

- **URL**: `/api/v1/theater/movies/{movie_id}/`
- **Method**: `DELETE`
- **Response Model**: `None`
- **Status Code**: `204 No Content` (on success), `404 Not Found` (movie not found), `422 Unprocessable Entity` (validation error)
- **Purpose**: Deletes a specific movie from the database by its unique ID.

### Path Parameters
- `movie_id` *(integer)*: The ID of the movie to delete.

### Security
- Requires `OAuth2PasswordBearer` authentication.

## Update Movie API Endpoint

- **URL**: `/api/v1/theater/movies/{movie_id}/`
- **Method**: `PATCH`
- **Response Model**: `None`
- **Status Code**: `200 OK` (on success), `404 Not Found` (movie not found), `422 Unprocessable Entity` (validation error)
- **Purpose**: Updates details of a specific movie by its unique ID.

### Path Parameters
- `movie_id` *(integer)*: The ID of the movie to update.

### Request Body
- Conforms to `MovieUpdateSchema`.

### Security
- Requires `OAuth2PasswordBearer` authentication.

## Add Comment to a Movie API Endpoint

- **URL**: `/api/v1/theater/movies/{movie_id}/comments/`
- **Method**: `POST`
- **Response Model**: `MovieCommentDetailSchema`
- **Status Code**: `201 Created` (on success), `404 Not Found` (movie not found), `422 Unprocessable Entity` (validation error)
- **Purpose**: Allows users to add a comment to a specific movie.

### Path Parameters
- `movie_id` *(integer)*: The ID of the movie to comment on.

### Request Body
- Conforms to `MovieCommentBaseSchema`.

### Security
- Requires `OAuth2PasswordBearer` authentication.

---

## Remove Comment from a Movie API Endpoint

- **URL**: `/api/v1/theater/movies/{movie_id}/comments/{comment_id}/`
- **Method**: `DELETE`
- **Response Model**: `None`
- **Status Code**: `204 No Content` (on success), `404 Not Found` (movie or comment not found), `403 Forbidden` (not the author), `422 Unprocessable Entity` (validation error)
- **Purpose**: Allows users to remove their own comment from a specific movie.

### Path Parameters
- `movie_id` *(integer)*: The ID of the movie.
- `comment_id` *(integer)*: The ID of the comment to remove.

### Security
- Requires `OAuth2PasswordBearer` authentication.

---

## Like/Dislike a Movie API Endpoint

- **URL**: `/api/v1/theater/movies/{movie_id}/votes/`
- **Method**: `POST`
- **Response Model**: `None`
- **Status Code**: `200 OK` (on success), `404 Not Found` (movie not found), `422 Unprocessable Entity` (validation error)
- **Purpose**: Allows users to like or dislike a specific movie.

### Path Parameters
- `movie_id` *(integer)*: The ID of the movie to vote on.

### Request Body
- Conforms to `VoteSchema`.

### Security
- Requires `OAuth2PasswordBearer` authentication.

## Remove Vote from a Movie API Endpoint

- **URL**: `/api/v1/theater/movies/{movie_id}/votes/`
- **Method**: `DELETE`
- **Response Model**: `None`
- **Status Code**: `204 No Content` (on success), `404 Not Found` (movie or vote not found), `200 OK` (vote updated), `422 Unprocessable Entity` (validation error)
- **Purpose**: Allows users to remove their vote from a specific movie.

### Path Parameters
- `movie_id` *(integer)*: The ID of the movie.

### Security
- Requires `OAuth2PasswordBearer` authentication.

---

## Get Favorite Movies API Endpoint

- **URL**: `/api/v1/theater/movies/favorites`
- **Method**: `GET`
- **Response Model**: `MovieListResponseSchema`
- **Status Code**: `200 OK` (on success), `404 Not Found` (no favorites), `422 Unprocessable Entity` (validation error)
- **Purpose**: Retrieves a paginated list of the authenticated user's favorite movies.

### Query Parameters
- `page` *(integer, optional)*: Page number (default: 1, minimum: 1).
- `per_page` *(integer, optional)*: Items per page (default: 10, maximum: 20, minimum: 1).
- `search` *(string, optional)*: Search movie title.
- `year` *(integer, optional)*: Release year.
- `genre` *(string, optional)*: Filter by genre.
- `sort_by` *(string, optional)*: Field to sort by (default: "id").
- `order` *(string, optional)*: Sort order ('asc' or 'desc', default: "desc").

### Security
- Requires `OAuth2PasswordBearer` authentication.

---

## Add Movie to Favorites API Endpoint

- **URL**: `/api/v1/theater/movies/{movie_id}/favorites/`
- **Method**: `POST`
- **Response Model**: `None`
- **Status Code**: `200 OK` (on success), `404 Not Found` (movie not found), `422 Unprocessable Entity` (validation error)
- **Purpose**: Adds a specific movie to the authenticated user's favorites list.

### Path Parameters
- `movie_id` *(integer)*: The ID of the movie to add.

### Security
- Requires `OAuth2PasswordBearer` authentication.

---

## Remove Movie from Favorites API Endpoint

- **URL**: `/api/v1/theater/movies/{movie_id}/favorites/`
- **Method**: `DELETE`
- **Response Model**: `None`
- **Status Code**: `204 No Content` (on success), `404 Not Found` (movie not found or not in favorites), `422 Unprocessable Entity` (validation error)
- **Purpose**: Removes a specific movie from the authenticated user's favorites list.

### Path Parameters
- `movie_id` *(integer)*: The ID of the movie to remove.

### Security
- Requires `OAuth2PasswordBearer` authentication.

## Shopping Cart endpoints:

## Admin View User Cart API Endpoint

- **URL**: `/api/v1/carts/admin/users/{user_id}/cart`
- **Method**: `GET`
- **Response Model**: `Object`
- **Status Code**: `200 OK` (on success), `422 Unprocessable Entity` (validation error)
- **Purpose**: Allows an admin to view a specific user's cart.

### Path Parameters
- `user_id` *(integer)*: The ID of the user whose cart to view.

### Security
- Requires `OAuth2PasswordBearer` authentication.

---

## Add Item to Cart API Endpoint

- **URL**: `/api/v1/carts/cart/items`
- **Method**: `POST`
- **Response Model**: `None`
- **Status Code**: `201 Created` (on success), `422 Unprocessable Entity` (validation error)
- **Purpose**: Adds a movie to the authenticated user's cart.

### Query Parameters
- `movie_id` *(integer)*: The ID of the movie to add.

### Security
- Requires `OAuth2PasswordBearer` authentication.

---

## Remove Item from Cart API Endpoint

- **URL**: `/api/v1/carts/cart/items/{item_id}`
- **Method**: `DELETE`
- **Response Model**: `Object`
- **Status Code**: `200 OK` (on success), `422 Unprocessable Entity` (validation error)
- **Purpose**: Removes a specific item from the authenticated user's cart.

### Path Parameters
- `item_id` *(integer)*: The ID of the item to remove.

### Security
- Requires `OAuth2PasswordBearer` authentication.

---

## View Cart API Endpoint

- **URL**: `/api/v1/carts/cart`
- **Method**: `GET`
- **Response Model**: `Object`
- **Status Code**: `200 OK` (on success)
- **Purpose**: Retrieves the current contents of the authenticated user's cart.

### Security
- Requires `OAuth2PasswordBearer` authentication.

---

## Clear Cart API Endpoint

- **URL**: `/api/v1/carts/cart`
- **Method**: `DELETE`
- **Response Model**: `Object`
- **Status Code**: `200 OK` (on success)
- **Purpose**: Clears all items from the authenticated user's cart.

### Security
- Requires `OAuth2PasswordBearer` authentication.

## Order Endpoints:

## Get User Orders API Endpoint

- **URL**: `/api/v1/orders/`
- **Method**: `GET`
- **Response Model**: `OrderListResponseSchema`
- **Status Code**: `200 OK` (on success)
- **Purpose**: Retrieves a list of orders associated with the authenticated user.

### Security
- Requires `OAuth2PasswordBearer` authentication.

---

## Create Order API Endpoint

- **URL**: `/api/v1/orders/`
- **Method**: `POST`
- **Response Model**: `OrderResponseSchema`
- **Status Code**: `201 Created` (on success), `422 Unprocessable Entity` (validation error)
- **Purpose**: Creates a new order for the authenticated user.

### Request Body:
```
{
  "items": [
    {
      "movie_id": <integer>
    }
  ]
}
```

### Security
- Requires `OAuth2PasswordBearer` authentication.

## Get Order By ID API Endpoint

- **URL**: `/api/v1/orders/{order_id}`
- **Method**: `GET`
- **Response Model**: `OrderResponseSchema`
- **Status Code**: `200 OK` (on success), `422 Unprocessable Entity` (validation error)
- **Purpose**: Retrieves details of a specific order by its ID.

### Path Parameters
- `order_id` (integer): The ID of the order to retrieve.

### Security
- Requires `OAuth2PasswordBearer` authentication.

---

## Cancel Order API Endpoint

- **URL**: `/api/v1/orders/{order_id}`
- **Method**: `DELETE`
- **Response Model**: None
- **Status Code**: `204 No Content` (on success), `422 Unprocessable Entity` (validation error)
- **Purpose**: Cancels a specific order by its ID.

### Path Parameters
- `order_id` (integer): The ID of the order to cancel.

### Security
- Requires `OAuth2PasswordBearer` authentication.

## Payment Endpoints:

## Create Payment API Endpoint

- **URL**: `/api/v1/payments/create_payment`
- **Method**: `POST`
- **Response Model**: `PaymentResponse`
- **Status Code**: `201 Created` (on success), `422 Unprocessable Entity` (validation error)
- **Purpose**: Creates a new payment session for the specified order.

### Request Body
```
{
  "order_id": 1
}
```
### Security
- Requires `OAuth2PasswordBearer` authentication.

## Payment Success API Endpoint

- **URL**: `/api/v1/payments/{order_id}/success`
- **Method**: `GET`
- **Response Model**: `PaymentSuccessResponse`
- **Status Code**: `200 OK` (on success), `422 Unprocessable Entity` (validation error)
- **Purpose**: Handles the callback for a successful payment (no authentication required).

### Path Parameters
- **order_id** (integer): The ID of the order.

### Query Parameters
- **session_id** (string): The payment session ID.

---

## Payment Cancel API Endpoint

- **URL**: `/api/v1/payments/{order_id}/cancel`
- **Method**: `GET`
- **Response Model**: `PaymentCancelResponse`
- **Status Code**: `200 OK` (on success), `422 Unprocessable Entity` (validation error)
- **Purpose**: Handles the callback for a canceled payment (no authentication required).

### Path Parameters
- **order_id** (integer): The ID of the order.

### Query Parameters
- **session_id** (string): The payment session ID.

---

## Get Payments API Endpoint

- **URL**: `/api/v1/payments/`
- **Method**: `GET`
- **Response Model**: `PaymentListResponse`
- **Status Code**: `200 OK` (on success), `422 Unprocessable Entity` (validation error)
- **Purpose**: Retrieves a paginated list of the authenticated user's payments.

### Query Parameters
- **page** (integer, optional): Page number (default: 1, minimum: 1).
- **per_page** (integer, optional): Items per page (default: 10, maximum: 100, minimum: 1).

### Security
- Requires `OAuth2PasswordBearer` authentication.

---

## Get Payment Details API Endpoint

- **URL**: `/api/v1/payments/{payment_id}`
- **Method**: `GET`
- **Response Model**: `PaymentDetailResponse`
- **Status Code**: `200 OK` (on success), `422 Unprocessable Entity` (validation error)
- **Purpose**: Retrieves details of a specific payment.

### Path Parameters
- **payment_id** (integer): The ID of the payment.

### Security
- Requires `OAuth2PasswordBearer` authentication.

## Stripe Webhook API Endpoint

- **URL**: `/api/v1/payments/webhook`
- **Method**: `POST`
- **Response Model**: `None`
- **Status Code**: `200 OK` (on success)
- **Purpose**: Handles Stripe webhook events for payment processing.

# 🔥The Backend Boys Team🔥
- [Bohdan Havryliuk](https://github.com/bogdAAAn1)
- [Danylo Trukhanov](https://github.com/DanilTrukhanov)
- [Arsenii Aristov](https://github.com/Bleit1)
- [Yehor Ripa](https://github.com/10kkyvl)
- [Arsen Myroniuk](https://github.com/kuinorymes/)
