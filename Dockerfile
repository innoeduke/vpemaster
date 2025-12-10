# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container at /app
COPY . .

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define environment variables
ENV FLASK_APP=run.py
# Note: You can add other environment variables like FLASK_ENV=production here

# Run the application using Gunicorn
# bind to 0.0.0.0 to allow external connections
# run:app refers to the 'app' object in the 'run.py' file
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "run:app"]
