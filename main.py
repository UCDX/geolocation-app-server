from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from geopy.distance import great_circle
from config import DATABASE_CONNECTION_URI
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
# Configurar CORS
CORS(app, resources={r"/*": {"origins": "*"}})  # Permitir todas las solicitudes desde cualquier origen
socketio = SocketIO(app)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_CONNECTION_URI
db = SQLAlchemy(app)

# ---------------------------------------------------------------------------------------------

# Modelo de Usuario
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    age = db.Column(db.Integer, nullable=True)
    birthdate = db.Column(db.Date, nullable=True)
    interests = db.Column(db.Text, nullable=True)

    def __init__(self, username, password, name, age=None, birthdate=None, interests=None):
        self.username = username
        self.password = password
        self.name = name
        self.age = age
        self.birthdate = birthdate
        self.interests = interests

# Ruta para el registro de usuarios
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if data:
        username = data.get('username')
        password = data.get('password')
        # Verificar si el usuario ya existe en la base de datos
        user = User.query.filter_by(username=username).first()
        if user:
            return jsonify({'message': 'El usuario ya existe en la base de datos'}), 409

        # Crear un nuevo usuario y almacenarlo en la base de datos
        new_user = User(username=username, password=password, name=username)
        db.session.add(new_user)
        db.session.commit()

        # Retorna una respuesta en formato JSON con los datos de registro exitoso
        return jsonify({
            'message': 'Registro exitoso',
            'data': {
                'id': new_user.id,
                'username': new_user.username,
            }
        }), 200
    else:
        return jsonify({'message': 'Error en el formato de los datos'}), 400

# Ruta para obtener información de un usuario
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if data:
        username = data.get('username')
        password = data.get('password')
        
        # Buscar al usuario en la base de datos
        user = User.query.filter_by(username=username, password=password).first()

        if user:
            user_info = {
                'id': user.id,
                'username': user.username
            }
            # Retorna una respuesta en formato JSON con la información del usuario
            return jsonify({
                'message': 'Inicio de sesión exitoso',
                'data': user_info
            })
        else:
            return jsonify({'message': 'Usuario no encontrado'}), 404
    else:
        return jsonify({'message': 'Error en el formato de los datos'}), 400

@app.route('/user/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = User.query.get(user_id)
    if user:
        user_info = {
            'id': user.id,
            'username': user.username,
            'name': user.name,
            'age': user.age,
            'birthdate': datetime.strptime( str(user.birthdate), '%Y-%m-%d').strftime('%m/%d/%Y'),
            'interests': user.interests
        }
        return jsonify({
            'message': 'Datos del usuario recuperados exitosamente',
            'data': user_info
        }), 200
    else:
        return jsonify({'message': 'Usuario no encontrado'}), 404

@app.route('/user/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    user = User.query.get(user_id)
    if user:
        data = request.get_json()
        if data:
            name = data.get('name')
            age = data.get('age')
            birthdate = datetime.strptime( data.get('birthdate'), '%m/%d/%Y').strftime('%Y-%m-%d')
            interests = data.get('interests')

            if not age or not birthdate or not interests:
                return jsonify({'message': 'Faltan datos obligatorios'}), 400

            user.name = name
            user.age = age
            user.birthdate = birthdate
            user.interests = interests
            db.session.commit()

            user_info = {
                'id': user.id,
                'username': user.username,
                'name': user.name,
                'age': user.age,
                'birthdate': str(user.birthdate),
                'interests': user.interests
            }
            return jsonify({'message': 'Datos de usuario actualizados exitosamente', 'data': user_info}), 200
        else:
            return jsonify({'message': 'Error en el formato de los datos'}), 400
    else:
        return jsonify({'message': 'Usuario no encontrado'}), 404

# ---------------------------------------------------------------------------------------------

# Lista para almacenar los datos de geolocalización de los usuarios
usuarios = []

# Ruta para testear la geolocalización.
@app.route('/close_users')
def index():
    return render_template('index.html')

# Manejador de eventos para la geolocalización del usuario
@socketio.on('ubicacion')
def handle_ubicacion(data):
    lat = float(data['lat'])
    lon = float(data['lon'])
    usuario = {
        'lat': lat,
        'lon': lon,
        'tiempo': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    # Comprobar si el usuario está dentro del área de detección de otros usuarios
    cercanos = []
    for u in usuarios:
        distancia = great_circle((lat, lon), (u['lat'], u['lon'])).meters
        print(f'Distancia: {distancia} metros')
        if distancia <= 20000: # Valor de distancia de detección en metros
            cercanos.append(u)  
    usuario['cercanos'] = cercanos
    usuarios.append(usuario)
    emit('usuarios_cercanos', {'usuarios': cercanos}, broadcast=True)

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    socketio.run(app, debug=True)
