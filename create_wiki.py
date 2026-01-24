#!/usr/bin/env python3
"""
GitHub Wiki Page Creator
Creates wiki pages via GitHub API
"""

import requests
import json
import os
import sys
from pathlib import Path

# Configuration
REPO_OWNER = "Ronaldmcdonaldeats"
REPO_NAME = "algo-trading-bot"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # Need to set this

# Wiki files to create
WIKI_FILES = {
    "Home": "Home.md",
    "Quick-Start": "Quick-Start.md",
    "Features": "Features.md",
    "Configuration": "Configuration.md",
    "Docker": "Docker.md",
    "Integration": "Integration.md",
    "Troubleshooting": "Troubleshooting.md",
}

def read_wiki_file(filename):
    """Read wiki file content"""
    filepath = Path("wiki-temp") / filename
    if not filepath.exists():
        print(f"❌ File not found: {filepath}")
        return None
    return filepath.read_text(encoding='utf-8')

def create_wiki_page(title, content):
    """Create wiki page via GitHub API"""
    if not GITHUB_TOKEN:
        print("❌ GITHUB_TOKEN environment variable not set")
        print("   Set it: $env:GITHUB_TOKEN = 'your_token'")
        return False
    
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/wiki"
    
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    data = {
        "title": title,
        "body": content
    }
    
    print(f"Creating page: {title}...", end=" ")
    
    try:
        response = requests.put(
            f"{url}/{title.replace(' ', '-')}",
            headers=headers,
            json=data
        )
        
        if response.status_code in [200, 201]:
            print("✅")
            return True
        else:
            print(f"❌ (Status: {response.status_code})")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Create all wiki pages"""
    print("\n🔧 Creating GitHub Wiki Pages\n")
    
    if not GITHUB_TOKEN:
        print("⚠️  GITHUB_TOKEN not set!")
        print("\nTo use this script:")
        print("1. Create a GitHub Personal Access Token:")
        print("   https://github.com/settings/tokens")
        print("\n2. Set environment variable:")
        print("   $env:GITHUB_TOKEN = 'your_token_here'")
        print("\n3. Run this script again")
        print("\nAlternatively, create pages manually at:")
        print("https://github.com/Ronaldmcdonaldeats/algo-trading-bot/wiki")
        return False
    
    print(f"Repository: {REPO_OWNER}/{REPO_NAME}")
    print(f"Token detected: Yes\n")
    
    success = 0
    failed = 0
    
    for page_title, filename in WIKI_FILES.items():
        content = read_wiki_file(filename)
        if content and create_wiki_page(page_title, content):
            success += 1
        else:
            failed += 1
    
    print(f"\n{'='*50}")
    print(f"✅ Created: {success}")
    print(f"❌ Failed: {failed}")
    print(f"{'='*50}\n")
    
    if failed == 0:
        print("🎉 All wiki pages created successfully!")
        print(f"\nView at: https://github.com/{REPO_OWNER}/{REPO_NAME}/wiki")
        return True
    else:
        print("⚠️  Some pages failed to create")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
