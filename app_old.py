import os
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
import jwt
from datetime import datetime
import mysql.connector
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['UPLOAD_FOLDER'] = 'uploads/chat'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'pdf'}

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
        payload = jwt.decode(token, os.getenv('JWT_SECRET'), algorithms=['HS256'])
        return payload['user_id']
    except:
        return None

# File extension check
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# API Endpoint for media upload
@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        return jsonify({
            'url': f"/uploads/chat/{filename}",
            'name': filename,
            'type': file.content_type,
            'extension': filename.rsplit('.', 1)[1].lower()
        })
    
    return jsonify({'error': 'File type not allowed'}), 400

# WebSocket Events
@socketio.on('connect')
def handle_connect():
    token = request.args.get('token')
    if not token:
        return False
    
    user_id = authenticate(token)
    if not user_id:
        return False
    
    print(f"User {user_id} connected")
    emit('connection_success', {'user_id': user_id})

@socketio.on('send_message')
def handle_send_message(data):
    token = request.args.get('token')
    sender_id = authenticate(token)
    if not sender_id:
        emit('error', {'message': 'Authentication failed'})
        return
    
    required_fields = ['receiver_id', 'content']
    if not all(field in data for field in required_fields):
        emit('error', {'message': 'Missing required fields'})
        return
    
    # Prepare message data
    message_data = {
        'sender_id': sender_id,
        'receiver_id': data['receiver_id'],
        'message': data['content'],
        'ip_address': request.remote_addr,
        'message_date_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'sender_delete': 0,
        'reciver_delete': 0,
        'is_read': 0
    }
    
    # Handle media attachments
    if data.get('attachment'):
        message_data.update({
            'attachment_name': data['attachment'].get('name'),
            'file_ext': data['attachment'].get('extension'),
            'mime_type': data['attachment'].get('type')
        })
    
    # Save to MySQL
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
        
        # Add message ID to response
        message_data['id'] = message_id
        message_data['status'] = 'delivered'
        
        # Emit to receiver
        emit('receive_message', message_data, room=data['receiver_id'])
        
        # Confirm to sender
        emit('message_sent', message_data)
        
    except Exception as e:
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
    # Create upload directory if it doesn't exist
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
