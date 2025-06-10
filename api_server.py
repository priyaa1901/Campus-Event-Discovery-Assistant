from flask import Flask, jsonify
import sqlite3
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

def get_db_connection():
    conn = sqlite3.connect('../events.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/events')
def events():
    conn = get_db_connection()
    events = conn.execute('SELECT * FROM events').fetchall()
    conn.close()
    return jsonify([dict(row) for row in events])

@app.route('/api/event/<int:event_id>')
def event(event_id):
    conn = get_db_connection()
    event = conn.execute('SELECT * FROM events WHERE id = ?', (event_id,)).fetchone()
    conn.close()
    if event is None:
        return jsonify({'error': 'Event not found'}), 404
    return jsonify(dict(event))

if __name__ == '__main__':
    app.run(debug=True)
