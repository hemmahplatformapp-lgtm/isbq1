import eventlet
# Must monkey-patch early to make eventlet compatible with socket/IO libraries
eventlet.monkey_patch()

import os
import csv
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit

# Load environment variables
load_dotenv()

# --- Configuration ---
app = Flask(__name__, static_folder='../frontend/static', template_folder='../frontend')

# Configure database
database_url = os.getenv('DATABASE_URL') or os.getenv('SQLALCHEMY_DATABASE_URI') or 'sqlite:///pilgrim_events.db'
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- Global State ---
SIMULATION_STATE = {
    'running': False,
    'speed': 1,
    'current_index': 0,
    'total_records': 0,
    'data': []
}

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

# --- Data Loading ---
def load_data():
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

# --- Seed DB ---
def seed_db():
    with app.app_context():
        db.create_all()
        if not SIMULATION_STATE['data']:
            load_data()
        existing = db.session.query(PilgrimEvent).first()
        if existing:
            print("Database already contains data; skipping seeding.")
            return
        print("Seeding database...")
        for row in SIMULATION_STATE['data']:
            try:
                ts = datetime.fromisoformat(row['timestamp'])
            except Exception:
                ts = datetime.utcnow()
            event = PilgrimEvent(
                timestamp=ts,
                pilgrim_id=row.get('pilgrim_id', 'unknown'),
                temp=float(row.get('temp', 0.0)),
                ground=row.get('ground', ''),
                nusuk=row.get('nusuk', ''),
                sos=(row.get('sos') == 'True'),
                lost_id=row.get('lost_id') if row.get('lost_id') else None
            )
            db.session.add(event)
        db.session.commit()
        print("Database seeding complete.")

# --- Decision Engine ---
def decision_engine(event_data):
    temp = event_data['temp']
    ground = event_data['ground']
    nusuk = event_data['nusuk']
    sos = event_data['sos']
    lost_id = event_data['lost_id']

    alert = 'GREEN'
    action = 'آمن ومطابق للمسار'
    icon = '✅'

    if ground != nusuk:
        alert = 'RED'
        action = 'تنبيه مخالفة مسار حرجة، تحديد المخالفين وإرسال دورية'
        icon = '🚨'
    elif sos:
        alert = 'ORANGE'
        action = 'تنبيه استغاثة (SOS)، إرسال إسعاف فوري'
        icon = '🚑'
    elif temp >= 40.0:
        alert = 'YELLOW'
        action = 'تنبيه خطر إجهاد حراري، إرسال فرق ترطيب'
        icon = '☀️'
    elif lost_id:
        alert = 'BLUE'
        action = f'تنبيه مفقود/منفصل، إشعار المفقود: {lost_id}'
        icon = '👤'

    return {
        'alert': alert,
        'action': action,
        'icon': icon,
        'event': event_data
    }

# --- Simulation Runner ---
def simulation_runner():
    print("Simulation runner started.")
    if not SIMULATION_STATE['data']:
        load_data()

    while True:
        eventlet.sleep(0.1)
        if SIMULATION_STATE['running']:
            if SIMULATION_STATE['current_index'] < SIMULATION_STATE['total_records']:
                raw_event = SIMULATION_STATE['data'][SIMULATION_STATE['current_index']]
                event_data = {
                    'timestamp': raw_event['timestamp'],
                    'pilgrim_id': raw_event['pilgrim_id'],
                    'temp': float(raw_event['temp']),
                    'ground': raw_event['ground'],
                    'nusuk': raw_event['nusuk'],
                    'sos': raw_event['sos'] == 'True',
                    'lost_id': raw_event['lost_id'] if raw_event['lost_id'] else None
                }
                processed_event = decision_engine(event_data)

                if processed_event['alert'] == 'RED':
                    STAT_COUNTERS['red_alerts'] += 1
                elif processed_event['alert'] == 'ORANGE':
                    STAT_COUNTERS['orange_alerts'] += 1
                elif processed_event['alert'] == 'YELLOW':
                    STAT_COUNTERS['yellow_alerts'] += 1
                elif processed_event['alert'] == 'BLUE':
                    STAT_COUNTERS['blue_alerts'] += 1
                STAT_COUNTERS['total_events'] += 1

                socketio.emit('realtime_event', processed_event, namespace='/ws/demo')

                current_time = datetime.fromisoformat(event_data['timestamp']).strftime('%H:%M:%S')
                counters = {
                    'ground': event_data['ground'],
                    'nusuk': event_data['nusuk'],
                    'time': current_time
                }
                socketio.emit('counters_update', counters, namespace='/ws/demo')

                SIMULATION_STATE['current_index'] += 1
                delay = 1.0 / SIMULATION_STATE['speed']
                eventlet.sleep(delay)
            else:
                SIMULATION_STATE['running'] = False
                socketio.emit('simulation_status', {'status': 'finished'}, namespace='/ws/demo')
                print("Simulation finished.")
        else:
            eventlet.sleep(1)

# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/control', methods=['POST'])
def control_simulation():
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
        for key in STAT_COUNTERS:
            STAT_COUNTERS[key] = 0
        response['message'] = 'Simulation reset.'
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

# --- SocketIO Events ---
@socketio.on('connect', namespace='/ws/demo')
def handle_connect():
    print('Client connected to /ws/demo')
    if not getattr(app, 'simulation_started', False):
        app.simulation_started = True
        load_data()
        eventlet.spawn(simulation_runner)
    emit('simulation_status', {'status': 'connected', 'running': SIMULATION_STATE['running'], 'speed': SIMULATION_STATE['speed']}, namespace='/ws/demo')

@socketio.on('disconnect', namespace='/ws/demo')
def handle_disconnect():
    print('Client disconnected from /ws/demo')

# --- Error handler ---
@app.errorhandler(500)
def handle_internal_error(e):
    try:
        if request.path.startswith('/api/'):
            return jsonify({'error': 'internal_server_error'}), 500
    except Exception:
        pass
    return ("Internal Server Error", 500)

# --- Application Startup ---
if __name__ == '__main__':
    print("Starting Flask-SocketIO server locally...")
    load_data()
    seed_db()
    eventlet.spawn(simulation_runner)
    socketio.run(app, host='0.0.0.0', port=5000)

# --- For Gunicorn / Render ---
if __name__ != '__main__':
    application = app
