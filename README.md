# OnlineCinemaAPI

# How to Clone and Run the Project


   1. Run the following command to clone the repository:

   ```
   git clone https://github.com/kuinorymes/OnlineCinemaAPI.git
   ```

   2. Navigate to the project directory
   
   ```
   cd online-cinema-api
   ```
   3. Create virtual environment:
   
   ```
   python -m venv .venv
   source .venv/bin/activate  # for Linux/Mac
   .venv\Scripts\activate  # for Windows
   ```
   
   4. clone the env (there's nothing important there, I don't know why I created it, but I did...)
      ```
      cp .env.sample .env
      ```
   5. Install Poetry & dependencies
   
      ```
      pip install poetry
      poetry install
      ```
      
   6. You could apply DB migrations via Alembic:
      
      ```
      alembic upgrade head
      ```
   7. Check if it works on endpoint http://127.0.0.1:8000/health:

      ```
      uvicorn src.main:app --reload
      ```
      