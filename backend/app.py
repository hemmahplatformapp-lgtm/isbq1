import os
import csv
import time
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
import eventlet

# Load environment variables
load_dotenv()

# --- Configuration ---
# app.py is now in backend/, so '../frontend' is the correct path to the frontend folder
app = Flask(__name__, static_folder='../frontend/static', template_folder='../frontend')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pilgrim_events.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- Global State for Simulation Control ---
SIMULATION_STATE = {
    'running': False,
    'speed': 1, # 1x, 2x, 4x
    'current_index': 0,
    'total_records': 0,
    'data': []
}

# --- Cumulative Statistics Tracking ---
STAT_COUNTERS = {
    'red_alerts': 0,
    'orange_alerts': 0,
    'yellow_alerts': 0,
    'blue_alerts': 0,
    'total_events': 0
}

# --- Database Model ---
class PilgrimEvent(db.Model):
    __tablename__ = 'pilgrim_events'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False)
    pilgrim_id = db.Column(db.String(50), nullable=False)
    temp = db.Column(db.Float, nullable=False)
    ground = db.Column(db.String(50), nullable=False)
    nusuk = db.Column(db.String(50), nullable=False)
    sos = db.Column(db.Boolean, nullable=False)
    lost_id = db.Column(db.String(50), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'pilgrim_id': self.pilgrim_id,
            'temp': self.temp,
            'ground': self.ground,
            'nusuk': self.nusuk,
            'sos': self.sos,
            'lost_id': self.lost_id
        }

# --- Data Loading and Seeding ---
def load_data():
    """Loads data from CSV and stores it in SIMULATION_STATE."""
    # pilgrims_data.csv is now in the root directory (../) relative to backend/
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'pilgrims_data.csv')
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            SIMULATION_STATE['data'] = list(reader)
            SIMULATION_STATE['total_records'] = len(SIMULATION_STATE['data'])
            print(f"Data loaded: {SIMULATION_STATE['total_records']} records.")
    except FileNotFoundError:
        print(f"Error: pilgrims_data.csv not found at {csv_path}")
        SIMULATION_STATE['data'] = []
        SIMULATION_STATE['total_records'] = 0

def seed_db():
    """Seeds the database with all historical data."""
    with app.app_context():
        db.drop_all()
        db.create_all()
        
        if not SIMULATION_STATE['data']:
            load_data()

        print("Seeding database...")
        for row in SIMULATION_STATE['data']:
            event = PilgrimEvent(
                timestamp=datetime.fromisoformat(row['timestamp']),
                pilgrim_id=row['pilgrim_id'],
                temp=float(row['temp']),
                ground=row['ground'],
                nusuk=row['nusuk'],
                sos=row['sos'] == 'True',
                lost_id=row['lost_id'] if row['lost_id'] else None
            )
            db.session.add(event)
        db.session.commit()
        print("Database seeding complete.")

# --- Decision Engine (Improved) ---
def decision_engine(event_data):
    """Applies decision logic to an event and returns an alert and action."""
    temp = event_data['temp']
    ground = event_data['ground']
    nusuk = event_data['nusuk']
    sos = event_data['sos']
    lost_id = event_data['lost_id']

    alert = 'GREEN'
    action = 'آمن ومطابق للمسار'
    icon = '✅'

    # Priority 1: RED (Critical Violation - Route Deviation)
    if ground != nusuk:
        alert = 'RED'
        action = 'تنبيه مخالفة مسار حرجة، تحديد المخالفين وإرسال دورية'
        icon = '🚨'
    # Priority 2: ORANGE (Immediate Danger - SOS Signal)
    elif sos:
        alert = 'ORANGE'
        action = 'تنبيه استغاثة (SOS)، إرسال إسعاف فوري'
        icon = '🚑'
    # Priority 3: YELLOW (High Risk - Heat Stress)
    elif temp >= 40.0:
        alert = 'YELLOW'
        action = 'تنبيه خطر إجهاد حراري، إرسال فرق ترطيب'
        icon = '☀️'
    # Priority 4: BLUE (Separation/Lost)
    elif lost_id:
        alert = 'BLUE'
        action = f'تنبيه مفقود/منفصل، إشعار المفقود: {lost_id}'
        icon = '👤'
    # Priority 5: GREEN (Safe)
    
    return {
        'alert': alert,
        'action': action,
        'icon': icon,
        'event': event_data
    }

# --- Simulation Thread ---
def simulation_runner():
    """Streams historical data as real-time events."""
    print("Simulation runner started.")
    
    # Ensure data is loaded
    if not SIMULATION_STATE['data']:
        load_data()

    while True:
        eventlet.sleep(0.1) # Non-blocking sleep

        if SIMULATION_STATE['running']:
            if SIMULATION_STATE['current_index'] < SIMULATION_STATE['total_records']:
                
                # Get the next event
                raw_event = SIMULATION_STATE['data'][SIMULATION_STATE['current_index']]
                
                # Convert types for decision engine
                event_data = {
                    'timestamp': raw_event['timestamp'],
                    'pilgrim_id': raw_event['pilgrim_id'],
                    'temp': float(raw_event['temp']),
                    'ground': raw_event['ground'],
                    'nusuk': raw_event['nusuk'],
                    'sos': raw_event['sos'] == 'True',
                    'lost_id': raw_event['lost_id'] if raw_event['lost_id'] else None
                }
                
                # Process event
                processed_event = decision_engine(event_data)
                
                # Update cumulative statistics
                if processed_event['alert'] == 'RED':
                    STAT_COUNTERS['red_alerts'] += 1
                elif processed_event['alert'] == 'ORANGE':
                    STAT_COUNTERS['orange_alerts'] += 1
                elif processed_event['alert'] == 'YELLOW':
                    STAT_COUNTERS['yellow_alerts'] += 1
                elif processed_event['alert'] == 'BLUE':
                    STAT_COUNTERS['blue_alerts'] += 1
                STAT_COUNTERS['total_events'] += 1
                
                # Broadcast event to all connected clients
                socketio.emit('realtime_event', processed_event, namespace='/ws/demo')
                
                # Update counters (simplified for demo: count all events)
                current_time = datetime.fromisoformat(event_data['timestamp']).strftime('%H:%M:%S')
                
                # Calculate current counters (simplified: just the current event's location)
                counters = {
                    'ground': event_data['ground'],
                    'nusuk': event_data['nusuk'],
                    'time': current_time
                }
                socketio.emit('counters_update', counters, namespace='/ws/demo')

                # Move to the next record
                SIMULATION_STATE['current_index'] += 1
                
                # Wait based on speed
                # Simulate a 1-second delay for 1x speed, adjusted by the speed factor
                delay = 1.0 / SIMULATION_STATE['speed']
                eventlet.sleep(delay)
            else:
                # Simulation finished
                SIMULATION_STATE['running'] = False
                socketio.emit('simulation_status', {'status': 'finished'}, namespace='/ws/demo')
                print("Simulation finished.")
        else:
            eventlet.sleep(1) # Wait longer when paused

# --- Routes and API Endpoints ---

@app.route('/')
def index():
    """Serves the main PWA dashboard page."""
    return render_template('index.html')

@app.route('/api/control', methods=['POST'])
def control_simulation():
    """API endpoint to control the simulation."""
    action = request.json.get('action')
    value = request.json.get('value')
    
    response = {'status': 'ok', 'message': f'Action {action} executed.'}

    if action == 'START':
        SIMULATION_STATE['running'] = True
        response['message'] = 'Simulation started.'
    elif action == 'PAUSE':
        SIMULATION_STATE['running'] = False
        response['message'] = 'Simulation paused.'
    elif action == 'RESET':
        SIMULATION_STATE['running'] = False
        SIMULATION_STATE['current_index'] = 0
        STAT_COUNTERS['red_alerts'] = 0
        STAT_COUNTERS['orange_alerts'] = 0
        STAT_COUNTERS['yellow_alerts'] = 0
        STAT_COUNTERS['blue_alerts'] = 0
        STAT_COUNTERS['total_events'] = 0
        response['message'] = 'Simulation reset.'
    elif action == 'NEXT_STEP':
        # Execute one step if not running
        if not SIMULATION_STATE['running']:
            # The original implementation of NEXT_STEP was complex and could lead to race conditions.
            # A simpler approach is to directly call the logic for one step.
            
            if SIMULATION_STATE['current_index'] < SIMULATION_STATE['total_records']:
                # Get the next event
                raw_event = SIMULATION_STATE['data'][SIMULATION_STATE['current_index']]
                
                # Convert types for decision engine
                event_data = {
                    'timestamp': raw_event['timestamp'],
                    'pilgrim_id': raw_event['pilgrim_id'],
                    'temp': float(raw_event['temp']),
                    'ground': raw_event['ground'],
                    'nusuk': raw_event['nusuk'],
                    'sos': raw_event['sos'] == 'True',
                    'lost_id': raw_event['lost_id'] if raw_event['lost_id'] else None
                }
                
                # Process event
                processed_event = decision_engine(event_data)
                
                # Update cumulative statistics
                if processed_event['alert'] == 'RED':
                    STAT_COUNTERS['red_alerts'] += 1
                elif processed_event['alert'] == 'ORANGE':
                    STAT_COUNTERS['orange_alerts'] += 1
                elif processed_event['alert'] == 'YELLOW':
                    STAT_COUNTERS['yellow_alerts'] += 1
                elif processed_event['alert'] == 'BLUE':
                    STAT_COUNTERS['blue_alerts'] += 1
                STAT_COUNTERS['total_events'] += 1
                
                # Broadcast event to all connected clients
                socketio.emit('realtime_event', processed_event, namespace='/ws/demo')
                
                # Update counters
                current_time = datetime.fromisoformat(event_data['timestamp']).strftime('%H:%M:%S')
                counters = {
                    'ground': event_data['ground'],
                    'nusuk': event_data['nusuk'],
                    'time': current_time
                }
                socketio.emit('counters_update', counters, namespace='/ws/demo')

                # Move to the next record
                SIMULATION_STATE['current_index'] += 1
                response['message'] = 'Executed next step.'
            else:
                response['status'] = 'error'
                response['message'] = 'Simulation finished, cannot step further.'
        else:
            response['status'] = 'error'
            response['message'] = 'Cannot step while running.'
    elif action == 'SPEED':
        try:
            speed = int(value)
            if speed in [1, 2, 4]:
                SIMULATION_STATE['speed'] = speed
                response['message'] = f'Playback speed set to {speed}x.'
            else:
                response['status'] = 'error'
                response['message'] = 'Invalid speed value.'
        except ValueError:
            response['status'] = 'error'
            response['message'] = 'Invalid speed format.'
    else:
        response['status'] = 'error'
        response['message'] = 'Invalid action.'

    socketio.emit('simulation_status', {'status': action.lower(), 'running': SIMULATION_STATE['running'], 'speed': SIMULATION_STATE['speed']}, namespace='/ws/demo')
    return jsonify(response)

@app.route('/api/status', methods=['GET'])
def get_status():
    """Returns the current status of the simulation."""
    return jsonify({
        'running': SIMULATION_STATE['running'],
        'speed': SIMULATION_STATE['speed'],
        'current_index': SIMULATION_STATE['current_index'],
        'total_records': SIMULATION_STATE['total_records']
    })

@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """Returns real-time statistics about alerts and pilgrim locations."""
    with app.app_context():
        # Count alerts by type
        red_alerts = db.session.query(PilgrimEvent).filter(PilgrimEvent.ground != PilgrimEvent.nusuk).count()
        orange_alerts = db.session.query(PilgrimEvent).filter(PilgrimEvent.sos == True).count()
        yellow_alerts = db.session.query(PilgrimEvent).filter(PilgrimEvent.temp >= 40.0).count()
        blue_alerts = db.session.query(PilgrimEvent).filter(PilgrimEvent.lost_id != None).count()
        
        # Count pilgrims by location
        locations = db.session.query(
            PilgrimEvent.ground,
            db.func.count(PilgrimEvent.id).label('count')
        ).group_by(PilgrimEvent.ground).all()
        
        location_data = {location: count for location, count in locations}
        
        # Temperature statistics
        temp_stats = db.session.query(
            db.func.min(PilgrimEvent.temp).label('min_temp'),
            db.func.max(PilgrimEvent.temp).label('max_temp'),
            db.func.avg(PilgrimEvent.temp).label('avg_temp')
        ).first()
        
        return jsonify({
            'alerts': {
                'red': red_alerts,
                'orange': orange_alerts,
                'yellow': yellow_alerts,
                'blue': blue_alerts
            },
            'locations': location_data,
            'temperature': {
                'min': float(temp_stats.min_temp) if temp_stats.min_temp else 0,
                'max': float(temp_stats.max_temp) if temp_stats.max_temp else 0,
                'avg': float(temp_stats.avg_temp) if temp_stats.avg_temp else 0
            }
        })

@app.route('/api/temperature-timeline', methods=['GET'])
def get_temperature_timeline():
    """Returns temperature data over time for charting."""
    with app.app_context():
        events = db.session.query(
            PilgrimEvent.timestamp,
            db.func.avg(PilgrimEvent.temp).label('avg_temp'),
            db.func.max(PilgrimEvent.temp).label('max_temp'),
            db.func.min(PilgrimEvent.temp).label('min_temp')
        ).group_by(
            db.func.strftime('%Y-%m-%d %H:%M', PilgrimEvent.timestamp)
        ).order_by(PilgrimEvent.timestamp).all()
        
        data = {
            'timestamps': [],
            'avg_temps': [],
            'max_temps': [],
            'min_temps': []
        }
        
        for event in events:
            data['timestamps'].append(event.timestamp.isoformat())
            data['avg_temps'].append(float(event.avg_temp) if event.avg_temp else 0)
            data['max_temps'].append(float(event.max_temp) if event.max_temp else 0)
            data['min_temps'].append(float(event.min_temp) if event.min_temp else 0)
        
        return jsonify(data)

@app.route('/api/alerts-timeline', methods=['GET'])
def get_alerts_timeline():
    """Returns alert counts over time for charting."""
    with app.app_context():
        # Get alerts grouped by time
        red_alerts = db.session.query(
            db.func.strftime('%Y-%m-%d %H:%M', PilgrimEvent.timestamp).label('time'),
            db.func.count(PilgrimEvent.id).label('count')
        ).filter(PilgrimEvent.ground != PilgrimEvent.nusuk).group_by('time').all()
        
        orange_alerts = db.session.query(
            db.func.strftime('%Y-%m-%d %H:%M', PilgrimEvent.timestamp).label('time'),
            db.func.count(PilgrimEvent.id).label('count')
        ).filter(PilgrimEvent.sos == True).group_by('time').all()
        
        yellow_alerts = db.session.query(
            db.func.strftime('%Y-%m-%d %H:%M', PilgrimEvent.timestamp).label('time'),
            db.func.count(PilgrimEvent.id).label('count')
        ).filter(PilgrimEvent.temp >= 40.0).group_by('time').all()
        
        # Convert to dict for easier lookup
        red_dict = {time: count for time, count in red_alerts}
        orange_dict = {time: count for time, count in orange_alerts}
        yellow_dict = {time: count for time, count in yellow_alerts}
        
        # Get all unique times
        all_times = sorted(set(red_dict.keys()) | set(orange_dict.keys()) | set(yellow_dict.keys()))
        
        data = {
            'timestamps': all_times,
            'red': [red_dict.get(t, 0) for t in all_times],
            'orange': [orange_dict.get(t, 0) for t in all_times],
            'yellow': [yellow_dict.get(t, 0) for t in all_times]
        }
        
        return jsonify(data)

@app.route('/api/location-distribution', methods=['GET'])
def get_location_distribution():
    """Returns distribution of pilgrims across locations."""
    with app.app_context():
        # Get latest location for each pilgrim
        subquery = db.session.query(
            PilgrimEvent.pilgrim_id,
            db.func.max(PilgrimEvent.timestamp).label('max_time')
        ).group_by(PilgrimEvent.pilgrim_id).subquery()
        
        latest_events = db.session.query(
            PilgrimEvent.ground,
            db.func.count(PilgrimEvent.id).label('count')
        ).join(
            subquery,
            (PilgrimEvent.pilgrim_id == subquery.c.pilgrim_id) &
            (PilgrimEvent.timestamp == subquery.c.max_time)
        ).group_by(PilgrimEvent.ground).all()
        
        data = {
            'locations': [location for location, _ in latest_events],
            'counts': [count for _, count in latest_events]
        }
        
        return jsonify(data)

@app.route('/api/cumulative-stats', methods=['GET'])
def get_cumulative_stats():
    """Returns cumulative statistics during simulation."""
    return jsonify(STAT_COUNTERS)

# --- SocketIO Events ---

@socketio.on('connect', namespace='/ws/demo')
def handle_connect():
    print('Client connected to /ws/demo')
    emit('simulation_status', {'status': 'connected', 'running': SIMULATION_STATE['running'], 'speed': SIMULATION_STATE['speed']}, namespace='/ws/demo')

@socketio.on('disconnect', namespace='/ws/demo')
def handle_disconnect():
    print('Client disconnected from /ws/demo')

# --- Application Startup ---
if __name__ == '__main__':
    load_data()
    # DB seeding is now handled locally since we removed Docker
    seed_db() 
    
    # Start the simulation thread
    eventlet.spawn(simulation_runner)
    
    # Run the application
    print("Starting Flask-SocketIO server...")
    socketio.run(app, host='0.0.0.0', port=5000)

# Use eventlet for WSGI server
if __name__ != '__main__':
    # This block is for running with a WSGI server like gunicorn/eventlet
    load_data()
    eventlet.spawn(simulation_runner)
    application = app
