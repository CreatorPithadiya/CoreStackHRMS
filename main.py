from app import app  # noqa: F401

# This file is just an entry point for running the application
# All application configuration is in app.py

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
