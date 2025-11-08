from app import create_app

# Create the app instance using the factory
app = create_app()

if __name__ == '__main__':
    # Set debug=True for development,
    # a production server (like Gunicorn) will run the app directly.
    app.run(debug=True)