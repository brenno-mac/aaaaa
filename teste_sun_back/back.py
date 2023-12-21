
from flask import Flask, request

from flask_cors import CORS

app = Flask(__name__)

CORS(app)

@app.route('/', methods=['GET', 'POST'])
def receber_localizacao():
    data = request.json
    latitude = data.get('latitude')
    longitude = data.get('longitude')

    print(f'Latitude: {latitude}, Longitude: {longitude}')
    return 'Coordenadas recebidas com sucesso!'

if __name__ == '__main__':
    app.run(debug=True)
