import os
import requests
from flask import Flask, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room
import jwt
from datetime import datetime
import mysql.connector
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

# Configure MySQL
db_config = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME')
}

socketio = SocketIO(app, cors_allowed_origins="*")

# Database connection helper
def get_db_connection():
    return mysql.connector.connect(**db_config)

# JWT Authentication
def authenticate(token):
    try:
        if token == os.getenv('JWT_SECRET'):
            return 1  # example user_id
        return None
    except Exception as e:
        print(f"Authentication error: {e}")
        return None

# WebSocket Events
@socketio.on('connect')
def handle_connect():
    token = request.args.get('token')
    print(token)
    print('connection request')
    if not token:
        return False
    
    user_id = authenticate(token)
    print(user_id)
    if not user_id:
        return False
    
    print(f"User {user_id} connected")
    emit('connection_success', {'user_id': user_id})
@socketio.on('join')
def on_join(data):
    user_id = data.get('user_id')
    if user_id:
        join_room(str(user_id))
        print(f"User {user_id} joined room.")

@socketio.on('send_message')
def handle_send_message(data):
    token = request.args.get('token')
    sender_id = authenticate(token)
    print(data)
    if not sender_id:
        emit('error', {'message': 'Authentication failed'})
        return
    print('connected with token') 
    required_fields = ['receiver_id', 'content']
    if not all(field in data for field in required_fields):
        emit('error', {'message': 'Missing required fields'})
        return
    print('goign for inserting datat')
    # Prepare message data
    message_data = {
        'sender_id': data['sender_id'],
        'receiver_id': data['receiver_id'],
        'message': data['content'],
        'ip_address': request.remote_addr,
        'message_date_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'sender_delete': 0,
        'reciver_delete': 0,
        'is_read': 0
    }
    
    # Handle media attachments
    if data.get('attachment_name'):
        message_data.update({
            'attachment_name': data['attachment_name'],
            'file_ext': data['file_ext'],
            'mime_type': data['mime_type']
        })
    else:
        message_data.update({
            'attachment_name': None,
            'file_ext': None,
            'mime_type': None
        })    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
        INSERT INTO chat 
        (sender_id, receiver_id, message, attachment_name, file_ext, mime_type, 
         message_date_time, ip_address, sender_delete, reciver_delete, is_read)
        VALUES (%(sender_id)s, %(receiver_id)s, %(message)s, %(attachment_name)s, 
                %(file_ext)s, %(mime_type)s, %(message_date_time)s, %(ip_address)s, 
                %(sender_delete)s, %(reciver_delete)s, %(is_read)s)
        """
        cursor.execute(query, message_data)
        message_id = cursor.lastrowid
        conn.commit()
        print('gogin to responde back') 
        # Prepare and send push notification via API
        notification_payload = {
             'sender_id': int(data['sender_id']),
             'receiver_id': int(data['receiver_id'])
        }
        headers = {
            'User-Agent': 'PostmanRuntime/7.36.3',
            'Accept': '*/*',
            'Content-Type': 'application/json',
            'x-api-key': '90c04994-b3d4-4663-9f75-d6733e40cc47'
        }
        response = requests.post(
            'https://takavitutors.com/api/v1/send-chat-push-notifications',
            json=notification_payload,
            headers=headers
        )

        print('[API] Push notification sent. Response:', response.status_code, response.text)
        # Add message ID to response
        message_data['id'] = message_id
        message_data['status'] = 'delivered'
       # Emit to receiver
        emit('receive_message', message_data, room=str(data['receiver_id']))
        
        # Confirm to sender
        emit('message_sent', message_data, room=request.sid) 
        
    except Exception as e:
        print('connecteion err')
        print(str(e))
        emit('error', {'message': str(e)})
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

@socketio.on('mark_as_read')
def handle_mark_as_read(data):
    token = request.args.get('token')
    user_id = authenticate(token)
    if not user_id:
        return
    
    message_id = data.get('message_id')
    if not message_id:
        return
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
        UPDATE chat 
        SET is_read = 1 
        WHERE id = %s AND receiver_id = %s
        """
        cursor.execute(query, (message_id, user_id))
        conn.commit()
        
        emit('read_receipt', {
            'message_id': message_id,
            'status': 'read',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        emit('error', {'message': str(e)})
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
