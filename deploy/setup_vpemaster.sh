#!/bin/bash

# Ensure the script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root or with sudo"
  exit
fi

echo "Updating system and installing Python, MySQL, and Build dependencies..."
apt update
# Added pkg-config, python3-dev, default-libmysqlclient-dev, and build-essential
apt install -y nginx python3-pip python3-venv git zsh pkg-config python3-dev default-libmysqlclient-dev build-essential

echo "Configuring Nginx..."
# Ensure Nginx starts on boot and is currently running
systemctl enable nginx
systemctl start nginx

echo "Configuring users and groups..."

# 1. Setup groups and users
getent group www-data >/dev/null || groupadd www-data

USERS=("ubuntu" "vpemaster")
for USERNAME in "${USERS[@]}"; do
  if ! id -u "$USERNAME" >/dev/null 2>&1; then
    useradd -m -s /bin/zsh "$USERNAME"
  else
    usermod -s /bin/zsh "$USERNAME"
  fi
  usermod -aG sudo "$USERNAME"
  usermod -aG www-data "$USERNAME"
done

# 2. Setup SSH Key for vpemaster
SSH_DIR="/home/vpemaster/.ssh"
KEY_PATH="$SSH_DIR/id_ed25519"

mkdir -p "$SSH_DIR"
chown vpemaster:vpemaster "$SSH_DIR"
chmod 700 "$SSH_DIR"

if [ ! -f "$KEY_PATH" ]; then
  echo "Generating SSH key..."
  ssh-keygen -t ed25519 -f "$KEY_PATH" -N "" -q
fi

chown vpemaster:vpemaster "$KEY_PATH" "${KEY_PATH}.pub"
chmod 600 "$KEY_PATH"
chmod 644 "${KEY_PATH}.pub"

echo "-----------------------------------------------------------"
echo "PUBLIC KEY (ED25519):"
cat "${KEY_PATH}.pub"
echo "-----------------------------------------------------------"
echo "Add to: https://serverless-100009545409.coding.net/user/account/setting/keys"
echo "-----------------------------------------------------------"
read -p "Press [Enter] once the key is added to CODING..."

# 3. Pre-trust host (Universal Scan)
echo "Scanning e.coding.net host keys..."
ssh-keyscan e.coding.net > "$SSH_DIR/known_hosts"
chown vpemaster:vpemaster "$SSH_DIR/known_hosts"
chmod 600 "$SSH_DIR/known_hosts"

# 4. Prepare directory and Clone
TARGET_DIR="/var/www/vpemaster"
mkdir -p "$TARGET_DIR"
chown vpemaster:www-data "$TARGET_DIR"
chmod 2775 "$TARGET_DIR"

REPO_SSH="git@e.coding.net:serverless-100009545409/toastmasters/vpemaster.git"
git config --global --add safe.directory "$TARGET_DIR"

if [ "$(ls -A $TARGET_DIR)" ]; then
    echo "Directory $TARGET_DIR is not empty. Skipping clone."
else
    echo "Cloning repository..."
    sudo -u vpemaster git clone "$REPO_SSH" "$TARGET_DIR"
    if [ $? -eq 0 ]; then
        sudo -u vpemaster git -C "$TARGET_DIR" config core.sharedRepository group
    else
        echo "Clone failed. Check SSH key."
        exit 1
    fi
fi

# 5. Create Virtual Environment
VENV_PATH="$TARGET_DIR/venv"
if [ ! -d "$VENV_PATH" ]; then
    echo "Creating virtual environment..."
    sudo -u vpemaster python3 -m venv "$VENV_PATH"
fi

# 6. Enforce deep group permissions
echo "Enforcing group write permissions..."
chown -R vpemaster:www-data "$TARGET_DIR"
find "$TARGET_DIR" -type d -exec chmod 2775 {} +
find "$TARGET_DIR" -type f -exec chmod 664 {} +

# 7. Update .zshrc for auto-activation
echo "Updating .zshrc for both users..."
for USERNAME in "${USERS[@]}"; do
  ZSHRC_FILE="/home/$USERNAME/.zshrc"
  touch "$ZSHRC_FILE"
  if ! grep -q "cd /var/www/vpemaster" "$ZSHRC_FILE"; then
    cat <<EOF >> "$ZSHRC_FILE"

# Auto-navigate and activate vpemaster environment
cd /var/www/vpemaster
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi
EOF
    chown "$USERNAME:$USERNAME" "$ZSHRC_FILE"
  fi
done

# 8. Setup ubuntu user SSH identity (Independent copy)
echo "Setting up ubuntu user SSH..."
U_SSH="/home/ubuntu/.ssh"
mkdir -p "$U_SSH"
chown ubuntu:ubuntu "$U_SSH"
chmod 700 "$U_SSH"

cp "$KEY_PATH" "$U_SSH/id_ed25519_vpemaster"
chown ubuntu:ubuntu "$U_SSH/id_ed25519_vpemaster"
chmod 600 "$U_SSH/id_ed25519_vpemaster"

ssh-keyscan e.coding.net > "$U_SSH/known_hosts"
chown ubuntu:ubuntu "$U_SSH/known_hosts"
chmod 600 "$U_SSH/known_hosts"

if [ ! -f "$U_SSH/config" ] || ! grep -q "id_ed25519_vpemaster" "$U_SSH/config"; then
cat <<EOF >> "$U_SSH/config"
Host e.coding.net
    HostName e.coding.net
    User git
    IdentityFile $U_SSH/id_ed25519_vpemaster
EOF
chown ubuntu:ubuntu "$U_SSH/config"
chmod 600 "$U_SSH/config"
fi

sudo -u ubuntu git config --global --add safe.directory "$TARGET_DIR"

echo "Setup complete. Libraries for mysqlclient are installed."
echo "You can now run: pip install -r requirements.txt"
