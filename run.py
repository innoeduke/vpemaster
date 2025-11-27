from app import create_app
import logging

# Create the app instance using the factory
app = create_app()

if __name__ == '__main__':
    # Set up logging
    logging.basicConfig(level=logging.DEBUG)
    
    # Set debug=True for development,
    # a production server (like Gunicorn) will run the app directly.
    app.run(debug=True)