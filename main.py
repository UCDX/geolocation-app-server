from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from geopy.distance import great_circle
import datetime

app = Flask(__name__)
socketio = SocketIO(app)

# Lista para almacenar los datos de geolocalización de los usuarios
usuarios = []

# Ruta para la página principal
@app.route('/')
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

if __name__ == '__main__':
    socketio.run(app, debug=True)
