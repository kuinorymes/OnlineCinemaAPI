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
### Step 1: Build and Start Docker Containers

To build the Docker images and start the containers, use the following command:

```bash
docker-compose up --build
```
This will start the application along with the database and other necessary services.
### Step 2: Running Migrations in Docker
If you're using Docker, you can apply the migrations inside the Docker container by running the following command:

```bash
docker-compose exec cinema_backend poetry run alembic revision --autogenerate "first_commit"
docker-compose exec cinema_backend poetry run alembic upgrade head
```
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

