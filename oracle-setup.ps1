# PowerShell SSH Helper for Oracle Cloud
# This script helps you SSH into your Oracle instance with your downloaded SSH key

# Configuration - CHANGE THESE:
$ORACLE_INSTANCE_IP = "YOUR_INSTANCE_IP"  # Replace with your Oracle instance IP
$SSH_KEY_PATH = "$HOME\Documents\key\ssh-key-2025-03-28(1).key"  # Path to your SSH key

# Function to fix SSH key permissions
function Fix-SSHKeyPermissions {
    param([string]$KeyPath)
    
    Write-Host "Fixing SSH key permissions..." -ForegroundColor Yellow
    
    # Convert to PuTTY .ppk format if needed
    $puttygen = "C:\Program Files\PuTTY\puttygen.exe"
    
    if (Test-Path $puttygen) {
        Write-Host "PuTTYgen found, converting key format..." -ForegroundColor Green
        & $puttygen $KeyPath -O private-openssh -o -C "" -o $KeyPath
        Write-Host "✓ Key converted successfully" -ForegroundColor Green
    }
}

# Function to connect via SSH
function Connect-Oracle {
    param([string]$IP, [string]$KeyPath)
    
    if (-not (Test-Path $KeyPath)) {
        Write-Host "❌ SSH key not found at: $KeyPath" -ForegroundColor Red
        Write-Host "Please download your SSH key from Oracle Cloud" -ForegroundColor Yellow
        return
    }
    
    Write-Host "Connecting to Oracle instance..." -ForegroundColor Cyan
    Write-Host "IP: $IP" -ForegroundColor White
    Write-Host "Key: $KeyPath" -ForegroundColor White
    echo ""
    
    # Try connection
    ssh -i $KeyPath ubuntu@$IP
}

# Function to upload setup script
function Upload-SetupScript {
    param([string]$IP, [string]$KeyPath)
    
    $scriptPath = ".\setup-oracle-cloud.sh"
    
    if (-not (Test-Path $scriptPath)) {
        Write-Host "❌ Setup script not found: $scriptPath" -ForegroundColor Red
        return
    }
    
    Write-Host "Uploading setup script..." -ForegroundColor Yellow
    scp -i $KeyPath $scriptPath ubuntu@${IP}:/tmp/setup-oracle-cloud.sh
    
    Write-Host "✓ Script uploaded. Now run this on the instance:" -ForegroundColor Green
    Write-Host "  bash /tmp/setup-oracle-cloud.sh" -ForegroundColor Cyan
}

# Main menu
Write-Host "`n"
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ORACLE CLOUD SETUP HELPER" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if ($ORACLE_INSTANCE_IP -eq "YOUR_INSTANCE_IP") {
    Write-Host "❌ ERROR: Replace YOUR_INSTANCE_IP with your actual Oracle instance IP" -ForegroundColor Red
    Write-Host ""
    Write-Host "Steps to find your IP:" -ForegroundColor Yellow
    Write-Host "1. Go to Oracle Cloud Console" -ForegroundColor White
    Write-Host "2. Click 'Compute' → 'Instances'" -ForegroundColor White
    Write-Host "3. Click your instance name" -ForegroundColor White
    Write-Host "4. Copy the 'Public IP Address'" -ForegroundColor White
    Write-Host ""
    Write-Host "Then edit this file and set ORACLE_INSTANCE_IP" -ForegroundColor Cyan
    exit
}

Write-Host "Select an option:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  1) Connect via SSH" -ForegroundColor Cyan
Write-Host "  2) Upload & run setup script" -ForegroundColor Cyan
Write-Host "  3) Fix SSH key permissions" -ForegroundColor Cyan
Write-Host "  4) View setup instructions" -ForegroundColor Cyan
Write-Host ""

$choice = Read-Host "Enter choice (1-4)"

switch ($choice) {
    "1" {
        Connect-Oracle -IP $ORACLE_INSTANCE_IP -KeyPath $SSH_KEY_PATH
    }
    "2" {
        Upload-SetupScript -IP $ORACLE_INSTANCE_IP -KeyPath $SSH_KEY_PATH
    }
    "3" {
        Fix-SSHKeyPermissions -KeyPath $SSH_KEY_PATH
    }
    "4" {
        Write-Host "`nQuick Setup Guide:" -ForegroundColor Yellow
        Write-Host "`n1. SSH into instance:" -ForegroundColor White
        Write-Host "   ssh -i $SSH_KEY_PATH ubuntu@$ORACLE_INSTANCE_IP" -ForegroundColor Cyan
        Write-Host "`n2. Run setup script:" -ForegroundColor White
        Write-Host "   bash /tmp/setup-oracle-cloud.sh" -ForegroundColor Cyan
        Write-Host "`n3. Edit environment variables:" -ForegroundColor White
        Write-Host "   nano /home/ubuntu/algo-trading-bot/.env" -ForegroundColor Cyan
        Write-Host "`n4. Restart bot:" -ForegroundColor White
        Write-Host "   docker stop trading-bot-cloud && docker rm trading-bot-cloud" -ForegroundColor Cyan
        Write-Host "   cd /home/ubuntu/algo-trading-bot && source .env && docker run -d --restart unless-stopped --name trading-bot-cloud -e APCA_API_KEY_ID=\$APCA_API_KEY_ID -e APCA_API_SECRET_KEY=\$APCA_API_SECRET_KEY -e APCA_API_BASE_URL=\$APCA_API_BASE_URL trading-bot" -ForegroundColor Cyan
        Write-Host "`n5. Check logs:" -ForegroundColor White
        Write-Host "   docker logs -f trading-bot-cloud" -ForegroundColor Cyan
    }
    default {
        Write-Host "❌ Invalid choice" -ForegroundColor Red
    }
}

Write-Host ""
