from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, text
from flask_socketio import SocketIO, emit
from geopy.distance import great_circle
from config import DATABASE_CONNECTION_URI, ENV, DIST_TRESHOLD
import config
from flask_cors import CORS
from datetime import datetime
from threading import Thread
import numpy as np
import time
import CommentClassifier as CC
from mysql import connector

app = Flask(__name__)
# Configurar CORS
CORS(app, resources={r"/*": {"origins": "*"}})  # Permitir todas las solicitudes desde cualquier origen
socketio = SocketIO(app, cors_allowed_origins="*")
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_CONNECTION_URI
db = SQLAlchemy(app)

# DB

engine = create_engine(DATABASE_CONNECTION_URI, pool_size=1, pool_recycle=3600)
conn = engine.connect()

# Modelo para clasificar comentarios
commentClassifier=CC.Classifier()

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

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    comment = db.Column(db.String(500), nullable=False)
    fromUserId = db.Column(db.Integer,db.ForeignKey('user.id'), nullable=False,)
    toUserId = db.Column(db.Integer, db.ForeignKey('user.id'),nullable=False)
    rate=db.Column(db.Integer, nullable=False)
    fromUser = db.relationship('User',foreign_keys=[fromUserId], backref=db.backref('fromUser_comment', lazy=True))  # Relación uno a muchos
    toUser = db.relationship('User',foreign_keys=[toUserId], backref=db.backref('comment', lazy=True))  # Relación uno a muchos

    def __init__(self, comment,fromUserId,toUserId,rate):
        self.comment=comment
        self.fromUserId=fromUserId
        self.toUserId=toUserId
        self.rate=rate

# Ruta para postear un comentario
@app.route('/comment', methods=['POST'])
def createComment():
    data = request.get_json()
    if data:
    # obtiene los datos del json
        comment = data.get('comment')
        fromUserId = data.get('fromUserId')
        toUserId=data.get('toUserId')
        rate=commentClassifier.classifyComment(comment) # Usa el modelo para clasificar el comentario

        # Crear un nuevo comentario y lo almacena en la BD
        newComment = Comment(comment,fromUserId,toUserId,rate)
        db.session.add(newComment)
        db.session.commit()

        # Retorna una respuesta en formato JSON con los datos de registro exitoso
        return jsonify({
            'message': 'Registro exitoso',
            'data': {
                'id': newComment.id,
                'username': newComment.comment,
                'rate': rate
            }
        }), 200
    else:
        return jsonify({'message': 'Error en el formato de los datos'}), 400

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
            'birthdate': datetime.strptime( str(user.birthdate), '%Y-%m-%d').strftime('%m/%d/%Y') if user.birthdate else '',
            'interests': user.interests
        }
        # Obtiene todos los comentarios de los usuarios cercanos
        #query='select C.comment,C.rate,FU.name,C.toUserId from comment as C inner join user as FU on FU.id=C.fromUserId where '
        query='select C.comment,C.rate,FU.name,C.toUserId from comment as C inner join user as FU on FU.id=C.fromUserId where '
        user_list = [user_id]
        where_clause = [ f'C.toUserId = {user_id}' for user_id in user_list ]
        query = query + ' or '.join(where_clause)
        print(query)
        # sql_text = text(query)
        # result = conn.execute(sql_text)
        # commentsRows = result.mappings().all()

        mysql_conn = connector.connect(
            host=config.host,
            user=config.user,
            password=config.password,
            database=config.database
        )

        cursor = mysql_conn.cursor()
        cursor.execute(query)
        comments=[]
        print('----------------- query result: --------------')
        for (comment, rate, name, toUserId) in cursor:
            print(f'comment={comment}, rate={rate}, name={name}, toUserId={toUserId}.')
            comments.append({
                'comment':comment,
                'rate':rate,
                'from':name
            })
        cursor.close()
        print(comments)
        
        #commentsRows = dict(commentsRows)
        #print(commentsRows)
        # comments=[]
        # for commentRow in commentsRows:
        #     comments.append({
        #         'comment':commentRow.comment,
        #         'rate':commentRow.rate,
        #         'from':commentRow.name,
        #     })
        user_info['comments'] = comments
        # Fin de obtener los comentarios.
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

users = {}

last_user_info_sent = {}

last_time_zero_info_was_sent = False


# Logs what the users dict have inside.
def logs_users_connected(users):
    print('------ Logging connected users ------')
    while True:
        print('---> Users connected:', users)
        time.sleep(3)


# Detects when a user is in the detection area of other one.
def nearby_users_detection_loop(users: dict):
    print('------ Detection Loop ------ ')
    dist_treshold = DIST_TRESHOLD # in meters
    while True:
        users_ = users.copy()
        l = len(users_)
        user_data_array = np.array(list(users_.values()))
        user_key_array = np.array(list(users_.keys()))
        nearby_users: dict[str, list] = {}
        for i in range(l):
            ui = user_data_array[i]
            for j in range(i + 1, l):
                uj = user_data_array[j]
                dist = great_circle((ui['lat'], ui['lon']), (uj['lat'], uj['lon'])).meters
                # print(f'dist: {dist}')
                if dist <= dist_treshold:
                    if user_key_array[i] in nearby_users:
                        nearby_users[ user_key_array[i] ].append(uj['user_id'])
                    else:
                        nearby_users[ user_key_array[i] ] = [ uj['user_id'] ]
                    if user_key_array[j] in nearby_users:
                        nearby_users[ user_key_array[j] ].append(ui['user_id'])
                    else:
                        nearby_users[ user_key_array[j] ] = [ ui['user_id'] ]
        send_users_info(nearby_users, user_key_array)
        time.sleep(0.5)


# Sends the information of the nearby users to the targe user.
def send_users_info(nearby_users: dict[str, list], all_users):
    global last_time_zero_info_was_sent
    global last_user_info_sent
    # if len(nearby_users) == 0:
    #     if not last_time_zero_info_was_sent:
    #         socketio.emit('nearby-users', [])
    #         last_time_zero_info_was_sent = True
    for user in nearby_users:
        last_time_zero_info_was_sent = False
        # Verify if something was sent before.
        if user in last_user_info_sent:
            # Verify if the previous info sent was the same as the current one.
            if set(nearby_users[user]) != set(last_user_info_sent[user]):
                # If not, save it and send it. Else, ignore it.
                print('-- Sending new info for:', user)
                users_data = get_users_data(nearby_users[user])
                last_user_info_sent[user] = nearby_users[user]
                socketio.emit('nearby-users', users_data, to=user)
        # If nothing was sent before, save it and send it.
        else:
            print('-- Firt time sending info for:', user)
            users_data = get_users_data(nearby_users[user])
            last_user_info_sent[user] = nearby_users[user]
            socketio.emit('nearby-users', users_data, to=user)
    remain_users = set(all_users) - set(list(nearby_users.keys()))
    for u in remain_users:
        if u in last_user_info_sent:
            if len(last_user_info_sent[u]) > 0:
                last_user_info_sent[u] = []
                socketio.emit('nearby-users', [])
        else:
            last_user_info_sent[u] = []
            socketio.emit('nearby-users', [])
            


def get_users_data(user_list):
    # user = User.query.filter_by(username=username).first()
    query = 'select * from user where '
    where_clause = [ f'id = {user_id}' for user_id in user_list ]
    query = query + ' or '.join(where_clause)
    print(query)
    sql_text = text(query)
    result = conn.execute(sql_text)
    print('----------------- query result: --------------')
    rows = result.mappings().all()

    # Obtiene todos los comentarios de los usuarios cercanos
    query='select C.comment,C.rate,FU.name,C.toUserId from comment as C inner join user as FU on FU.id=C.fromUserId where '
    where_clause = [ f'C.toUserId = {user_id}' for user_id in user_list ]
    query = query + ' or '.join(where_clause)
    print(query)
    sql_text = text(query)
    result = conn.execute(sql_text)
    print('----------------- query result: --------------')
    commentsRows = result.mappings().all()
    return rows_to_dict(rows,commentsRows)


# custom for: get_users_data(...) function.
def rows_to_dict(rows,commentsRows):
    rs = []
    for r in rows:
        comments=[]

        for commentRow in commentsRows:
            if commentRow.toUserId==r.id:
                comment={
                    'comment':commentRow.comment,
                    'rate':commentRow.rate,
                    'from':commentRow.name,
                }

                comments.append(comment)

        d = {
            'id': r.id,
            'username': r.username,
            'name': r.name,
            'age': r.age,
            'birthdate': datetime.strptime( str(r.birthdate), '%Y-%m-%d').strftime('%m/%d/%Y') if r.birthdate else '',
            'interests': r.interests,
            'comments':comments
        }
        rs.append(d)
    return rs


@socketio.on('connect')
def test_connect(auth):
  print(f'-------->>> Client connected:: {request.sid}')
  #print('users:', users)
  pass


@socketio.on('disconnect')
def test_disconnect():
    print(f'-------->>> Client disconnected: {request.sid}')
    if request.sid in users:
        del users[request.sid]
    if request.sid in last_user_info_sent:
        del last_user_info_sent[request.sid]
    print('users:', users)


@socketio.on('update-location')
def hanlder_update_location(data):
    #print('--- On: update_location')
    users[request.sid] = data
    #print('users:', users)

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
        'tiempo': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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


def main(): #logs_users_connected
    th_log_users = Thread(target=logs_users_connected, args=(users, ))
    th_log_users.start()
    th = Thread(target=nearby_users_detection_loop, args=(users, ))
    th.start()
    if ENV == 'production':
        socketio.run(app)
    elif ENV == 'development':
        socketio.run(app, debug=False, port=5000)
    else:
        socketio.run(app, debug=False, port=5000)

if __name__ == '__main__':
    main()
