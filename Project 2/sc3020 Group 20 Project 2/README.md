# SC3020 Project 2

## Pre-Requisite
Assume you have PostgreSQL setuped with data being properly inserted.

## Run Guide
1. Check your .env file, Change the parameters to your own PostgreSQL configuration
    - DB_HOST = postgres
    - DB_PORT = 5432
    - DB_NAME = postgres
    - DB_USER = postgres
    - DB_PASSWORD = 1234

2. Setup a virtual environment to install the python pre-requisite modules
    ```bash
    python -m venv venv
    ```
    Changing the environment to the virtual environment by running
    ```bash
    venv\Scripts\Activate
    ```
    Followed by installing from requirements.txt
    ```bash
    pip install -r requirements.txt
    ```

3. Ensure that the 4 files (annotation.py, interface.py, project.py, preprocessing.py) are in the same directory
4. Run the following command to start the interface
    ```bash
    python project.py
    ```

## User Guide
- Press Connect DB to connect to the database
- Click on Annotate Query to display the explanation on the Annotated output and QEP
- Click on Cost Chart to see the cost comparison
- Can drag around the QEP canvas and also zoom in/out via the button interface
- History button opens up history logs to view past queries and restore them