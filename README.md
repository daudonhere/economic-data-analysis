<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:00DB25,100:58BF69&height=200&section=header&animation=fadeIn" />
</p>

<h2 align="center">Economy & Finance Trend Analytics</h2>

<p align="center" style="width: 60%; max-width: 400px; margin: 0 auto;">
  This application serves to analyze trend data related to economics and finance. This application helps users to understand patterns and movements in economic and financial data for better decision-making.
</p>

---

## 🚀 Installation and Running the Project

Here are the steps to install and run this project in your local environment:

1.  **Activate Virtual Environment (venv)**

    Ensure you have a virtual environment installed. If not, you can create one with the following command (for Python 3):
    ```bash
    python -m venv venv
    ```
    Activate the virtual environment:
    * For Windows:
        ```bash
        .\venv\Scripts\activate
        ```
    * For macOS/Linux:
        ```bash
        source venv/bin/activate
        ```

2.  **Install Requirements**

    After the virtual environment is active, install all the necessary dependencies listed in the `requirements.txt` file:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Environment Variables**

    Create a `.env` file in the root directory of your project. Copy the content below into this `.env` file and fill in the values according to your configuration:
    ```env
    DB_USER=xxxx
    DB_PASSWORD=xxxx
    DB_HOST=xxxx
    DB_PORT=xxxx
    DB_NAME=xxxx
    FMP_API_KEY=xxxx
    FMP_BASE_URL=xxxx
    ALPHA_API_KEY=xxxx
    ALPHA_BASE_URL=xxxx
    DJANGO_SECRET_KEY=xxxx
    ```
    * `DB_USER`: Your database username.
    * `DB_PASSWORD`: Your database password.
    * `DB_HOST`: Your database host (e.g., `localhost` or IP address).
    * `DB_PORT`: Your database port (e.g., `5432` for PostgreSQL).
    * `DB_NAME`: Your database name.
    * `FMP_API_KEY`: Your API Key for the Financial Modeling Prep service.
    * `FMP_BASE_URL`: The base URL for the Financial Modeling Prep API.
    * `ALPHA_API_KEY`: Your API Key for the Alpha Vantage service.
    * `ALPHA_BASE_URL`: The base URL for the Alpha Vantage API.
    * `DJANGO_SECRET_KEY`: The secret key for your Django application (ensure this is unique and secure).

4.  **Migrate Database Models**

    Run the migration commands to create the database schema based on your Django models:
    ```bash
    python manage.py makemigrations
    python manage.py migrate
    ```

5.  **Run Django Server**

    After all the above steps are completed, run the Django development server:
    ```bash
    python manage.py runserver
    ```
    The application will run by default at `http://localhost:8000` or `http://127.0.0.1:8000`. Open this address in your browser to see the application.

6.  **Notes**

    In development or local mode you can set the code:
    ```bash
    DEBUG = False
    ALLOWED_HOSTS = []
    ```
    In app configs/settings.py for debugging

---

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:00DB25,100:58BF69&height=160&section=footer"/>
</p>
