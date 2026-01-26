#!/bin/bash

# Add new SSH public key to authorized_keys
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# Add the new RSA key
cat >> ~/.ssh/authorized_keys << 'EOF'
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCjs4+1FbhNax8i7m7S0lua8f8mvfGYJHHHVyi1/eOXobludr5sVDlULv/l+cNU2ugqywjXt2WWHb55WxBI8Ys0MDqnLdXh/C4Wl3qWHTrvgmNSm9knabhSqu4DELjx3Loo7SpIN7myA9gqk2zJG2BI7r136HrriV9ZgVjphoVYK7me3XD3okzTgJFOUAY/qZLnPBF6zViNSQ7dAswBO2rrmC4N9r3AFxa17axuBtW+XPNqmRqN8DspObC0QVsGKlZQUI1c79QRhnqEKtZCMCRiAmnBqkWVyzjgbqs65NbqBktr82x2c15i0FCXfqtyEbGsHDa7cG8D6dMCjWFNhKs9 ssh-key-2026-01-26
EOF

# Set proper permissions
chmod 600 ~/.ssh/authorized_keys

# Verify
echo "✅ SSH key added successfully!"
echo "Current authorized_keys:"
cat ~/.ssh/authorized_keys
