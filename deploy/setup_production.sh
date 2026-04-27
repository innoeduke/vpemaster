#!/bin/bash

# setup_production.sh
# Automates the deployment of VPEMaster on macOS, Ubuntu, and OpenCloudOS.

set -e

# --- Configuration ---
PROJECT_ROOT=$(pwd)
SERVICE_USER="vpemaster"
DEPLOYER_USER="deployer"
SHARED_GROUP="vpemaster-web"
WORKERS=4
SERVER_NAME="moleqode.com" # Updated to your domain

echo "🚀 Starting VPEMaster Deployment Setup..."
echo "📍 Project Root: $PROJECT_ROOT"

# --- OS Detection ---
OS_TYPE="unknown"
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS_TYPE="macos"
elif [ -f /etc/os-release ]; then
    . /etc/os-release
    if [[ "$ID" == "ubuntu" ]]; then
        OS_TYPE="ubuntu"
    elif [[ "$ID" == "opencloudos" ]]; then
        OS_TYPE="opencloudos"
    fi
fi

echo "🖥️  Detected OS: $OS_TYPE"

if [ "$OS_TYPE" == "unknown" ]; then
    echo "❌ Unsupported OS. Manual setup required."
    exit 1
fi

# --- User and Group Creation ---
echo "👤 Setting up users and groups..."

if [ "$OS_TYPE" == "macos" ]; then
    # macOS user creation is complex; we'll check if they exist or use current user for simplicity if not root
    # For a production-like setup on macOS, we'll assume the current user is the deployer.
    echo "ℹ️  On macOS, skipping automated user creation. Using current user: $(whoami)"
    SERVICE_USER=$(whoami)
    DEPLOYER_USER=$(whoami)
    SHARED_GROUP="staff"
else
    # Linux (Ubuntu/OpenCloudOS)
    # Create shared group
    if ! getent group $SHARED_GROUP > /dev/null; then
        sudo groupadd $SHARED_GROUP
    fi

    # Create service user
    if ! id -u $SERVICE_USER > /dev/null 2>&1; then
        sudo useradd -r -s /bin/false -g $SHARED_GROUP $SERVICE_USER
        echo "✅ Created service user: $SERVICE_USER"
    fi

    # Create deployer user
    if ! id -u $DEPLOYER_USER > /dev/null 2>&1; then
        sudo useradd -m -s /bin/bash -g $SHARED_GROUP $DEPLOYER_USER
        echo "✅ Created deployer user: $DEPLOYER_USER"
    fi

    # Add Nginx to the shared group
    NGINX_USER="www-data"
    if [ "$OS_TYPE" == "opencloudos" ]; then NGINX_USER="nginx"; fi
    if getent passwd $NGINX_USER > /dev/null; then
        sudo usermod -a -G $SHARED_GROUP $NGINX_USER
        echo "✅ Added $NGINX_USER to $SHARED_GROUP"
    fi

    # Add current user to the shared group (for manual testing like 'flask run')
    CURRENT_USER=$(whoami)
    if [ "$CURRENT_USER" != "root" ]; then
        sudo usermod -a -G $SHARED_GROUP $CURRENT_USER
        echo "✅ Added $CURRENT_USER to $SHARED_GROUP"
    fi
fi

# --- Permission Management ---
echo "🔐 Configuring permissions (Least Privilege)..."

# 1. Set ownership: deployer owns the code, shared group for access
sudo chown -R $DEPLOYER_USER:$SHARED_GROUP "$PROJECT_ROOT"

# 2. Default permissions: Directories 755, Files 644 (excluding venv)
sudo find "$PROJECT_ROOT" -type d -not -path "*/venv/*" -exec chmod 755 {} +
sudo find "$PROJECT_ROOT" -type f -not -path "*/venv/*" -exec chmod 644 {} +

# 2b. Ensure venv binaries are executable
if [ -d "$PROJECT_ROOT/venv/bin" ]; then
    sudo chmod +x "$PROJECT_ROOT/venv/bin/"*
fi

# 3. Restrict sensitive files (.env, private keys)
if [ -f "$PROJECT_ROOT/.env" ]; then
    sudo chmod 640 "$PROJECT_ROOT/.env"
    sudo chown $DEPLOYER_USER:$SHARED_GROUP "$PROJECT_ROOT/.env"
fi

# 4. Writable directories for the service user
mkdir -p "$PROJECT_ROOT/instance" "$PROJECT_ROOT/logs"
sudo chown -R $SERVICE_USER:$SHARED_GROUP "$PROJECT_ROOT/instance" "$PROJECT_ROOT/logs"
sudo chmod -R 770 "$PROJECT_ROOT/instance" "$PROJECT_ROOT/logs"

# 5. Ensure Gunicorn socket directory is accessible (if applicable)
# The socket will be created in PROJECT_ROOT, so SHARED_GROUP needs execute on PROJECT_ROOT
sudo chmod 755 "$PROJECT_ROOT"

# --- Service File Generation ---
echo "⚙️  Generating service configuration..."
if [ "$OS_TYPE" == "macos" ]; then
    PLIST_DEST="$HOME/Library/LaunchAgents/com.vpemaster.app.plist"
    sed -e "s|{{PROJECT_ROOT}}|$PROJECT_ROOT|g" \
        -e "s|{{WORKERS}}|$WORKERS|g" \
        deploy/com.vpemaster.app.plist.template > "$PLIST_DEST"
    echo "✅ Generated macOS plist: $PLIST_DEST"
    launchctl load "$PLIST_DEST" || echo "⚠️  Could not load plist (maybe already loaded?)"
else
    SERVICE_DEST="/etc/systemd/system/vpemaster.service"
    sudo sed -e "s|{{PROJECT_ROOT}}|$PROJECT_ROOT|g" \
             -e "s|{{SERVICE_USER}}|$SERVICE_USER|g" \
             -e "s|{{SHARED_GROUP}}|$SHARED_GROUP|g" \
             -e "s|{{WORKERS}}|$WORKERS|g" \
             deploy/vpemaster.service.template | sudo tee "$SERVICE_DEST" > /dev/null
    
    echo "✅ Generated systemd service: $SERVICE_DEST"
    sudo systemctl daemon-reload
    sudo systemctl enable vpemaster
    sudo systemctl start vpemaster
fi

# --- Nginx Configuration ---
echo "🌐 Configuring Nginx..."
NGINX_CONF_DIR=""
if [ "$OS_TYPE" == "ubuntu" ]; then
    NGINX_CONF_DIR="/etc/nginx/sites-enabled"
elif [ "$OS_TYPE" == "opencloudos" ]; then
    NGINX_CONF_DIR="/etc/nginx/conf.d"
elif [ "$OS_TYPE" == "macos" ]; then
    NGINX_CONF_DIR="/usr/local/etc/nginx/servers"
    mkdir -p "$NGINX_CONF_DIR"
fi

if [ -n "$NGINX_CONF_DIR" ]; then
    NGINX_DEST="$NGINX_CONF_DIR/vpemaster.conf"
    sudo sed -e "s|{{PROJECT_ROOT}}|$PROJECT_ROOT|g" \
             -e "s|{{SERVER_NAME}}|$SERVER_NAME|g" \
             deploy/vpemaster.nginx.template | sudo tee "$NGINX_DEST" > /dev/null
    
    echo "✅ Generated Nginx config: $NGINX_DEST"
    if command -v nginx > /dev/null; then
        sudo nginx -t && sudo nginx -s reload || echo "⚠️  Nginx reload failed. Check config."
    fi
fi

echo "✨ Deployment setup complete!"

# --- SSL Setup ---
if [ "$SERVER_NAME" != "_" ]; then
    echo "🔒 Checking for SSL certificates in /etc/nginx/..."
    CERT_FILE="/etc/nginx/${SERVER_NAME}_bundle.crt"
    KEY_FILE="/etc/nginx/${SERVER_NAME}.key"

    if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
        echo "✅ SSL Certificates found: $CERT_FILE and $KEY_FILE"
        echo "🛡️  Ensuring correct permissions for certificates..."
        sudo chmod 600 "$KEY_FILE"
        sudo chmod 644 "$CERT_FILE"
    else
        echo "⚠️  SSL Certificates NOT found at $CERT_FILE or $KEY_FILE"
        echo "🔒 Would you like to set up SSL with Certbot instead? (y/n)"
        read -r setup_ssl
        if [[ "$setup_ssl" =~ ^([yY][eE][sS]|[yY])$ ]]; then
            echo "📥 Installing Certbot..."
            if [ "$OS_TYPE" == "ubuntu" ]; then
                sudo apt update && sudo apt install -y certbot python3-certbot-nginx
            elif [ "$OS_TYPE" == "opencloudos" ]; then
                sudo dnf install -y certbot python3-certbot-nginx
            elif [ "$OS_TYPE" == "macos" ]; then
                brew install certbot
            fi

            echo "🛡️  Running Certbot for $SERVER_NAME..."
            if [ "$OS_TYPE" == "macos" ]; then
                sudo certbot certonly --nginx -d "$SERVER_NAME"
            else
                sudo certbot --nginx -d "$SERVER_NAME"
            fi
            echo "✅ SSL setup complete with Certbot!"
        else
            echo "💡 Please upload your certificates to /etc/nginx/ as:"
            echo "   - $CERT_FILE"
            echo "   - $KEY_FILE"
            echo "   Then run 'sudo nginx -t && sudo nginx -s reload'"
        fi
    fi
fi

echo "📝 Note: You may need to update 'SERVER_NAME' in $NGINX_DEST and run 'sudo nginx -s reload'."
