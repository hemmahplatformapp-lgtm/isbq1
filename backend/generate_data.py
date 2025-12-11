import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# Define the number of records and the time range
NUM_RECORDS = 300
START_TIME = datetime(2025, 6, 15, 8, 0, 0) # Simulated Hajj day start

# Possible locations for 'ground' and 'nusuk'
LOCATIONS = ['Mina', 'Arafat', 'Muzdalifah', 'Jamarat', 'Haram']

def generate_data():
    data = []
    
    # Generate a list of timestamps
    time_deltas = [timedelta(seconds=random.randint(1, 10)) for _ in range(NUM_RECORDS)]
    timestamps = [START_TIME + sum(time_deltas[:i+1], timedelta()) for i in range(NUM_RECORDS)]
    
    # Generate unique pilgrim IDs
    pilgrim_ids = [f"P{i:05d}" for i in range(1, NUM_RECORDS + 1)]
    
    for i in range(NUM_RECORDS):
        # Simulate time progression
        timestamp = timestamps[i]
        
        # Simulate normal conditions most of the time
        temp = np.random.normal(loc=38, scale=2)
        ground = random.choice(LOCATIONS)
        nusuk = ground # Allowed location is usually the current location
        sos = False
        lost_id = None
        
        # Introduce anomalies for decision engine testing
        if random.random() < 0.02: # 2% chance of high temp
            temp = np.random.normal(loc=46, scale=1)
        
        if random.random() < 0.05: # 5% chance of ground != nusuk (violator)
            nusuk = random.choice([loc for loc in LOCATIONS if loc != ground])
        
        if random.random() < 0.005: # 0.5% chance of SOS
            sos = True
            
        if random.random() < 0.01: # 1% chance of lost person
            lost_id = random.choice(pilgrim_ids)
            
        data.append({
            'timestamp': timestamp.isoformat(),
            'pilgrim_id': pilgrim_ids[i % len(pilgrim_ids)], # Reuse IDs to simulate movement
            'temp': round(temp, 2),
            'ground': ground,
            'nusuk': nusuk,
            'sos': sos,
            'lost_id': lost_id
        })

    df = pd.DataFrame(data)
    # Sort by timestamp to ensure correct streaming order
    df = df.sort_values(by='timestamp').reset_index(drop=True)
    
    # Save to CSV
    df.to_csv('pilgrims_data.csv', index=False)
    print(f"Generated {len(df)} records to pilgrims_data.csv")

if __name__ == "__main__":
    generate_data()
