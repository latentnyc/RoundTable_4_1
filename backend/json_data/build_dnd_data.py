import requests
import json
import time
import os

# Base URL for the 5e SRD API
BASE_URL = "https://www.dnd5eapi.co"

def fetch_all(endpoint):
    """Fetches the index list of resources."""
    print(f"Fetching index: {endpoint}...")
    try:
        response = requests.get(f"{BASE_URL}{endpoint}")
        if response.status_code == 200:
            return response.json().get('results', [])
    except Exception as e:
        print(f"Error connecting to {endpoint}: {e}")
    return []

def fetch_detail(url):
    """Fetches full details from a specific URL."""
    # Sleep to respect API rate limits
    time.sleep(0.05) 
    try:
        response = requests.get(f"{BASE_URL}{url}")
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f"✅ SAVED: {filename} ({len(data)} records)")

# ==========================================
# MONSTER BUILDER
# ==========================================
def build_monster_box():
    print("\n--- Processing Monsters (This is large, please wait) ---")
    monsters = []
    
    # 1. Get the list of all monsters
    index = fetch_all("/api/monsters")
    total = len(index)
    
    # 2. Loop through and get full details for each
    for i, m_idx in enumerate(index):
        if i % 25 == 0: 
            print(f"Processing monster {i}/{total}...")
        
        data = fetch_detail(m_idx['url'])
        
        if data:
            # Helper: Flatten Special Abilities descriptions for easier UI
            if 'special_abilities' in data:
                for ability in data['special_abilities']:
                    if 'desc' in ability:
                         # Ensure desc is clean text
                         pass
            
            monsters.append(data)
        
    save_json('monsters.json', monsters)

if __name__ == "__main__":
    print("STARTING MONSTER HARVEST...")
    build_monster_box()
    print("\nDONE.")