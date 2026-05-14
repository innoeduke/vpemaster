#!/bin/bash

# Ensure the script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root or with sudo"
  exit
fi

# Configuration - Change these as needed
DB_NAME="vpemaster"
DB_USER="root"
DB_PASS="hondaGL9565!" # Change this!

echo "Installing MySQL Server..."
apt update
apt install -y mysql-server

# Ensure MySQL is running
systemctl start mysql
systemctl enable mysql

echo "Configuring MySQL Security..."

# Check if the database already exists
DB_EXISTS=$(mysql -u root -e "SHOW DATABASES LIKE '$DB_NAME';" | grep "$DB_NAME")

if [ -z "$DB_EXISTS" ]; then
    echo "Creating Database: $DB_NAME"
    mysql -u root -e "CREATE DATABASE IF NOT EXISTS \`$DB_NAME\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    
    echo "Creating User: $DB_USER"
    # We use mysql_native_password for better compatibility with some older Python drivers, 
    # but caching_sha2_password is the default in MySQL 8.0+
    mysql -u root -e "CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASS';"
    
    echo "Granting Privileges..."
    mysql -u root -e "GRANT ALL PRIVILEGES ON \`$DB_NAME\`.* TO '$DB_USER'@'localhost';"
    mysql -u root -e "FLUSH PRIVILEGES;"
    
    echo "Database setup complete."
else
    echo "Database $DB_NAME already exists. Skipping creation."
fi

# Optional: Display current databases to verify
echo "-----------------------------------"
echo "Current MySQL Databases:"
mysql -u root -e "SHOW DATABASES;"
echo "-----------------------------------"

echo "MySQL Installation and Setup finished."
echo "DB Name: $DB_NAME"
echo "DB User: $DB_USER"
