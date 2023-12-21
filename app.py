from flask import Flask, jsonify, request
from datetime import datetime, timedelta
import requests
import pytz
from google.cloud import bigquery
import random
# from google.oauth2 import service_account
import os

from flask_cors import CORS

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'googlecredentials.json'
openweathermap_key = 'f1e2d7f95a234708727deecc82c74cb1'



timezone = pytz.timezone('America/Sao_Paulo')
app = Flask(__name__)

CORS(app)

# Create a BigQuery client using the credentials
client = bigquery.Client()

def get_cases_now():
    global minuto_atual
    valores_por_minuto = []
    valores_e_timestamps = []  # Defina a lista de valores e timestamps
    minuto_atual = 0
    
    # Sua consulta BigQuery original
    query = """
    SELECT
        FORMAT_TIMESTAMP('%Y-%m-%d', forecast_timestamp) AS dia,
        ROUND(forecast_value) AS previsao
    FROM
        ML.FORECAST(MODEL cancer_de_pele.cancer_forecast, 
            STRUCT(365 AS horizon))
    WHERE DATE(forecast_timestamp) = CURRENT_DATE()
    """
    query_job = client.query(query)
    result = query_job.result()
    
    # Obtém o valor do dia atual da consulta
    for row in result:
        valor_dia = row.previsao
    
    # Data e hora atual
    agora = datetime.now()

    # Verifica se o minuto atual mudou
    novo_minuto = agora.hour * 60 + agora.minute
    if novo_minuto > minuto_atual:
        minuto_atual = novo_minuto

        # Calcula a parte inteira da distribuição para o novo minuto
        parte_inteira = valor_dia // (24 * 60)

        # Distribui a parte inteira igualmente pelos minutos do dia
        valores_por_minuto = [parte_inteira] * (minuto_atual - len(valores_por_minuto))
        
        # Registra os valores e timestamps de atribuição
        timestamps = [agora - timedelta(minutes=i) for i in range(len(valores_por_minuto))]
        valores_e_timestamps.extend(zip(valores_por_minuto, timestamps))

        # Calcula o valor restante e o distribui aleatoriamente
        valor_restante = int(valor_dia - sum(valores_por_minuto))
        for _ in range(valor_restante):
            minuto_aleatorio = random.randint(0, minuto_atual - 1)
            valores_e_timestamps[minuto_aleatorio] = (valores_e_timestamps[minuto_aleatorio][0] + 1, valores_e_timestamps[minuto_aleatorio][1])

    # Filtra os valores diferentes de zero e seus timestamps
    valores_nao_zero_e_timestamps = [(valor, timestamp) for valor, timestamp in valores_e_timestamps if valor != 0]

    # Calcula a soma cumulativa até o minuto atual
    soma_cumulativa = sum([valor for valor, _ in valores_nao_zero_e_timestamps])

    return int(soma_cumulativa)

def get_cases_2023():
    query = """
    with agregado as ((with vegetti as (
SELECT
  max(parse_date('%d/%m/%Y', DT_DIAG)) AS maxdate
FROM
  cancer_de_pele.teste
WHERE
  EXTRACT(YEAR FROM parse_date('%d/%m/%Y', DT_DIAG)) = EXTRACT(YEAR FROM current_date()) and uf_resid = 33
)
select 
forecast_timestamp as dia, 
ROUND(forecast_value) as valor,
'Sim' as previsao
from 
ML.FORECAST(
  MODEL cancer_de_pele.cancer_forecast, 
  STRUCT(365 AS horizon))
where 
date(forecast_timestamp) between (select maxdate from vegetti) and current_date()
)
union all
(
  SELECT
  timestamp(parse_date('%d/%m/%Y', DT_DIAG)) AS date_parsed,
  COUNT(*) AS count,
  'Não' as previsao
FROM
  `datalake-2022.cancer_de_pele.teste`
WHERE
  EXTRACT(YEAR FROM parse_date('%d/%m/%Y', DT_DIAG)) = 2023 and uf_resid = 33
GROUP BY
  date_parsed
ORDER BY
  date_parsed desc

))
SELECT SUM(valor) AS total_cases
FROM agregado
WHERE dia != TIMESTAMP_TRUNC(CURRENT_TIMESTAMP, DAY)
"""
    query_job = client.query(query)
    result = query_job.result()
    for row in result:
        return row.total_cases


@app.route('/')
def index():
    return """
<!DOCTYPE html>
<html lang="en">

<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">

  <title>Document</title>
  <link href="https://fonts.googleapis.com/css2?family=Bai+Jamjuree:wght@200;300;400;500;600;700&display=swap" rel="stylesheet">
  <link href="https://fonts.googleapis.com/css2?family=Ubuntu:wght@300;400;500;700&display=swap" rel="stylesheet">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/bodymovin/5.12.2/lottie.min.js" integrity="sha512-jEnuDt6jfecCjthQAJ+ed0MTVA++5ZKmlUcmDGBv2vUI/REn6FuIdixLNnQT+vKusE2hhTk2is3cFvv5wA+Sgg==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>

  <script defer>

    var geolocationCollected = false;
    var latitude = null;
    var longitude = null;
    var lastUvIndexUpdateTime = 0; // Variável para controlar a última atualização do uv_index
    var uvIndexUpdateInterval = 30 * 60 * 1000; // Intervalo de atualização do uv_index em milissegundos (30 minutos)

    function collectLocation() {
      if ('geolocation' in navigator && !geolocationCollected) {
        navigator.geolocation.getCurrentPosition(function (position) {
          latitude = position.coords.latitude;
          longitude = position.coords.longitude;
          geolocationCollected = true;
          updateWeatherData();
        });
      }
    }

    function updateWeatherData() {
      if (latitude !== null && longitude !== null) {
        fetch(127.90.'/get_weather_data?lat=' + latitude + '&lon=' + longitude)
          .then(response => response.json())
          .then(data => {
            document.getElementById('city').textContent = data.city;
            document.getElementById('temperature').textContent = data.temperature;
            document.getElementById('humidity').textContent = data.humidity;
            document.getElementById('wind_speed').textContent = data.wind_speed;
            document.getElementById('fps_recommendation').textContent = data.fps_recommendation;
            document.getElementById('cases_2023').textContent = data.cases_2023;
            document.getElementById('cases_now').textContent = data.cases_now;
            document.getElementById('last_day').textContent = data.last_day;
            // Atualizar uv_index somente se o tempo desde a última atualização for maior que o intervalo especificado
            var currentTime = new Date().getTime();
            if (currentTime - lastUvIndexUpdateTime >= uvIndexUpdateInterval) {
              document.getElementById('uv_index').textContent = data.uv_index;
              lastUvIndexUpdateTime = currentTime; // Atualizar o tempo da última atualização do uv_index
            }

            // Ocultar a barra de carregamento e mostrar os dados
            document.getElementById('loadingScreem').style.display = 'none';
            document.getElementById('main_container').style.display = 'flex';
          });
      }
    }

    collectLocation();
    setInterval(updateWeatherData, 1800000); // Atualiza a cada 10 segundos

    function updateClock() {
      const clockElement = document.getElementById('clock');
      const now = new Date();
      const hours = now.getHours().toString().padStart(2, '0');
      const minutes = now.getMinutes().toString().padStart(2, '0');
      const seconds = now.getSeconds().toString().padStart(2, '0');
      const formattedTime = `${hours}:${minutes}:${seconds}`;
      clockElement.textContent = formattedTime;
    }

    setInterval(updateClock, 1000); // Atualiza o relógio a cada segundo
  </script>

  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
      font-family: 'Bai Jamjuree', sans-serif;
      font-style: normal;
      line-height: normal;
      color: #FFF;
    }

    #weather-data-container {
      display: flex;
      flex-direction: column;
      background: linear-gradient(#5ee6da, #035fa1);
      backdrop-filter: blur(267px);
      justify-content: flex-end;
      align-items: center;
      min-height: 100vh;
    }

    #loadingScreem {
      display: flex;
      height: 100%;
      align-items: center;
      margin: auto;
    }

    #animation_container {
      width: 500px;
      height: 500px;
    }

    .logo {
      padding-right: 20px;
    }

    #main_container {
      display: none;
      flex-direction: column;
      align-items: center;
      height: 100%;
      gap: 50px;
      padding: 30px 30px 30px 30px;
      margin: auto;
    }

    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      width: 100%;
      max-width: 953px;
    }

    footer {
      width: 100%;
      height: 64px;
      background: #353535;
      align-items: center;
      display: flex;
      justify-content: space-between;
      padding: 0px 20px 0px 20px;
    }

    .clock_local {
      display: flex;
      max-width: 953px;
      width: 100%;
      justify-content: center;
      gap: 24px;
      border-radius: 8px;
      background: linear-gradient(180deg, #FCD935 0%, #C19F00 100%), #FFF;
    }

    .clock_content,
    .clock_local h1 {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 16px;
    }

    .clock_local--text {
      color: #2D2D2D;
      text-align: center;
      font-family: Ubuntu;
      font-size: 24px;
      font-weight: 400;
    }

    .clock_content {
      display: flex;
      align-items: center
    }

    .cards-container {
      display: flex;
      flex-wrap: wrap;
      gap: 38px 27px;
      width: 100%;
      max-width: 964px;
      justify-content: center;
    }

    .card {
      display: flex;
      width: 463px;
      height: 223px;
      padding: 24px;
      flex-direction: column;
      align-items: center;
      gap: 8px;
      border-radius: 32px;
      border: 1px solid #FFF;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.15) 0%, rgba(255, 255, 255, 0.00) 100%);
      box-shadow: 0px 4px 20px 0px rgba(0, 0, 0, 0.60);
    }

    .card--title {
      display: flex;
      padding: 8px 0px;
      align-items: center;
      gap: 10px;
      font-size: 24px;
      font-weight: 400;
      font-family: Ubuntu;
    }

    .card--nums {
      font-family: Ubuntu;
      font-size: 55px;
      font-weight: 700;
    }

    .card--subtitles {
      font-family: Ubuntu;
      font-size: 16px;
      font-weight: 400;
      text-align: center;
    }

    .c5 {
      display: flex;
      max-height: 547px;
      max-width: 964px;
      width: 100%;
      padding: 35px 48px;
      justify-content: space-between;
      flex-direction: row;
      align-items: center;
    }

    .c5-info {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 16px;
    }

    @media(max-width: 1012px) {
      .c5 {
        width: 463px;
        flex-direction: column;
        height: 100%;
      }
    }

      @media(max-width: 550px){
        .logo_footer{
          width: 300px
        }
    }

    @media(max-width: 520px) {
      .card {
        width: 100%;
      }

      .clock_local--text {
        font-size: 18px;
      }

      card--title {
        font-size: 20px
      }

      .card--nums {
        font-size: 33px;
      }

      #animation_container {
        width: 300px;
        height: 300px;
      }
    }

    @media(max-width: 550px) {
      .logo {
        width: 170px;
      }

      .sol_logo {
        width: 106px;
      }
    }

  @media(max-width: 400px){
    .clock_local--text {
        font-size: 13px;
      }
  }

     @media(max-width: 350px){
      #main_container{
        padding: 30px 10px 30px 10px;
      } 
    }

  </style>

</head>

<body>

  <div id="weather-data-container">

    <div id="loadingScreem">
      <div id="animation_container"></div>
    </div>
    <script defer>
      let animdata = { "v": "4.8.0", "meta": { "g": "LottieFiles AE 3.5.1", "a": "", "k": "", "d": "", "tc": "" }, "fr": 25, "ip": 0, "op": 239, "w": 500, "h": 500, "nm": "Composição 1", "ddd": 0, "assets": [], "layers": [{ "ddd": 0, "ind": 1, "ty": 4, "nm": "Camada de forma 1", "sr": 1, "ks": { "o": { "a": 0, "k": 100, "ix": 11 }, "r": { "a": 0, "k": 0, "ix": 10 }, "p": { "a": 0, "k": [250, 250, 0], "ix": 2 }, "a": { "a": 0, "k": [0.5, -2.5, 0], "ix": 1 }, "s": { "a": 1, "k": [{ "i": { "x": [0.667, 0.667, 0.667], "y": [1, 1, 1] }, "o": { "x": [0.333, 0.333, 0.333], "y": [0, 0, 0] }, "t": 0, "s": [100, 100, 100] }, { "i": { "x": [0.833, 0.833, 0.833], "y": [1, 1, 1] }, "o": { "x": [0.167, 0.167, 0.167], "y": [0, 0, 0] }, "t": 44, "s": [105, 105, 100] }, { "i": { "x": [0.833, 0.833, 0.833], "y": [1, 1, 1] }, "o": { "x": [0.167, 0.167, 0.167], "y": [0, 0, 0] }, "t": 74, "s": [100, 100, 100] }, { "i": { "x": [0.833, 0.833, 0.833], "y": [1, 1, 1] }, "o": { "x": [0.167, 0.167, 0.167], "y": [0, 0, 0] }, "t": 104, "s": [105, 105, 100] }, { "i": { "x": [0.833, 0.833, 0.833], "y": [1, 1, 1] }, "o": { "x": [0.167, 0.167, 0.167], "y": [0, 0, 0] }, "t": 129, "s": [100, 100, 100] }, { "i": { "x": [0.833, 0.833, 0.833], "y": [1, 1, 1] }, "o": { "x": [0.167, 0.167, 0.167], "y": [0, 0, 0] }, "t": 160, "s": [105, 105, 100] }, { "i": { "x": [0.833, 0.833, 0.833], "y": [1, 1, 1] }, "o": { "x": [0.167, 0.167, 0.167], "y": [0, 0, 0] }, "t": 190, "s": [100, 100, 100] }, { "i": { "x": [0.833, 0.833, 0.833], "y": [1, 1, 1] }, "o": { "x": [0.167, 0.167, 0.167], "y": [0, 0, 0] }, "t": 219, "s": [105, 105, 100] }, { "t": 239, "s": [100, 100, 100] }], "ix": 6 } }, "ao": 0, "shapes": [{ "ty": "gr", "it": [{ "d": 1, "ty": "el", "s": { "a": 0, "k": [219, 219], "ix": 2 }, "p": { "a": 0, "k": [0, 0], "ix": 3 }, "nm": "Caminho da elipse 1", "mn": "ADBE Vector Shape - Ellipse", "hd": false }, { "ty": "gf", "o": { "a": 0, "k": 100, "ix": 10 }, "r": 1, "bm": 0, "g": { "p": 3, "k": { "a": 0, "k": [0, 0.992, 0.761, 0.208, 0.5, 0.994, 0.804, 0.176, 1, 0.996, 0.846, 0.145], "ix": 9 } }, "s": { "a": 0, "k": [0, 0], "ix": 5 }, "e": { "a": 0, "k": [100, 0], "ix": 6 }, "t": 2, "h": { "a": 0, "k": 0, "ix": 7 }, "a": { "a": 0, "k": 0, "ix": 8 }, "nm": "Preenchimento de gradiente 1", "mn": "ADBE Vector Graphic - G-Fill", "hd": false }, { "ty": "tr", "p": { "a": 0, "k": [0.5, -2.5], "ix": 2 }, "a": { "a": 0, "k": [0, 0], "ix": 1 }, "s": { "a": 0, "k": [100, 100], "ix": 3 }, "r": { "a": 0, "k": 0, "ix": 6 }, "o": { "a": 0, "k": 100, "ix": 7 }, "sk": { "a": 0, "k": 0, "ix": 4 }, "sa": { "a": 0, "k": 0, "ix": 5 }, "nm": "Transformar" }], "nm": "Elipse 1", "np": 3, "cix": 2, "bm": 0, "ix": 1, "mn": "ADBE Vector Group", "hd": false }], "ip": 0, "op": 250, "st": 0, "bm": 0 }, { "ddd": 0, "ind": 2, "ty": 4, "nm": "Camada de forma 13", "sr": 1, "ks": { "o": { "a": 0, "k": 100, "ix": 11 }, "r": { "a": 0, "k": 240, "ix": 10 }, "p": { "a": 1, "k": [{ "i": { "x": 0.667, "y": 1 }, "o": { "x": 0.333, "y": 0 }, "t": 114, "s": [250, 250, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "i": { "x": 0.667, "y": 0.667 }, "o": { "x": 0.333, "y": 0.333 }, "t": 119, "s": [172.033, 113.726, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "i": { "x": 0.667, "y": 1 }, "o": { "x": 0.333, "y": 0 }, "t": 232, "s": [172.033, 113.726, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "t": 238, "s": [250, 250, 0] }], "ix": 2 }, "a": { "a": 0, "k": [157.5, -0.25, 0], "ix": 1 }, "s": { "a": 0, "k": [100, 100, 100], "ix": 6 } }, "ao": 0, "shapes": [{ "ty": "gr", "it": [{ "ty": "rc", "d": 1, "s": { "a": 0, "k": [56, 25.5], "ix": 2 }, "p": { "a": 0, "k": [0, 0], "ix": 3 }, "r": { "a": 0, "k": 643, "ix": 4 }, "nm": "Caminho do retângulo 1", "mn": "ADBE Vector Shape - Rect", "hd": false }, { "ty": "gf", "o": { "a": 0, "k": 100, "ix": 10 }, "r": 1, "bm": 0, "g": { "p": 3, "k": { "a": 0, "k": [0, 0.992, 0.761, 0.208, 0.5, 0.994, 0.804, 0.176, 1, 0.996, 0.846, 0.145], "ix": 9 } }, "s": { "a": 0, "k": [-28, 0], "ix": 5 }, "e": { "a": 0, "k": [47, 2], "ix": 6 }, "t": 2, "h": { "a": 0, "k": 0, "ix": 7 }, "a": { "a": 0, "k": 0, "ix": 8 }, "nm": "Preenchimento de gradiente 1", "mn": "ADBE Vector Graphic - G-Fill", "hd": false }, { "ty": "tr", "p": { "a": 0, "k": [157.5, -0.25], "ix": 2 }, "a": { "a": 0, "k": [0, 0], "ix": 1 }, "s": { "a": 0, "k": [100, 100], "ix": 3 }, "r": { "a": 0, "k": 0, "ix": 6 }, "o": { "a": 0, "k": 100, "ix": 7 }, "sk": { "a": 0, "k": 0, "ix": 4 }, "sa": { "a": 0, "k": 0, "ix": 5 }, "nm": "Transformar" }], "nm": "Retângulo 1", "np": 3, "cix": 2, "bm": 0, "ix": 1, "mn": "ADBE Vector Group", "hd": false }], "ip": 114, "op": 239, "st": 114, "bm": 0 }, { "ddd": 0, "ind": 3, "ty": 4, "nm": "Camada de forma 12", "sr": 1, "ks": { "o": { "a": 0, "k": 100, "ix": 11 }, "r": { "a": 0, "k": 210, "ix": 10 }, "p": { "a": 1, "k": [{ "i": { "x": 0.667, "y": 1 }, "o": { "x": 0.333, "y": 0 }, "t": 104, "s": [250, 250, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "i": { "x": 0.667, "y": 0.667 }, "o": { "x": 0.333, "y": 0.333 }, "t": 109, "s": [114.476, 171.467, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "i": { "x": 0.667, "y": 1 }, "o": { "x": 0.333, "y": 0 }, "t": 221, "s": [114.476, 171.467, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "t": 227, "s": [250, 250, 0] }], "ix": 2 }, "a": { "a": 0, "k": [157.5, -0.25, 0], "ix": 1 }, "s": { "a": 0, "k": [100, 100, 100], "ix": 6 } }, "ao": 0, "shapes": [{ "ty": "gr", "it": [{ "ty": "rc", "d": 1, "s": { "a": 0, "k": [56, 25.5], "ix": 2 }, "p": { "a": 0, "k": [0, 0], "ix": 3 }, "r": { "a": 0, "k": 643, "ix": 4 }, "nm": "Caminho do retângulo 1", "mn": "ADBE Vector Shape - Rect", "hd": false }, { "ty": "gf", "o": { "a": 0, "k": 100, "ix": 10 }, "r": 1, "bm": 0, "g": { "p": 3, "k": { "a": 0, "k": [0, 0.992, 0.761, 0.208, 0.5, 0.994, 0.804, 0.176, 1, 0.996, 0.846, 0.145], "ix": 9 } }, "s": { "a": 0, "k": [-28, 0], "ix": 5 }, "e": { "a": 0, "k": [47, 2], "ix": 6 }, "t": 2, "h": { "a": 0, "k": 0, "ix": 7 }, "a": { "a": 0, "k": 0, "ix": 8 }, "nm": "Preenchimento de gradiente 1", "mn": "ADBE Vector Graphic - G-Fill", "hd": false }, { "ty": "tr", "p": { "a": 0, "k": [157.5, -0.25], "ix": 2 }, "a": { "a": 0, "k": [0, 0], "ix": 1 }, "s": { "a": 0, "k": [100, 100], "ix": 3 }, "r": { "a": 0, "k": 0, "ix": 6 }, "o": { "a": 0, "k": 100, "ix": 7 }, "sk": { "a": 0, "k": 0, "ix": 4 }, "sa": { "a": 0, "k": 0, "ix": 5 }, "nm": "Transformar" }], "nm": "Retângulo 1", "np": 3, "cix": 2, "bm": 0, "ix": 1, "mn": "ADBE Vector Group", "hd": false }], "ip": 104, "op": 229, "st": 104, "bm": 0 }, { "ddd": 0, "ind": 4, "ty": 4, "nm": "Camada de forma 11", "sr": 1, "ks": { "o": { "a": 0, "k": 100, "ix": 11 }, "r": { "a": 0, "k": 180, "ix": 10 }, "p": { "a": 1, "k": [{ "i": { "x": 0.667, "y": 1 }, "o": { "x": 0.333, "y": 0 }, "t": 94, "s": [250, 250, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "i": { "x": 0.667, "y": 0.667 }, "o": { "x": 0.333, "y": 0.333 }, "t": 99, "s": [93.5, 250.25, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "i": { "x": 0.667, "y": 1 }, "o": { "x": 0.333, "y": 0 }, "t": 212, "s": [93.5, 250.25, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "t": 218, "s": [250, 250, 0] }], "ix": 2 }, "a": { "a": 0, "k": [157.5, -0.25, 0], "ix": 1 }, "s": { "a": 0, "k": [100, 100, 100], "ix": 6 } }, "ao": 0, "shapes": [{ "ty": "gr", "it": [{ "ty": "rc", "d": 1, "s": { "a": 0, "k": [56, 25.5], "ix": 2 }, "p": { "a": 0, "k": [0, 0], "ix": 3 }, "r": { "a": 0, "k": 643, "ix": 4 }, "nm": "Caminho do retângulo 1", "mn": "ADBE Vector Shape - Rect", "hd": false }, { "ty": "gf", "o": { "a": 0, "k": 100, "ix": 10 }, "r": 1, "bm": 0, "g": { "p": 3, "k": { "a": 0, "k": [0, 0.992, 0.761, 0.208, 0.5, 0.994, 0.804, 0.176, 1, 0.996, 0.846, 0.145], "ix": 9 } }, "s": { "a": 0, "k": [-28, 0], "ix": 5 }, "e": { "a": 0, "k": [47, 2], "ix": 6 }, "t": 2, "h": { "a": 0, "k": 0, "ix": 7 }, "a": { "a": 0, "k": 0, "ix": 8 }, "nm": "Preenchimento de gradiente 1", "mn": "ADBE Vector Graphic - G-Fill", "hd": false }, { "ty": "tr", "p": { "a": 0, "k": [157.5, -0.25], "ix": 2 }, "a": { "a": 0, "k": [0, 0], "ix": 1 }, "s": { "a": 0, "k": [100, 100], "ix": 3 }, "r": { "a": 0, "k": 0, "ix": 6 }, "o": { "a": 0, "k": 100, "ix": 7 }, "sk": { "a": 0, "k": 0, "ix": 4 }, "sa": { "a": 0, "k": 0, "ix": 5 }, "nm": "Transformar" }], "nm": "Retângulo 1", "np": 3, "cix": 2, "bm": 0, "ix": 1, "mn": "ADBE Vector Group", "hd": false }], "ip": 94, "op": 219, "st": 94, "bm": 0 }, { "ddd": 0, "ind": 5, "ty": 4, "nm": "Camada de forma 10", "sr": 1, "ks": { "o": { "a": 0, "k": 100, "ix": 11 }, "r": { "a": 0, "k": 150, "ix": 10 }, "p": { "a": 1, "k": [{ "i": { "x": 0.667, "y": 1 }, "o": { "x": 0.333, "y": 0 }, "t": 84, "s": [250, 250, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "i": { "x": 0.667, "y": 0.667 }, "o": { "x": 0.333, "y": 0.333 }, "t": 89, "s": [114.726, 328.967, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "i": { "x": 0.667, "y": 1 }, "o": { "x": 0.333, "y": 0 }, "t": 202, "s": [114.726, 328.967, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "t": 208, "s": [250, 250, 0] }], "ix": 2 }, "a": { "a": 0, "k": [157.5, -0.25, 0], "ix": 1 }, "s": { "a": 0, "k": [100, 100, 100], "ix": 6 } }, "ao": 0, "shapes": [{ "ty": "gr", "it": [{ "ty": "rc", "d": 1, "s": { "a": 0, "k": [56, 25.5], "ix": 2 }, "p": { "a": 0, "k": [0, 0], "ix": 3 }, "r": { "a": 0, "k": 643, "ix": 4 }, "nm": "Caminho do retângulo 1", "mn": "ADBE Vector Shape - Rect", "hd": false }, { "ty": "gf", "o": { "a": 0, "k": 100, "ix": 10 }, "r": 1, "bm": 0, "g": { "p": 3, "k": { "a": 0, "k": [0, 0.992, 0.761, 0.208, 0.5, 0.994, 0.804, 0.176, 1, 0.996, 0.846, 0.145], "ix": 9 } }, "s": { "a": 0, "k": [-28, 0], "ix": 5 }, "e": { "a": 0, "k": [47, 2], "ix": 6 }, "t": 2, "h": { "a": 0, "k": 0, "ix": 7 }, "a": { "a": 0, "k": 0, "ix": 8 }, "nm": "Preenchimento de gradiente 1", "mn": "ADBE Vector Graphic - G-Fill", "hd": false }, { "ty": "tr", "p": { "a": 0, "k": [157.5, -0.25], "ix": 2 }, "a": { "a": 0, "k": [0, 0], "ix": 1 }, "s": { "a": 0, "k": [100, 100], "ix": 3 }, "r": { "a": 0, "k": 0, "ix": 6 }, "o": { "a": 0, "k": 100, "ix": 7 }, "sk": { "a": 0, "k": 0, "ix": 4 }, "sa": { "a": 0, "k": 0, "ix": 5 }, "nm": "Transformar" }], "nm": "Retângulo 1", "np": 3, "cix": 2, "bm": 0, "ix": 1, "mn": "ADBE Vector Group", "hd": false }], "ip": 84, "op": 209, "st": 84, "bm": 0 }, { "ddd": 0, "ind": 6, "ty": 4, "nm": "Camada de forma 9", "sr": 1, "ks": { "o": { "a": 0, "k": 100, "ix": 11 }, "r": { "a": 0, "k": 120, "ix": 10 }, "p": { "a": 1, "k": [{ "i": { "x": 0.667, "y": 1 }, "o": { "x": 0.333, "y": 0 }, "t": 74, "s": [250, 250, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "i": { "x": 0.667, "y": 0.667 }, "o": { "x": 0.333, "y": 0.333 }, "t": 79, "s": [172.467, 386.524, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "i": { "x": 0.667, "y": 1 }, "o": { "x": 0.333, "y": 0 }, "t": 192, "s": [172.467, 386.524, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "t": 198, "s": [250, 250, 0] }], "ix": 2 }, "a": { "a": 0, "k": [157.5, -0.25, 0], "ix": 1 }, "s": { "a": 0, "k": [100, 100, 100], "ix": 6 } }, "ao": 0, "shapes": [{ "ty": "gr", "it": [{ "ty": "rc", "d": 1, "s": { "a": 0, "k": [56, 25.5], "ix": 2 }, "p": { "a": 0, "k": [0, 0], "ix": 3 }, "r": { "a": 0, "k": 643, "ix": 4 }, "nm": "Caminho do retângulo 1", "mn": "ADBE Vector Shape - Rect", "hd": false }, { "ty": "gf", "o": { "a": 0, "k": 100, "ix": 10 }, "r": 1, "bm": 0, "g": { "p": 3, "k": { "a": 0, "k": [0, 0.992, 0.761, 0.208, 0.5, 0.994, 0.804, 0.176, 1, 0.996, 0.846, 0.145], "ix": 9 } }, "s": { "a": 0, "k": [-28, 0], "ix": 5 }, "e": { "a": 0, "k": [47, 2], "ix": 6 }, "t": 2, "h": { "a": 0, "k": 0, "ix": 7 }, "a": { "a": 0, "k": 0, "ix": 8 }, "nm": "Preenchimento de gradiente 1", "mn": "ADBE Vector Graphic - G-Fill", "hd": false }, { "ty": "tr", "p": { "a": 0, "k": [157.5, -0.25], "ix": 2 }, "a": { "a": 0, "k": [0, 0], "ix": 1 }, "s": { "a": 0, "k": [100, 100], "ix": 3 }, "r": { "a": 0, "k": 0, "ix": 6 }, "o": { "a": 0, "k": 100, "ix": 7 }, "sk": { "a": 0, "k": 0, "ix": 4 }, "sa": { "a": 0, "k": 0, "ix": 5 }, "nm": "Transformar" }], "nm": "Retângulo 1", "np": 3, "cix": 2, "bm": 0, "ix": 1, "mn": "ADBE Vector Group", "hd": false }], "ip": 74, "op": 199, "st": 74, "bm": 0 }, { "ddd": 0, "ind": 7, "ty": 4, "nm": "Camada de forma 8", "sr": 1, "ks": { "o": { "a": 0, "k": 100, "ix": 11 }, "r": { "a": 0, "k": 90, "ix": 10 }, "p": { "a": 1, "k": [{ "i": { "x": 0.667, "y": 1 }, "o": { "x": 0.333, "y": 0 }, "t": 64, "s": [250, 250, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "i": { "x": 0.667, "y": 0.667 }, "o": { "x": 0.333, "y": 0.333 }, "t": 69, "s": [251.25, 407.5, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "i": { "x": 0.667, "y": 1 }, "o": { "x": 0.333, "y": 0 }, "t": 182, "s": [251.25, 407.5, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "t": 188, "s": [250, 250, 0] }], "ix": 2 }, "a": { "a": 0, "k": [157.5, -0.25, 0], "ix": 1 }, "s": { "a": 0, "k": [100, 100, 100], "ix": 6 } }, "ao": 0, "shapes": [{ "ty": "gr", "it": [{ "ty": "rc", "d": 1, "s": { "a": 0, "k": [56, 25.5], "ix": 2 }, "p": { "a": 0, "k": [0, 0], "ix": 3 }, "r": { "a": 0, "k": 643, "ix": 4 }, "nm": "Caminho do retângulo 1", "mn": "ADBE Vector Shape - Rect", "hd": false }, { "ty": "gf", "o": { "a": 0, "k": 100, "ix": 10 }, "r": 1, "bm": 0, "g": { "p": 3, "k": { "a": 0, "k": [0, 0.992, 0.761, 0.208, 0.5, 0.994, 0.804, 0.176, 1, 0.996, 0.846, 0.145], "ix": 9 } }, "s": { "a": 0, "k": [-28, 0], "ix": 5 }, "e": { "a": 0, "k": [47, 2], "ix": 6 }, "t": 2, "h": { "a": 0, "k": 0, "ix": 7 }, "a": { "a": 0, "k": 0, "ix": 8 }, "nm": "Preenchimento de gradiente 1", "mn": "ADBE Vector Graphic - G-Fill", "hd": false }, { "ty": "tr", "p": { "a": 0, "k": [157.5, -0.25], "ix": 2 }, "a": { "a": 0, "k": [0, 0], "ix": 1 }, "s": { "a": 0, "k": [100, 100], "ix": 3 }, "r": { "a": 0, "k": 0, "ix": 6 }, "o": { "a": 0, "k": 100, "ix": 7 }, "sk": { "a": 0, "k": 0, "ix": 4 }, "sa": { "a": 0, "k": 0, "ix": 5 }, "nm": "Transformar" }], "nm": "Retângulo 1", "np": 3, "cix": 2, "bm": 0, "ix": 1, "mn": "ADBE Vector Group", "hd": false }], "ip": 64, "op": 189, "st": 64, "bm": 0 }, { "ddd": 0, "ind": 8, "ty": 4, "nm": "Camada de forma 7", "sr": 1, "ks": { "o": { "a": 0, "k": 100, "ix": 11 }, "r": { "a": 0, "k": 60, "ix": 10 }, "p": { "a": 1, "k": [{ "i": { "x": 0.667, "y": 1 }, "o": { "x": 0.333, "y": 0 }, "t": 54, "s": [250, 250, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "i": { "x": 0.667, "y": 0.667 }, "o": { "x": 0.333, "y": 0.333 }, "t": 59, "s": [329.967, 386.274, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "i": { "x": 0.667, "y": 1 }, "o": { "x": 0.333, "y": 0 }, "t": 172, "s": [329.967, 386.274, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "t": 178, "s": [250, 250, 0] }], "ix": 2 }, "a": { "a": 0, "k": [157.5, -0.25, 0], "ix": 1 }, "s": { "a": 0, "k": [100, 100, 100], "ix": 6 } }, "ao": 0, "shapes": [{ "ty": "gr", "it": [{ "ty": "rc", "d": 1, "s": { "a": 0, "k": [56, 25.5], "ix": 2 }, "p": { "a": 0, "k": [0, 0], "ix": 3 }, "r": { "a": 0, "k": 643, "ix": 4 }, "nm": "Caminho do retângulo 1", "mn": "ADBE Vector Shape - Rect", "hd": false }, { "ty": "gf", "o": { "a": 0, "k": 100, "ix": 10 }, "r": 1, "bm": 0, "g": { "p": 3, "k": { "a": 0, "k": [0, 0.992, 0.761, 0.208, 0.5, 0.994, 0.804, 0.176, 1, 0.996, 0.846, 0.145], "ix": 9 } }, "s": { "a": 0, "k": [-28, 0], "ix": 5 }, "e": { "a": 0, "k": [47, 2], "ix": 6 }, "t": 2, "h": { "a": 0, "k": 0, "ix": 7 }, "a": { "a": 0, "k": 0, "ix": 8 }, "nm": "Preenchimento de gradiente 1", "mn": "ADBE Vector Graphic - G-Fill", "hd": false }, { "ty": "tr", "p": { "a": 0, "k": [157.5, -0.25], "ix": 2 }, "a": { "a": 0, "k": [0, 0], "ix": 1 }, "s": { "a": 0, "k": [100, 100], "ix": 3 }, "r": { "a": 0, "k": 0, "ix": 6 }, "o": { "a": 0, "k": 100, "ix": 7 }, "sk": { "a": 0, "k": 0, "ix": 4 }, "sa": { "a": 0, "k": 0, "ix": 5 }, "nm": "Transformar" }], "nm": "Retângulo 1", "np": 3, "cix": 2, "bm": 0, "ix": 1, "mn": "ADBE Vector Group", "hd": false }], "ip": 54, "op": 179, "st": 54, "bm": 0 }, { "ddd": 0, "ind": 9, "ty": 4, "nm": "Camada de forma 6", "sr": 1, "ks": { "o": { "a": 0, "k": 100, "ix": 11 }, "r": { "a": 0, "k": 30, "ix": 10 }, "p": { "a": 1, "k": [{ "i": { "x": 0.667, "y": 1 }, "o": { "x": 0.333, "y": 0 }, "t": 44, "s": [250, 250, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "i": { "x": 0.667, "y": 0.667 }, "o": { "x": 0.333, "y": 0.333 }, "t": 49, "s": [387.524, 328.533, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "i": { "x": 0.667, "y": 1 }, "o": { "x": 0.333, "y": 0 }, "t": 162, "s": [387.524, 328.533, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "t": 168, "s": [250, 250, 0] }], "ix": 2 }, "a": { "a": 0, "k": [157.5, -0.25, 0], "ix": 1 }, "s": { "a": 0, "k": [100, 100, 100], "ix": 6 } }, "ao": 0, "shapes": [{ "ty": "gr", "it": [{ "ty": "rc", "d": 1, "s": { "a": 0, "k": [56, 25.5], "ix": 2 }, "p": { "a": 0, "k": [0, 0], "ix": 3 }, "r": { "a": 0, "k": 643, "ix": 4 }, "nm": "Caminho do retângulo 1", "mn": "ADBE Vector Shape - Rect", "hd": false }, { "ty": "gf", "o": { "a": 0, "k": 100, "ix": 10 }, "r": 1, "bm": 0, "g": { "p": 3, "k": { "a": 0, "k": [0, 0.992, 0.761, 0.208, 0.5, 0.994, 0.804, 0.176, 1, 0.996, 0.846, 0.145], "ix": 9 } }, "s": { "a": 0, "k": [-28, 0], "ix": 5 }, "e": { "a": 0, "k": [47, 2], "ix": 6 }, "t": 2, "h": { "a": 0, "k": 0, "ix": 7 }, "a": { "a": 0, "k": 0, "ix": 8 }, "nm": "Preenchimento de gradiente 1", "mn": "ADBE Vector Graphic - G-Fill", "hd": false }, { "ty": "tr", "p": { "a": 0, "k": [157.5, -0.25], "ix": 2 }, "a": { "a": 0, "k": [0, 0], "ix": 1 }, "s": { "a": 0, "k": [100, 100], "ix": 3 }, "r": { "a": 0, "k": 0, "ix": 6 }, "o": { "a": 0, "k": 100, "ix": 7 }, "sk": { "a": 0, "k": 0, "ix": 4 }, "sa": { "a": 0, "k": 0, "ix": 5 }, "nm": "Transformar" }], "nm": "Retângulo 1", "np": 3, "cix": 2, "bm": 0, "ix": 1, "mn": "ADBE Vector Group", "hd": false }], "ip": 44, "op": 169, "st": 44, "bm": 0 }, { "ddd": 0, "ind": 10, "ty": 4, "nm": "Camada de forma 5", "sr": 1, "ks": { "o": { "a": 0, "k": 100, "ix": 11 }, "r": { "a": 0, "k": 0, "ix": 10 }, "p": { "a": 1, "k": [{ "i": { "x": 0.667, "y": 1 }, "o": { "x": 0.333, "y": 0 }, "t": 34, "s": [250, 250, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "i": { "x": 0.667, "y": 0.667 }, "o": { "x": 0.333, "y": 0.333 }, "t": 39, "s": [408.5, 249.75, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "i": { "x": 0.667, "y": 1 }, "o": { "x": 0.333, "y": 0 }, "t": 152, "s": [408.5, 249.75, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "t": 159, "s": [250, 250, 0] }], "ix": 2 }, "a": { "a": 0, "k": [157.5, -0.25, 0], "ix": 1 }, "s": { "a": 0, "k": [100, 100, 100], "ix": 6 } }, "ao": 0, "shapes": [{ "ty": "gr", "it": [{ "ty": "rc", "d": 1, "s": { "a": 0, "k": [56, 25.5], "ix": 2 }, "p": { "a": 0, "k": [0, 0], "ix": 3 }, "r": { "a": 0, "k": 643, "ix": 4 }, "nm": "Caminho do retângulo 1", "mn": "ADBE Vector Shape - Rect", "hd": false }, { "ty": "gf", "o": { "a": 0, "k": 100, "ix": 10 }, "r": 1, "bm": 0, "g": { "p": 3, "k": { "a": 0, "k": [0, 0.992, 0.761, 0.208, 0.5, 0.994, 0.804, 0.176, 1, 0.996, 0.846, 0.145], "ix": 9 } }, "s": { "a": 0, "k": [-28, 0], "ix": 5 }, "e": { "a": 0, "k": [47, 2], "ix": 6 }, "t": 2, "h": { "a": 0, "k": 0, "ix": 7 }, "a": { "a": 0, "k": 0, "ix": 8 }, "nm": "Preenchimento de gradiente 1", "mn": "ADBE Vector Graphic - G-Fill", "hd": false }, { "ty": "tr", "p": { "a": 0, "k": [157.5, -0.25], "ix": 2 }, "a": { "a": 0, "k": [0, 0], "ix": 1 }, "s": { "a": 0, "k": [100, 100], "ix": 3 }, "r": { "a": 0, "k": 0, "ix": 6 }, "o": { "a": 0, "k": 100, "ix": 7 }, "sk": { "a": 0, "k": 0, "ix": 4 }, "sa": { "a": 0, "k": 0, "ix": 5 }, "nm": "Transformar" }], "nm": "Retângulo 1", "np": 3, "cix": 2, "bm": 0, "ix": 1, "mn": "ADBE Vector Group", "hd": false }], "ip": 34, "op": 159, "st": 34, "bm": 0 }, { "ddd": 0, "ind": 11, "ty": 4, "nm": "Camada de forma 4", "sr": 1, "ks": { "o": { "a": 0, "k": 100, "ix": 11 }, "r": { "a": 0, "k": -30, "ix": 10 }, "p": { "a": 1, "k": [{ "i": { "x": 0.667, "y": 1 }, "o": { "x": 0.333, "y": 0 }, "t": 24, "s": [250, 250, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "i": { "x": 0.667, "y": 0.667 }, "o": { "x": 0.333, "y": 0.333 }, "t": 29, "s": [386.274, 171.033, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "i": { "x": 0.667, "y": 1 }, "o": { "x": 0.333, "y": 0 }, "t": 141, "s": [386.274, 171.033, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "t": 148, "s": [250, 250, 0] }], "ix": 2 }, "a": { "a": 0, "k": [157.5, -0.25, 0], "ix": 1 }, "s": { "a": 0, "k": [100, 100, 100], "ix": 6 } }, "ao": 0, "shapes": [{ "ty": "gr", "it": [{ "ty": "rc", "d": 1, "s": { "a": 0, "k": [56, 25.5], "ix": 2 }, "p": { "a": 0, "k": [0, 0], "ix": 3 }, "r": { "a": 0, "k": 643, "ix": 4 }, "nm": "Caminho do retângulo 1", "mn": "ADBE Vector Shape - Rect", "hd": false }, { "ty": "gf", "o": { "a": 0, "k": 100, "ix": 10 }, "r": 1, "bm": 0, "g": { "p": 3, "k": { "a": 0, "k": [0, 0.992, 0.761, 0.208, 0.5, 0.994, 0.804, 0.176, 1, 0.996, 0.846, 0.145], "ix": 9 } }, "s": { "a": 0, "k": [-28, 0], "ix": 5 }, "e": { "a": 0, "k": [47, 2], "ix": 6 }, "t": 2, "h": { "a": 0, "k": 0, "ix": 7 }, "a": { "a": 0, "k": 0, "ix": 8 }, "nm": "Preenchimento de gradiente 1", "mn": "ADBE Vector Graphic - G-Fill", "hd": false }, { "ty": "tr", "p": { "a": 0, "k": [157.5, -0.25], "ix": 2 }, "a": { "a": 0, "k": [0, 0], "ix": 1 }, "s": { "a": 0, "k": [100, 100], "ix": 3 }, "r": { "a": 0, "k": 0, "ix": 6 }, "o": { "a": 0, "k": 100, "ix": 7 }, "sk": { "a": 0, "k": 0, "ix": 4 }, "sa": { "a": 0, "k": 0, "ix": 5 }, "nm": "Transformar" }], "nm": "Retângulo 1", "np": 3, "cix": 2, "bm": 0, "ix": 1, "mn": "ADBE Vector Group", "hd": false }], "ip": 24, "op": 149, "st": 24, "bm": 0 }, { "ddd": 0, "ind": 12, "ty": 4, "nm": "Camada de forma 3", "sr": 1, "ks": { "o": { "a": 0, "k": 100, "ix": 11 }, "r": { "a": 0, "k": -60, "ix": 10 }, "p": { "a": 1, "k": [{ "i": { "x": 0.667, "y": 1 }, "o": { "x": 0.333, "y": 0 }, "t": 14, "s": [250, 250, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "i": { "x": 0.667, "y": 0.667 }, "o": { "x": 0.333, "y": 0.333 }, "t": 19, "s": [328.533, 113.476, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "i": { "x": 0.667, "y": 1 }, "o": { "x": 0.333, "y": 0 }, "t": 132, "s": [328.533, 113.476, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "t": 139, "s": [250, 250, 0] }], "ix": 2 }, "a": { "a": 0, "k": [157.5, -0.25, 0], "ix": 1 }, "s": { "a": 0, "k": [100, 100, 100], "ix": 6 } }, "ao": 0, "shapes": [{ "ty": "gr", "it": [{ "ty": "rc", "d": 1, "s": { "a": 0, "k": [56, 25.5], "ix": 2 }, "p": { "a": 0, "k": [0, 0], "ix": 3 }, "r": { "a": 0, "k": 643, "ix": 4 }, "nm": "Caminho do retângulo 1", "mn": "ADBE Vector Shape - Rect", "hd": false }, { "ty": "gf", "o": { "a": 0, "k": 100, "ix": 10 }, "r": 1, "bm": 0, "g": { "p": 3, "k": { "a": 0, "k": [0, 0.992, 0.761, 0.208, 0.5, 0.994, 0.804, 0.176, 1, 0.996, 0.846, 0.145], "ix": 9 } }, "s": { "a": 0, "k": [-28, 0], "ix": 5 }, "e": { "a": 0, "k": [47, 2], "ix": 6 }, "t": 2, "h": { "a": 0, "k": 0, "ix": 7 }, "a": { "a": 0, "k": 0, "ix": 8 }, "nm": "Preenchimento de gradiente 1", "mn": "ADBE Vector Graphic - G-Fill", "hd": false }, { "ty": "tr", "p": { "a": 0, "k": [157.5, -0.25], "ix": 2 }, "a": { "a": 0, "k": [0, 0], "ix": 1 }, "s": { "a": 0, "k": [100, 100], "ix": 3 }, "r": { "a": 0, "k": 0, "ix": 6 }, "o": { "a": 0, "k": 100, "ix": 7 }, "sk": { "a": 0, "k": 0, "ix": 4 }, "sa": { "a": 0, "k": 0, "ix": 5 }, "nm": "Transformar" }], "nm": "Retângulo 1", "np": 3, "cix": 2, "bm": 0, "ix": 1, "mn": "ADBE Vector Group", "hd": false }], "ip": 14, "op": 139, "st": 14, "bm": 0 }, { "ddd": 0, "ind": 13, "ty": 4, "nm": "Camada de forma 2", "sr": 1, "ks": { "o": { "a": 0, "k": 100, "ix": 11 }, "r": { "a": 0, "k": -90, "ix": 10 }, "p": { "a": 1, "k": [{ "i": { "x": 0.667, "y": 1 }, "o": { "x": 0.333, "y": 0 }, "t": 4, "s": [250, 250, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "i": { "x": 0.667, "y": 0.667 }, "o": { "x": 0.333, "y": 0.333 }, "t": 9, "s": [248.75, 92.5, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "i": { "x": 0.667, "y": 1 }, "o": { "x": 0.167, "y": 0 }, "t": 124, "s": [248.75, 92.5, 0], "to": [0, 0, 0], "ti": [0, 0, 0] }, { "t": 129, "s": [250, 250, 0] }], "ix": 2 }, "a": { "a": 0, "k": [157.5, -0.25, 0], "ix": 1 }, "s": { "a": 0, "k": [100, 100, 100], "ix": 6 } }, "ao": 0, "shapes": [{ "ty": "gr", "it": [{ "ty": "rc", "d": 1, "s": { "a": 0, "k": [56, 25.5], "ix": 2 }, "p": { "a": 0, "k": [0, 0], "ix": 3 }, "r": { "a": 0, "k": 643, "ix": 4 }, "nm": "Caminho do retângulo 1", "mn": "ADBE Vector Shape - Rect", "hd": false }, { "ty": "gf", "o": { "a": 0, "k": 100, "ix": 10 }, "r": 1, "bm": 0, "g": { "p": 3, "k": { "a": 0, "k": [0, 0.992, 0.761, 0.208, 0.5, 0.994, 0.804, 0.176, 1, 0.996, 0.846, 0.145], "ix": 9 } }, "s": { "a": 0, "k": [-28, 0], "ix": 5 }, "e": { "a": 0, "k": [47, 2], "ix": 6 }, "t": 2, "h": { "a": 0, "k": 0, "ix": 7 }, "a": { "a": 0, "k": 0, "ix": 8 }, "nm": "Preenchimento de gradiente 1", "mn": "ADBE Vector Graphic - G-Fill", "hd": false }, { "ty": "tr", "p": { "a": 0, "k": [157.5, -0.25], "ix": 2 }, "a": { "a": 0, "k": [0, 0], "ix": 1 }, "s": { "a": 0, "k": [100, 100], "ix": 3 }, "r": { "a": 0, "k": 0, "ix": 6 }, "o": { "a": 0, "k": 100, "ix": 7 }, "sk": { "a": 0, "k": 0, "ix": 4 }, "sa": { "a": 0, "k": 0, "ix": 5 }, "nm": "Transformar" }], "nm": "Retângulo 1", "np": 3, "cix": 2, "bm": 0, "ix": 1, "mn": "ADBE Vector Group", "hd": false }], "ip": 4, "op": 129, "st": 4, "bm": 0 }], "markers": [] };
      bodymovin.loadAnimation({
        container: document.getElementById('animation_container'),
        animationData: animdata
      })
    </script>

    <main class="main_container" id="main_container">
      <header>
        <svg class="logo" width="337" height="121" viewBox="0 0 337 121" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M32.324 76.9884L41.9084 97.3702L30.2624 108.401L11.1391 101.06L1.45788 82.9736L10.9113 70.0065L32.324 76.9884ZM47.6716 61.0997L34.1691 76.2366L43.7137 96.6413L66.4589 104.739L82.7746 92.0626L73.7027 68.7137L47.6716 61.0997ZM10.6551 28.3828L0 46.3501L10.8885 68.0759L32.4606 75.0066L45.9574 59.5337L35.1771 34.4763L10.6551 28.3828ZM53.6227 11.6514L37.4892 33.5993L48.2183 58.7876L74.6025 66.3219L94.4604 47.6656L84.4546 17.9157L53.6227 11.6514Z" fill="white" />
          <path d="M116.92 59.2584H108.664L110.584 48.1224H118.84L119.416 44.9544C120.44 39.5144 122.776 35.4184 126.424 32.6664C130.072 29.8504 134.968 28.4424 141.112 28.4424H147.928L145.912 39.5784H139.288C137.496 39.5784 135.992 39.9944 134.776 40.8264C133.624 41.5944 132.856 43.0344 132.472 45.1464L131.896 48.1224H143.416L141.496 59.2584H129.976L123.448 96.0264H110.392L116.92 59.2584ZM159.919 43.6104C157.807 43.6104 156.111 43.0344 154.831 41.8824C153.551 40.7304 152.911 39.2264 152.911 37.3704C152.911 34.5544 153.775 32.2824 155.503 30.5544C157.295 28.7624 159.663 27.8664 162.607 27.8664C164.719 27.8664 166.415 28.4424 167.695 29.5944C168.975 30.7464 169.615 32.2504 169.615 34.1064C169.615 36.9224 168.719 39.2264 166.927 41.0184C165.199 42.7464 162.863 43.6104 159.919 43.6104ZM152.527 48.1224H165.583L157.135 96.0264H144.079L152.527 48.1224ZM188.152 96.7944C182.648 96.7944 178.264 95.5464 175 93.0504C171.8 90.5544 170.2 87.1944 170.2 82.9704C170.2 82.0104 170.296 81.0504 170.488 80.0904H183.352C183.288 80.3464 183.256 80.6984 183.256 81.1464C183.256 82.6184 183.736 83.7704 184.696 84.6024C185.656 85.4344 187 85.8504 188.728 85.8504H197.368C199.224 85.8504 200.696 85.5944 201.784 85.0824C202.872 84.5064 203.512 83.7064 203.704 82.6824L203.992 81.0504C204.12 80.4104 203.896 79.8344 203.32 79.3224C202.808 78.7464 202.04 78.3624 201.016 78.1704L184.888 75.2904C181.496 74.6504 178.84 73.4664 176.92 71.7384C175 69.9464 174.04 67.8024 174.04 65.3064C174.04 64.9224 174.104 64.3464 174.232 63.5784L174.808 60.4104C175.512 56.3144 177.624 53.1144 181.144 50.8104C184.728 48.5064 189.304 47.3544 194.872 47.3544H202.36C207.544 47.3544 211.64 48.5384 214.648 50.9064C217.72 53.2104 219.256 56.3144 219.256 60.2184C219.256 61.0504 219.16 61.9464 218.968 62.9064H206.104C206.168 62.7144 206.2 62.4264 206.2 62.0424C206.2 60.8904 205.784 59.9944 204.952 59.3544C204.184 58.6504 203.128 58.2984 201.784 58.2984H194.488C192.568 58.2984 191 58.5544 189.784 59.0664C188.632 59.5784 187.96 60.2824 187.768 61.1784L187.48 62.7144C187.352 63.3544 187.512 63.9304 187.96 64.4424C188.408 64.9544 189.144 65.3064 190.168 65.4984L207.064 68.6664C210.264 69.3064 212.76 70.5224 214.552 72.3144C216.408 74.0424 217.336 76.0584 217.336 78.3624C217.336 79.0024 217.304 79.4824 217.24 79.8024L216.664 83.2584C215.96 87.5464 213.848 90.8744 210.328 93.2424C206.872 95.6104 202.36 96.7944 196.792 96.7944H188.152ZM240.071 96.7944C235.399 96.7944 231.687 95.4824 228.935 92.8584C226.247 90.1704 224.903 86.6184 224.903 82.2024C224.903 81.3064 225.031 79.9624 225.287 78.1704L230.567 48.1224H243.623L238.343 78.3624C238.215 79.2584 238.151 79.8664 238.151 80.1864C238.151 81.7864 238.567 83.0664 239.399 84.0264C240.231 84.9864 241.383 85.4664 242.855 85.4664H248.423C250.599 85.4664 252.647 84.6024 254.567 82.8744C256.551 81.1464 258.183 78.8104 259.463 75.8664L264.359 48.1224H277.415L268.967 96.0264H256.871L257.927 89.8824C256.007 91.9944 253.991 93.6904 251.879 94.9704C249.831 96.1864 247.943 96.7944 246.215 96.7944H240.071ZM288.518 48.1224H300.614L299.558 53.8824C301.414 51.8344 303.43 50.2344 305.606 49.0824C307.782 47.9304 309.894 47.3544 311.942 47.3544H317.318C322.118 47.3544 325.894 48.6344 328.646 51.1944C331.462 53.6904 332.87 57.0504 332.87 61.2744C332.87 62.3624 332.774 63.5464 332.582 64.8264L327.11 96.0264H314.054L319.43 65.3064C319.494 64.9224 319.526 64.3784 319.526 63.6744C319.526 62.1384 319.11 60.9224 318.278 60.0264C317.51 59.1304 316.422 58.6824 315.014 58.6824H309.254C307.014 58.6824 304.838 59.5144 302.726 61.1784C300.678 62.7784 299.142 64.8904 298.118 67.5144L293.126 96.0264H280.07L288.518 48.1224Z" fill="white" />
        </svg>
        <svg class="sol_logo" xmlns="http://www.w3.org/2000/svg" width="148" height="147" viewBox="0 0 148 147" fill="none">
          <path d="M74.0142 116.372C97.8113 116.372 117.103 97.0809 117.103 73.2838C117.103 49.4867 97.8113 30.1953 74.0142 30.1953C50.2171 30.1953 30.9258 49.4867 30.9258 73.2838C30.9258 97.0809 50.2171 116.372 74.0142 116.372Z" fill="url(#paint0_linear_101_5284)" />
          <path fill-rule="evenodd" clip-rule="evenodd" d="M69.0236 5.02117V17.2085C69.0236 19.9656 71.2612 22.2033 74.0184 22.2033C76.7755 22.2033 79.0132 19.9656 79.0132 17.2085V5.02117C79.0132 2.26404 76.7755 0.0263672 74.0184 0.0263672C71.2612 0.0263672 69.0236 2.26404 69.0236 5.02117Z" fill="url(#paint1_linear_101_5284)" />
          <path fill-rule="evenodd" clip-rule="evenodd" d="M103.818 11.6662L97.7241 22.2218C96.3455 24.6127 97.1647 27.6695 99.5555 29.0481C101.94 30.4266 104.997 29.6075 106.375 27.2166L112.475 16.661C113.847 14.2768 113.028 11.22 110.644 9.8414C108.26 8.46284 105.196 9.28198 103.818 11.6662Z" fill="url(#paint2_linear_101_5284)" />
          <path fill-rule="evenodd" clip-rule="evenodd" d="M130.637 34.8221L120.081 40.9224C117.69 42.301 116.871 45.3578 118.25 47.742C119.628 50.1328 122.685 50.952 125.076 49.5734L135.632 43.4797C138.016 42.1012 138.835 39.0377 137.456 36.6535C136.078 34.2693 133.021 33.4502 130.637 34.8221Z" fill="url(#paint3_linear_101_5284)" />
          <path fill-rule="evenodd" clip-rule="evenodd" d="M142.281 68.2891H130.093C127.336 68.2891 125.099 70.5267 125.099 73.2839C125.099 76.041 127.336 78.2787 130.093 78.2787H142.281C145.038 78.2787 147.275 76.041 147.275 73.2839C147.275 70.5267 145.038 68.2891 142.281 68.2891Z" fill="url(#paint4_linear_101_5284)" />
          <path fill-rule="evenodd" clip-rule="evenodd" d="M135.632 103.089L125.076 96.9955C122.685 95.6169 119.628 96.436 118.25 98.8269C116.871 101.211 117.69 104.268 120.081 105.646L130.637 111.747C133.021 113.119 136.078 112.3 137.456 109.915C138.835 107.531 138.016 104.468 135.632 103.089Z" fill="url(#paint5_linear_101_5284)" />
          <path fill-rule="evenodd" clip-rule="evenodd" d="M112.475 129.902L106.375 119.346C104.997 116.956 101.94 116.136 99.5555 117.515C97.1647 118.894 96.3455 121.95 97.7241 124.341L103.818 134.897C105.196 137.281 108.26 138.1 110.644 136.722C113.028 135.343 113.847 132.286 112.475 129.902Z" fill="url(#paint6_linear_101_5284)" />
          <path fill-rule="evenodd" clip-rule="evenodd" d="M79.0132 141.546V129.359C79.0132 126.602 76.7755 124.364 74.0184 124.364C71.2612 124.364 69.0236 126.602 69.0236 129.359V141.546C69.0236 144.303 71.2612 146.541 74.0184 146.541C76.7755 146.541 79.0132 144.303 79.0132 141.546Z" fill="url(#paint7_linear_101_5284)" />
          <path fill-rule="evenodd" clip-rule="evenodd" d="M44.215 134.897L50.3086 124.341C51.6872 121.95 50.868 118.894 48.4772 117.515C46.093 116.136 43.0362 116.956 41.6576 119.346L35.5573 129.902C34.1854 132.286 35.0046 135.343 37.3888 136.722C39.7729 138.1 42.8364 137.281 44.215 134.897Z" fill="url(#paint8_linear_101_5284)" />
          <path fill-rule="evenodd" clip-rule="evenodd" d="M17.395 111.747L27.9506 105.646C30.3415 104.268 31.1606 101.211 29.7821 98.8269C28.4035 96.436 25.3467 95.6169 22.9559 96.9955L12.4002 103.089C10.016 104.468 9.19685 107.531 10.5754 109.915C11.954 112.3 15.0108 113.119 17.395 111.747Z" fill="url(#paint9_linear_101_5284)" />
          <path fill-rule="evenodd" clip-rule="evenodd" d="M5.75615 78.2787H17.9435C20.7006 78.2787 22.9383 76.041 22.9383 73.2839C22.9383 70.5267 20.7006 68.2891 17.9435 68.2891H5.75615C2.99902 68.2891 0.761353 70.5267 0.761353 73.2839C0.761353 76.041 2.99902 78.2787 5.75615 78.2787Z" fill="url(#paint10_linear_101_5284)" />
          <path fill-rule="evenodd" clip-rule="evenodd" d="M12.4043 43.4797L22.9588 49.5734C25.3466 50.9519 28.4033 50.1329 29.7819 47.7451C31.1604 45.3574 30.3414 42.3007 27.9536 40.9221L17.3991 34.8285C15.0114 33.4499 11.9547 34.2689 10.5761 36.6567C9.19752 39.0444 10.0166 42.1011 12.4043 43.4797Z" fill="url(#paint11_linear_101_5284)" />
          <path fill-rule="evenodd" clip-rule="evenodd" d="M35.5621 16.6651L41.6558 27.2197C43.0343 29.6074 46.091 30.4265 48.4788 29.0479C50.8665 27.6693 51.6856 24.6126 50.307 22.2249L44.2133 11.6703C42.8348 9.28261 39.7781 8.46356 37.3903 9.84213C35.0026 11.2207 34.1835 14.2774 35.5621 16.6651Z" fill="url(#paint12_linear_101_5284)" />
          <defs>
            <linearGradient id="paint0_linear_101_5284" x1="64.6586" y1="88.2682" x2="64.6586" y2="221.463" gradientUnits="userSpaceOnUse">
              <stop stop-color="#FCD935" />
              <stop offset="1" stop-color="#C19F00" />
            </linearGradient>
            <linearGradient id="paint1_linear_101_5284" x1="74.0184" y1="13.6382" x2="74.0184" y2="61.629" gradientUnits="userSpaceOnUse">
              <stop stop-color="#FCD935" />
              <stop offset="1" stop-color="#C19F00" />
            </linearGradient>
            <linearGradient id="paint2_linear_101_5284" x1="103.129" y1="22.2045" x2="88.3839" y2="54.968" gradientUnits="userSpaceOnUse">
              <stop stop-color="#FCD935" />
              <stop offset="1" stop-color="#C19F00" />
            </linearGradient>
            <linearGradient id="paint3_linear_101_5284" x1="128.958" y1="42.1984" x2="98.9897" y2="63.0935" gradientUnits="userSpaceOnUse">
              <stop stop-color="#FCD935" />
              <stop offset="1" stop-color="#C19F00" />
            </linearGradient>
            <linearGradient id="paint4_linear_101_5284" x1="138.13" y1="74.5286" x2="90.6357" y2="73.2841" gradientUnits="userSpaceOnUse">
              <stop stop-color="#FCD935" />
              <stop offset="1" stop-color="#C19F00" />
            </linearGradient>
            <linearGradient id="paint5_linear_101_5284" x1="127.854" y1="104.921" x2="92.33" y2="78.2816" gradientUnits="userSpaceOnUse">
              <stop stop-color="#FCD935" />
              <stop offset="1" stop-color="#C19F00" />
            </linearGradient>
            <linearGradient id="paint6_linear_101_5284" x1="105.099" y1="128.115" x2="83.8903" y2="96.3225" gradientUnits="userSpaceOnUse">
              <stop stop-color="#FCD935" />
              <stop offset="1" stop-color="#C19F00" />
            </linearGradient>
            <linearGradient id="paint7_linear_101_5284" x1="74.0184" y1="134.887" x2="72.3534" y2="98.5702" gradientUnits="userSpaceOnUse">
              <stop stop-color="#FCD935" />
              <stop offset="1" stop-color="#C19F00" />
            </linearGradient>
            <linearGradient id="paint8_linear_101_5284" x1="42.9337" y1="124.894" x2="62.3628" y2="93.5723" gradientUnits="userSpaceOnUse">
              <stop stop-color="#FCD935" />
              <stop offset="1" stop-color="#C19F00" />
            </linearGradient>
            <linearGradient id="paint9_linear_101_5284" x1="20.1774" y1="104.921" x2="65.7081" y2="76.9505" gradientUnits="userSpaceOnUse">
              <stop stop-color="#FCD935" />
              <stop offset="1" stop-color="#C19F00" />
            </linearGradient>
            <linearGradient id="paint10_linear_101_5284" x1="11.8511" y1="73.2839" x2="83.7709" y2="73.2839" gradientUnits="userSpaceOnUse">
              <stop stop-color="#FCD935" />
              <stop offset="1" stop-color="#C19F00" />
            </linearGradient>
            <linearGradient id="paint11_linear_101_5284" x1="20.1801" y1="42.2016" x2="82.4645" y2="78.1615" gradientUnits="userSpaceOnUse">
              <stop stop-color="#FCD935" />
              <stop offset="1" stop-color="#C19F00" />
            </linearGradient>
            <linearGradient id="paint12_linear_101_5284" x1="42.9352" y1="19.4462" x2="78.8951" y2="81.7305" gradientUnits="userSpaceOnUse">
              <stop stop-color="#FCD935" />
              <stop offset="1" stop-color="#C19F00" />
            </linearGradient>
          </defs>
        </svg>
      </header>

      <div class="clock_local">

        <h1 class="clock_local--text"><svg xmlns="http://www.w3.org/2000/svg" width="25" height="25" viewBox="0 0 25 25" fill="none">
            <path d="M12.5 2.25781C8.63 2.25781 5.5 5.38781 5.5 9.25781C5.5 14.5078 12.5 22.2578 12.5 22.2578C12.5 22.2578 19.5 14.5078 19.5 9.25781C19.5 5.38781 16.37 2.25781 12.5 2.25781ZM12.5 11.7578C11.837 11.7578 11.2011 11.4944 10.7322 11.0256C10.2634 10.5567 10 9.92085 10 9.25781C10 8.59477 10.2634 7.95889 10.7322 7.49005C11.2011 7.0212 11.837 6.75781 12.5 6.75781C13.163 6.75781 13.7989 7.0212 14.2678 7.49005C14.7366 7.95889 15 8.59477 15 9.25781C15 9.92085 14.7366 10.5567 14.2678 11.0256C13.7989 11.4944 13.163 11.7578 12.5 11.7578Z" fill="#2D2D2D" />
          </svg>Local: <span class="clock_local--text" id="city"></span>
        </h1>

        <div class="clock_content">
          <svg xmlns="http://www.w3.org/2000/svg" width="25" height="25" viewBox="0 0 25 25" fill="none">
            <path d="M3.49194 11.8345C3.49194 10.2025 3.89994 8.69055 4.70794 7.30655C5.51594 5.92255 6.61194 4.82655 7.99594 4.01855C9.37994 3.21055 10.8839 2.81055 12.5079 2.81055C13.7239 2.81055 14.8919 3.05055 16.0039 3.52255C17.1159 3.99455 18.0679 4.64255 18.8759 5.44255C19.6839 6.24255 20.3239 7.20255 20.7959 8.32255C21.2679 9.44255 21.5079 10.6025 21.5079 11.8345C21.5079 13.0505 21.2679 14.2185 20.7959 15.3305C20.3239 16.4425 19.6759 17.4025 18.8759 18.2025C18.0759 19.0025 17.1159 19.6425 16.0039 20.1145C14.8919 20.5865 13.7319 20.8265 12.5079 20.8265C11.2839 20.8265 10.1079 20.5865 8.99594 20.1145C7.88394 19.6425 6.92394 18.9945 6.11594 18.1945C5.30794 17.3945 4.67594 16.4345 4.19594 15.3305C3.71594 14.2265 3.49194 13.0585 3.49194 11.8345ZM5.47594 11.8345C5.47594 13.7305 6.16394 15.3785 7.54794 16.7785C8.93194 18.1625 10.5799 18.8505 12.5079 18.8505C13.7719 18.8505 14.9479 18.5385 16.0199 17.9065C17.0919 17.2745 17.9559 16.4265 18.5879 15.3465C19.2199 14.2665 19.5399 13.0985 19.5399 11.8345C19.5399 10.5705 19.2199 9.39455 18.5879 8.31455C17.9559 7.23455 17.0999 6.37855 16.0199 5.74655C14.9399 5.11455 13.7719 4.80255 12.5079 4.80255C11.2439 4.80255 10.0679 5.11455 8.99594 5.74655C7.92394 6.37855 7.05994 7.23455 6.41994 8.31455C5.77994 9.39455 5.47594 10.5705 5.47594 11.8345ZM11.8119 11.8345V6.50655C11.8119 6.32255 11.8759 6.16255 12.0039 6.03455C12.1319 5.90655 12.2919 5.84255 12.4759 5.84255C12.6599 5.84255 12.8199 5.90655 12.9479 6.03455C13.0759 6.16255 13.1399 6.32255 13.1399 6.50655V11.4265L16.0119 13.0985C16.1719 13.1945 16.2679 13.3305 16.3159 13.5065C16.3639 13.6825 16.3399 13.8505 16.2439 14.0025C16.1159 14.2265 15.9239 14.3385 15.6679 14.3385C15.5319 14.3385 15.4199 14.3065 15.3319 14.2425L12.2759 12.4585C12.1399 12.4185 12.0279 12.3385 11.9399 12.2265C11.8519 12.1145 11.8119 11.9865 11.8119 11.8345Z" fill="#2D2D2D" />
          </svg>
          <div id="clock" class="clock_local--text"></div>
        </div>

      </div>

      <div class="cards-container">

        <div class="card c1">
          <h1 class="card--title"><svg xmlns="http://www.w3.org/2000/svg" width="44" height="44" viewBox="0 0 44 44" fill="none">
              <path fill-rule="evenodd" clip-rule="evenodd" d="M32.134 6.71007C32.673 7.08682 33.0814 7.62169 33.256 8.27344C33.4334 8.93619 33.3427 9.61269 33.0553 10.2149C32.8092 10.7292 33.0278 11.3452 33.542 11.5899C34.0549 11.8347 34.6709 11.6174 34.917 11.1032C35.4148 10.0596 35.555 8.88532 35.2484 7.73994C34.9459 6.60969 34.2515 5.67469 33.3179 5.02019C32.8518 4.69432 32.2083 4.80707 31.881 5.27319C31.5552 5.73932 31.6679 6.38282 32.134 6.71007Z" fill="url(#paint0_linear_101_5200)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M33.985 3.63117C35.2596 4.52492 36.218 5.79542 36.6319 7.33817C37.0512 8.90292 36.845 10.5048 36.1644 11.932C35.9196 12.4449 36.1369 13.0609 36.6511 13.3057C37.1654 13.5518 37.7814 13.3332 38.0261 12.8189C38.9157 10.9517 39.1729 8.85342 38.6242 6.80467C38.0825 4.78342 36.8381 3.11279 35.1675 1.94267C34.7013 1.61542 34.0578 1.72954 33.732 2.19567C33.4047 2.66179 33.5188 3.30529 33.985 3.63117Z" fill="url(#paint1_linear_101_5200)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M23.7873 8.33508C23.7873 7.67233 23.5136 7.03845 23.031 6.58333C22.547 6.1282 21.898 5.89308 21.2353 5.93433L10.0606 6.6122C8.79151 6.6892 7.80151 7.74108 7.80151 9.01433C7.80151 10.0676 7.80151 11.3807 7.80151 11.3807C7.80151 11.95 8.26214 12.412 8.83276 12.412H22.756C23.3266 12.412 23.7873 11.95 23.7873 11.3807V8.33508Z" fill="url(#paint2_linear_101_5200)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M30.3386 18.3773V11.3359C30.3386 10.7667 29.8766 10.3047 29.3074 10.3047C28.7381 10.3047 28.2761 10.7667 28.2761 11.3359V18.3773C28.2761 18.9466 28.7381 19.4086 29.3074 19.4086C29.8766 19.4086 30.3386 18.9466 30.3386 18.3773Z" fill="url(#paint3_linear_101_5200)" />
              <path d="M29.4563 12.3667C31.0351 12.3667 32.3149 11.0868 32.3149 9.50804C32.3149 7.92926 31.0351 6.64941 29.4563 6.64941C27.8775 6.64941 26.5977 7.92926 26.5977 9.50804C26.5977 11.0868 27.8775 12.3667 29.4563 12.3667Z" fill="url(#paint4_linear_101_5200)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M25.1018 17.3457C24.5312 17.3457 24.0706 17.8077 24.0706 18.377V41.2501C24.0706 41.8193 24.5312 42.2813 25.1018 42.2813H33.8124C34.3831 42.2813 34.8437 41.8193 34.8437 41.2501V19.8358C34.8437 19.1992 34.6223 18.5915 34.2442 18.1405C33.8069 17.6207 33.2047 17.3457 32.5873 17.3457H25.1018Z" fill="url(#paint5_linear_101_5200)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M34.8429 23.0664V29.4024H32.9248C32.2868 29.4024 31.6749 29.148 31.2239 28.697C30.7729 28.246 30.5186 27.6342 30.5186 26.9962V25.4727C30.5186 24.8347 30.7729 24.2228 31.2239 23.7718C31.6749 23.3208 32.2868 23.0664 32.9248 23.0664H34.8429Z" fill="url(#paint6_linear_101_5200)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M34.8429 31.5059V37.8419H32.9248C32.2868 37.8419 31.6749 37.5875 31.2239 37.1365C30.7729 36.6855 30.5186 36.0736 30.5186 35.4356V33.9121C30.5186 33.2741 30.7729 32.6622 31.2239 32.2112C31.6749 31.7589 32.2868 31.5059 32.9248 31.5059H34.8429Z" fill="url(#paint7_linear_101_5200)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M26.1321 41.25V12.7559C26.1321 12.1165 25.8777 11.5046 25.4267 11.0536C24.9757 10.6026 24.3639 10.3496 23.7259 10.3496C20.276 10.3496 11.2876 10.3496 7.83911 10.3496C7.20111 10.3496 6.58924 10.6026 6.13824 11.0536C5.68586 11.5046 5.43286 12.1165 5.43286 12.7559V41.25C5.43286 41.8192 5.89486 42.2812 6.46411 42.2812H25.1009C25.6701 42.2812 26.1321 41.8192 26.1321 41.25Z" fill="url(#paint8_linear_101_5200)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M14.7102 33.0179C14.7102 32.4487 14.2482 31.9867 13.679 31.9867H10.3501C9.78085 31.9867 9.31885 32.4487 9.31885 33.0179V36.3468C9.31885 36.916 9.78085 37.378 10.3501 37.378H13.679C14.2482 37.378 14.7102 36.916 14.7102 36.3468V33.0179ZM22.2452 33.0179C22.2452 32.4487 21.7832 31.9867 21.214 31.9867H17.8865C17.3172 31.9867 16.8552 32.4487 16.8552 33.0179V36.3468C16.8552 36.916 17.3172 37.378 17.8865 37.378H21.214C21.7832 37.378 22.2452 36.916 22.2452 36.3468V33.0179ZM14.7102 24.6511C14.7102 24.0818 14.2482 23.6198 13.679 23.6198H10.3501C9.78085 23.6198 9.31885 24.0818 9.31885 24.6511V27.9786C9.31885 28.5492 9.78085 29.0098 10.3501 29.0098H13.679C14.2482 29.0098 14.7102 28.5492 14.7102 27.9786V24.6511ZM22.2452 24.6511C22.2452 24.0818 21.7832 23.6198 21.214 23.6198H17.8865C17.3172 23.6198 16.8552 24.0818 16.8552 24.6511V27.9786C16.8552 28.5492 17.3172 29.0098 17.8865 29.0098H21.214C21.7832 29.0098 22.2452 28.5492 22.2452 27.9786V24.6511ZM14.7102 16.2842C14.7102 15.7149 14.2482 15.2529 13.679 15.2529H10.3501C9.78085 15.2529 9.31885 15.7149 9.31885 16.2842V19.6117C9.31885 20.1809 9.78085 20.6429 10.3501 20.6429H13.679C14.2482 20.6429 14.7102 20.1809 14.7102 19.6117V16.2842ZM22.2452 16.2842C22.2452 15.7149 21.7832 15.2529 21.214 15.2529H17.8865C17.3172 15.2529 16.8552 15.7149 16.8552 16.2842V19.6117C16.8552 20.1809 17.3172 20.6429 17.8865 20.6429H21.214C21.7832 20.6429 22.2452 20.1809 22.2452 19.6117V16.2842Z" fill="url(#paint9_linear_101_5200)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M41.25 40.2188H3.09375C2.5245 40.2188 2.0625 40.6807 2.0625 41.25C2.0625 41.8192 2.5245 42.2812 3.09375 42.2812H41.25C41.8192 42.2812 42.2812 41.8192 42.2812 41.25C42.2812 40.6807 41.8192 40.2188 41.25 40.2188Z" fill="url(#paint10_linear_101_5200)" />
              <defs>
                <linearGradient id="paint0_linear_101_5200" x1="29.2578" y1="8.73926" x2="61.1864" y2="6.46671e-05" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#0593FF" />
                  <stop offset="1" stop-color="#00599D" />
                </linearGradient>
                <linearGradient id="paint1_linear_101_5200" x1="29.2594" y1="8.73899" x2="61.188" y2="-0.000220083" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#0593FF" />
                  <stop offset="1" stop-color="#00599D" />
                </linearGradient>
                <linearGradient id="paint2_linear_101_5200" x1="15.8982" y1="6.64962" x2="15.8982" y2="29.2761" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#0593FF" />
                  <stop offset="1" stop-color="#00599D" />
                </linearGradient>
                <linearGradient id="paint3_linear_101_5200" x1="28.8742" y1="13.0629" x2="28.8742" y2="28.6626" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#0593FF" />
                  <stop offset="1" stop-color="#00599D" />
                </linearGradient>
                <linearGradient id="paint4_linear_101_5200" x1="29.1513" y1="7.96987" x2="29.1513" y2="30.1461" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#D8E1EF" />
                  <stop offset="1" stop-color="#5B8EDE" />
                </linearGradient>
                <linearGradient id="paint5_linear_101_5200" x1="29.5862" y1="32.0086" x2="9.37827" y2="32.0086" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#D8E1EF" />
                  <stop offset="1" stop-color="#5B8EDE" />
                </linearGradient>
                <linearGradient id="paint6_linear_101_5200" x1="36.6671" y1="28.3399" x2="7.70827" y2="28.3399" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#0E6AE0" />
                  <stop offset="1" stop-color="#003D8B" />
                </linearGradient>
                <linearGradient id="paint7_linear_101_5200" x1="36.6671" y1="28.341" x2="7.70827" y2="28.341" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#0E6AE0" />
                  <stop offset="1" stop-color="#003D8B" />
                </linearGradient>
                <linearGradient id="paint8_linear_101_5200" x1="13.0472" y1="23.0674" x2="13.0472" y2="94.2993" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#D8E1EF" />
                  <stop offset="1" stop-color="#5B8EDE" />
                </linearGradient>
                <linearGradient id="paint9_linear_101_5200" x1="12.3755" y1="17.9481" x2="12.3755" y2="74.1894" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#0E6AE0" />
                  <stop offset="1" stop-color="#003D8B" />
                </linearGradient>
                <linearGradient id="paint10_linear_101_5200" x1="22.1719" y1="40.9764" x2="22.1719" y2="71.247" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#D8E1EF" />
                  <stop offset="1" stop-color="#5B8EDE" />
                </linearGradient>
              </defs>
            </svg>Casos de Câncer de Pele</h1>
          <span class="card--nums" id="cases_2023">1</span>
          <span class="card--subtitles" id="last_day">1</span>
        </div>
        <div class="card c2">
          <h1 class="card--title"><svg xmlns="http://www.w3.org/2000/svg" width="44" height="44" viewBox="0 0 44 44" fill="none">
              <path fill-rule="evenodd" clip-rule="evenodd" d="M40.7289 34.375C40.7289 33.8057 40.2669 33.3438 39.6976 33.3438H36.4375C35.8683 33.3438 35.4062 33.8057 35.4062 34.375V41.25C35.4062 41.8193 35.8683 42.2812 36.4375 42.2812H39.6976C40.2669 42.2812 40.7289 41.8193 40.7289 41.25V34.375Z" fill="url(#paint0_linear_101_5217)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M4.30225 33.3438C3.733 33.3438 3.271 33.8057 3.271 34.375V41.25C3.271 41.8193 3.733 42.2812 4.30225 42.2812H7.56237C8.13162 42.2812 8.59362 41.8193 8.59362 41.25V34.375C8.59362 33.8057 8.13162 33.3438 7.56237 33.3438H4.30225Z" fill="url(#paint1_linear_101_5217)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M35.7819 15.8147V15.8092C35.7819 13.5528 33.9531 11.7227 31.6954 11.7227H31.4217C30.055 11.7227 30.3877 13.3232 30.3877 12.7539V18.8699C30.3877 19.4392 30.8497 19.9012 31.419 19.9012H31.6954C33.9531 19.9012 35.7819 18.071 35.7819 15.8147Z" fill="url(#paint2_linear_101_5217)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M12.3043 19.9012L12.6343 19.8998C13.1788 19.8723 13.6119 19.4213 13.6119 18.8699V12.7539C13.6119 12.7539 13.9446 11.7227 12.5779 11.7227H12.3043C10.0465 11.7227 8.21777 13.5528 8.21777 15.8092V15.8147C8.21777 18.071 10.0465 19.9012 12.3043 19.9012Z" fill="url(#paint3_linear_101_5217)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M26.0376 22C26.0376 21.4307 25.5756 20.9688 25.0064 20.9688H18.9949C18.4256 20.9688 17.9636 21.4307 17.9636 22V26.125C17.9636 26.6943 18.4256 27.1562 18.9949 27.1562H25.0064C25.5756 27.1562 26.0376 26.6943 26.0376 26.125V22Z" fill="url(#paint4_linear_101_5217)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M20.2939 7.25769C20.771 6.90431 21.3609 6.69531 22.0003 6.69531C22.6479 6.69531 23.2474 6.91119 23.7273 7.27281C24.1824 7.61656 24.8287 7.52581 25.1724 7.07069C25.5148 6.61694 25.424 5.96931 24.9689 5.62694C24.1425 5.00269 23.114 4.63281 22.0003 4.63281C20.9017 4.63281 19.8869 4.99306 19.066 5.60081C18.6082 5.94044 18.5119 6.58669 18.8515 7.04319C19.1898 7.50106 19.836 7.59731 20.2939 7.25769Z" fill="url(#paint5_linear_101_5217)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M17.9461 5.1095C19.0723 4.27488 20.4665 3.78125 21.9735 3.78125C23.5025 3.78125 24.9146 4.28863 26.049 5.14387C26.5028 5.48762 27.1504 5.39688 27.4928 4.94175C27.8351 4.488 27.7458 3.84037 27.2906 3.498C25.8111 2.3815 23.9686 1.71875 21.9735 1.71875C20.0059 1.71875 18.1881 2.36362 16.7183 3.45125C16.2604 3.79087 16.1655 4.43712 16.5038 4.895C16.842 5.3515 17.4883 5.44775 17.9461 5.1095Z" fill="url(#paint6_linear_101_5217)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M42.2812 31.625V31.6222C42.2812 29.535 40.59 27.8438 38.5028 27.8438C36.1034 27.8438 33 27.8438 33 27.8438C32.4307 27.8438 31.9688 28.3057 31.9688 28.875V34.375C31.9688 34.9443 32.4307 35.4062 33 35.4062H38.5C40.5886 35.4062 42.2812 33.7136 42.2812 31.625Z" fill="url(#paint7_linear_101_5217)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M1.71875 31.6222V31.625C1.71875 33.7136 3.41137 35.4062 5.5 35.4062H11C11.5693 35.4062 12.0312 34.9443 12.0312 34.375V28.875C12.0312 28.3057 11.5693 27.8438 11 27.8438C11 27.8438 7.89663 27.8438 5.49725 27.8438C3.41 27.8438 1.71875 29.535 1.71875 31.6222Z" fill="url(#paint8_linear_101_5217)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M32.4505 15.125C32.4505 11.5184 29.5259 8.59375 25.9193 8.59375H18.0818C14.4752 8.59375 11.5505 11.5184 11.5505 15.125V16.5C11.5505 20.1066 14.4752 23.0312 18.0818 23.0312H25.9193C29.5259 23.0312 32.4505 20.1066 32.4505 16.5V15.125Z" fill="url(#paint9_linear_101_5217)" />
              <path d="M17.9636 18.9062C19.6723 18.9062 21.0574 17.5211 21.0574 15.8125C21.0574 14.1039 19.6723 12.7188 17.9636 12.7188C16.255 12.7188 14.8699 14.1039 14.8699 15.8125C14.8699 17.5211 16.255 18.9062 17.9636 18.9062Z" fill="#D8E1EF" />
              <path d="M26.0364 18.9062C27.745 18.9062 29.1301 17.5211 29.1301 15.8125C29.1301 14.1039 27.745 12.7188 26.0364 12.7188C24.3277 12.7188 22.9426 14.1039 22.9426 15.8125C22.9426 17.5211 24.3277 18.9062 26.0364 18.9062Z" fill="#D8E1EF" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M34.0312 28.875C34.0312 27.8726 33.6325 26.9101 32.9244 26.2006C32.2149 25.4925 31.2524 25.0938 30.25 25.0938H13.75C12.7476 25.0938 11.7851 25.4925 11.0756 26.2006C10.3675 26.9101 9.96875 27.8726 9.96875 28.875C9.96875 31.6058 9.96875 35.7692 9.96875 38.5C9.96875 39.5024 10.3675 40.4649 11.0756 41.1744C11.7851 41.8825 12.7476 42.2812 13.75 42.2812H30.25C31.2524 42.2812 32.2149 41.8825 32.9244 41.1744C33.6325 40.4649 34.0312 39.5024 34.0312 38.5V28.875Z" fill="url(#paint10_linear_101_5217)" />
              <defs>
                <linearGradient id="paint0_linear_101_5217" x1="21.3125" y1="46.0625" x2="21.3125" y2="23.1118" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#0593FF" />
                  <stop offset="1" stop-color="#00599D" />
                </linearGradient>
                <linearGradient id="paint1_linear_101_5217" x1="21.3124" y1="46.0625" x2="21.3124" y2="23.1118" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#0593FF" />
                  <stop offset="1" stop-color="#00599D" />
                </linearGradient>
                <linearGradient id="paint2_linear_101_5217" x1="39.5583" y1="17.1091" x2="10.463" y2="17.1091" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#0E6AE0" />
                  <stop offset="1" stop-color="#003D8B" />
                </linearGradient>
                <linearGradient id="paint3_linear_101_5217" x1="4.1244" y1="15.0558" x2="32.3119" y2="15.0558" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#0E6AE0" />
                  <stop offset="1" stop-color="#003D8B" />
                </linearGradient>
                <linearGradient id="paint4_linear_101_5217" x1="22.78" y1="19.8557" x2="22.78" y2="34.7188" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#D8E1EF" />
                  <stop offset="1" stop-color="#5B8EDE" />
                </linearGradient>
                <linearGradient id="paint5_linear_101_5217" x1="22.0219" y1="0.885846" x2="22.0219" y2="18.9067" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#0593FF" />
                  <stop offset="1" stop-color="#00599D" />
                </linearGradient>
                <linearGradient id="paint6_linear_101_5217" x1="22.024" y1="0.885409" x2="22.024" y2="18.9063" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#0593FF" />
                  <stop offset="1" stop-color="#00599D" />
                </linearGradient>
                <linearGradient id="paint7_linear_101_5217" x1="50.1875" y1="31.9489" x2="2.24356e-07" y2="31.9489" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#D8E1EF" />
                  <stop offset="1" stop-color="#5B8EDE" />
                </linearGradient>
                <linearGradient id="paint8_linear_101_5217" x1="0.6875" y1="30.7557" x2="41.25" y2="30.7557" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#D8E1EF" />
                  <stop offset="1" stop-color="#5B8EDE" />
                </linearGradient>
                <linearGradient id="paint9_linear_101_5217" x1="20.8707" y1="9.54317" x2="20.8707" y2="37.125" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#0593FF" />
                  <stop offset="1" stop-color="#00599D" />
                </linearGradient>
                <linearGradient id="paint10_linear_101_5217" x1="24.1625" y1="25.7175" x2="24.1625" y2="67.375" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#0593FF" />
                  <stop offset="1" stop-color="#00599D" />
                </linearGradient>
              </defs>
            </svg>Diagnósticos Previstos para Hoje</h1>
          <span class="card--nums" id="cases_now">1</span>
        </div>
        <div class="card c3">
          <h1 class="card--title"><svg xmlns="http://www.w3.org/2000/svg" width="45" height="44" viewBox="0 0 45 44" fill="none">
              <path fill-rule="evenodd" clip-rule="evenodd" d="M18.686 8.39952C18.686 8.62468 18.7919 8.83853 18.976 8.98556C19.159 9.13155 19.4027 9.19632 19.6419 9.16034C19.7346 9.14697 19.8283 9.13978 19.9242 9.13978H24.879C24.975 9.13978 25.0687 9.14697 25.1613 9.16034C25.4005 9.19632 25.6431 9.13155 25.8272 8.98556C26.0114 8.83853 26.1172 8.62468 26.1172 8.39952V6.6342C26.1172 5.9402 25.8217 5.27499 25.2947 4.78354C24.7688 4.29312 24.0554 4.01758 23.3112 4.01758C22.7236 4.01758 22.0797 4.01758 21.492 4.01758C20.7478 4.01758 20.0344 4.29312 19.5074 4.78354C18.9815 5.27499 18.686 5.9402 18.686 6.6342V8.39952Z" fill="url(#paint0_linear_101_5239)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M30.3095 12.2075C30.3095 11.2078 30.0158 10.248 29.4916 9.54039C28.9674 8.83419 28.2573 8.43652 27.5157 8.43652C24.7981 8.43652 20.0049 8.43652 17.2873 8.43652C16.5457 8.43652 15.8356 8.83419 15.3114 9.54039C14.7871 10.248 14.4935 11.2078 14.4935 12.2075C14.4935 17.7871 14.4935 30.4 14.4935 35.9796C14.4935 36.9793 14.7871 37.9378 15.3114 38.6453C15.8356 39.3529 16.5457 39.7506 17.2873 39.7506C20.0049 39.7506 24.7981 39.7506 27.5157 39.7506C28.2573 39.7506 28.9674 39.3529 29.4916 38.6453C30.0158 37.9378 30.3095 36.9793 30.3095 35.9796V12.2075Z" fill="url(#paint1_linear_101_5239)" />
              <path d="M30.3109 13.2822H14.4936V35.0371H30.3109V13.2822Z" fill="url(#paint2_linear_101_5239)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M23.4337 17.5743C23.4332 17.5738 23.4332 17.5732 23.4327 17.5727C23.2576 17.205 22.8868 16.9707 22.4794 16.9707C22.0721 16.9707 21.7013 17.205 21.5262 17.5727C21.5257 17.5732 21.5257 17.5738 21.5252 17.5743C21.5252 17.5743 18.2516 24.5565 18.2516 27.5431C18.2516 29.8765 20.146 31.7709 22.4794 31.7709C24.8129 31.7709 26.7073 29.8765 26.7073 27.5431C26.7073 24.5565 23.4337 17.5743 23.4337 17.5743Z" fill="url(#paint3_linear_101_5239)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M24.9413 25.1564C25.1912 26.0639 25.3482 26.8993 25.3482 27.543C25.3482 29.1258 24.0628 30.4112 22.4795 30.4112C20.8961 30.4112 19.6107 29.1258 19.6107 27.543C19.6107 27.3087 19.6308 27.0508 19.6764 26.7744C19.7055 26.5727 19.8325 26.3976 20.0161 26.3078C20.2017 26.2165 20.4205 26.224 20.5996 26.3278C20.6021 26.3293 20.6046 26.3309 20.6071 26.3324C21.4179 26.8275 22.0515 26.524 22.9661 25.6099C23.3469 25.2286 23.7051 24.9512 24.0463 24.7665C24.0498 24.7645 24.0538 24.7625 24.0578 24.7605C24.2259 24.6772 24.422 24.6737 24.5931 24.75C24.7637 24.8267 24.8916 24.9758 24.9413 25.1564Z" fill="url(#paint4_linear_101_5239)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M20.0176 25.1564C19.7678 26.0639 19.6107 26.8993 19.6107 27.543C19.6107 29.1258 20.8961 30.4112 22.4795 30.4112C24.0628 30.4112 25.3482 29.1258 25.3482 27.543C25.3482 27.3087 25.3281 27.0508 25.2825 26.7744C25.2534 26.5727 25.1264 26.3976 24.9428 26.3078C24.7572 26.2165 24.5384 26.224 24.3593 26.3278C24.3568 26.3293 24.3543 26.3309 24.3518 26.3324C23.5411 26.8275 22.9074 26.524 21.9928 25.6099C21.612 25.2286 21.2538 24.9512 20.9126 24.7665C20.9091 24.7645 20.9051 24.7625 20.9011 24.7605C20.733 24.6772 20.5369 24.6737 20.3658 24.75C20.1952 24.8267 20.0673 24.9758 20.0176 25.1564Z" fill="url(#paint5_linear_101_5239)" />
              <defs>
                <linearGradient id="paint0_linear_101_5239" x1="22.4016" y1="5.30275" x2="22.4016" y2="13.8767" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#FFC45C" />
                  <stop offset="1" stop-color="#E39100" />
                </linearGradient>
                <linearGradient id="paint1_linear_101_5239" x1="22.053" y1="30.5677" x2="22.053" y2="64.7733" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#D8DDFA" />
                  <stop offset="1" stop-color="#435EFF" />
                </linearGradient>
                <linearGradient id="paint2_linear_101_5239" x1="22.5784" y1="18.5127" x2="22.5784" y2="82.2037" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#3F555E" />
                  <stop offset="1" stop-color="#152C36" />
                </linearGradient>
                <linearGradient id="paint3_linear_101_5239" x1="22.746" y1="27.988" x2="22.746" y2="43.652" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#FFC484" />
                  <stop offset="1" stop-color="#D8815C" />
                </linearGradient>
                <linearGradient id="paint4_linear_101_5239" x1="24.1581" y1="25.3741" x2="23.232" y2="28.6352" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#D8815C" />
                  <stop offset="1" stop-color="#FFC484" />
                </linearGradient>
                <linearGradient id="paint5_linear_101_5239" x1="22.4795" y1="27.8826" x2="22.4795" y2="40.7066" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#FFECD8" />
                  <stop offset="1" stop-color="#D8815C" />
                </linearGradient>
              </defs>
            </svg>Protetor recomendado</h1>
          <span class="card--nums" id="fps_recommendation">1</span>
          <span class="card--subtitles" id="str_fps_recomendation">Em caso de exposição ao Sol, utilize protetor solar a cada 2 horas.</span>
        </div>
        <div class="card c4">
          <h1 class="card--title"><svg xmlns="http://www.w3.org/2000/svg" width="44" height="44" viewBox="0 0 44 44" fill="none">
              <path d="M21.9987 34.9404C29.1453 34.9404 34.9387 29.147 34.9387 22.0005C34.9387 14.8539 29.1453 9.06055 21.9987 9.06055C14.8521 9.06055 9.05872 14.8539 9.05872 22.0005C9.05872 29.147 14.8521 34.9404 21.9987 34.9404Z" fill="url(#paint0_linear_101_5254)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M20.5 1.49999V5.15997C20.5 5.98796 21.172 6.65996 22 6.65996C22.828 6.65996 23.5 5.98796 23.5 5.15997V1.49999C23.5 0.671996 22.828 0 22 0C21.172 0 20.5 0.671996 20.5 1.49999Z" fill="url(#paint1_linear_101_5254)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M30.9491 3.49516L29.1191 6.66514C28.7051 7.38313 28.9511 8.30113 29.6691 8.71512C30.3851 9.12912 31.3031 8.88312 31.7171 8.16513L33.5491 4.99515C33.9611 4.27915 33.7151 3.36116 32.9991 2.94716C32.2831 2.53316 31.3631 2.77916 30.9491 3.49516Z" fill="url(#paint2_linear_101_5254)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M39.0031 10.4497L35.8331 12.2817C35.1151 12.6957 34.8691 13.6136 35.2831 14.3296C35.6971 15.0476 36.6151 15.2936 37.3331 14.8796L40.5031 13.0497C41.2191 12.6357 41.4651 11.7157 41.0511 10.9997C40.6371 10.2837 39.7191 10.0377 39.0031 10.4497Z" fill="url(#paint3_linear_101_5254)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M42.5 20.5H38.84C38.012 20.5 37.34 21.172 37.34 22C37.34 22.828 38.012 23.5 38.84 23.5H42.5C43.328 23.5 44 22.828 44 22C44 21.172 43.328 20.5 42.5 20.5Z" fill="url(#paint4_linear_101_5254)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M40.5031 30.9509L37.3331 29.1209C36.6151 28.7069 35.6971 28.9529 35.2831 29.6709C34.8691 30.3869 35.1151 31.3049 35.8331 31.7189L39.0031 33.5509C39.7191 33.9629 40.6371 33.7169 41.0511 33.0009C41.4651 32.2849 41.2191 31.3649 40.5031 30.9509Z" fill="url(#paint5_linear_101_5254)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M33.5491 39.003L31.7171 35.833C31.3031 35.115 30.3851 34.869 29.6691 35.283C28.9511 35.697 28.7051 36.615 29.1191 37.333L30.9491 40.503C31.3631 41.219 32.2831 41.465 32.9991 41.051C33.7151 40.637 33.9611 39.719 33.5491 39.003Z" fill="url(#paint6_linear_101_5254)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M23.5 42.4998V38.8398C23.5 38.0118 22.828 37.3398 22 37.3398C21.172 37.3398 20.5 38.0118 20.5 38.8398V42.4998C20.5 43.3278 21.172 43.9998 22 43.9998C22.828 43.9998 23.5 43.3278 23.5 42.4998Z" fill="url(#paint7_linear_101_5254)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M13.0497 40.503L14.8797 37.333C15.2937 36.615 15.0477 35.697 14.3297 35.283C13.6137 34.869 12.6957 35.115 12.2817 35.833L10.4497 39.003C10.0377 39.719 10.2837 40.637 10.9997 41.051C11.7157 41.465 12.6357 41.219 13.0497 40.503Z" fill="url(#paint8_linear_101_5254)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M4.99528 33.5509L8.16528 31.7189C8.88328 31.3049 9.12928 30.3869 8.71528 29.6709C8.30128 28.9529 7.38328 28.7069 6.66528 29.1209L3.49528 30.9509C2.77928 31.3649 2.53328 32.2849 2.94728 33.0009C3.36128 33.7169 4.27928 33.9629 4.99528 33.5509Z" fill="url(#paint9_linear_101_5254)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M1.5 23.5H5.16C5.988 23.5 6.66 22.828 6.66 22C6.66 21.172 5.988 20.5 5.16 20.5H1.5C0.672 20.5 0 21.172 0 22C0 22.828 0.672 23.5 1.5 23.5Z" fill="url(#paint10_linear_101_5254)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M3.49655 13.0502L6.6662 14.8802C7.38327 15.2942 8.30124 15.0482 8.71524 14.3312C9.12924 13.6141 8.88327 12.6961 8.1662 12.2821L4.99655 10.4521C4.27948 10.0381 3.36151 10.2841 2.94751 11.0012C2.53351 11.7182 2.77948 12.6362 3.49655 13.0502Z" fill="url(#paint11_linear_101_5254)" />
              <path fill-rule="evenodd" clip-rule="evenodd" d="M10.4511 4.99726L12.2811 8.1669C12.6951 8.88396 13.6131 9.12993 14.3302 8.71593C15.0472 8.30193 15.2932 7.38397 14.8792 6.66691L13.0492 3.49727C12.6352 2.78021 11.7172 2.53424 11.0002 2.94824C10.2831 3.36223 10.0371 4.2802 10.4511 4.99726Z" fill="url(#paint12_linear_101_5254)" />
              <defs>
                <linearGradient id="paint0_linear_101_5254" x1="19.1891" y1="26.5004" x2="19.1891" y2="66.5002" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#FCD935" />
                  <stop offset="1" stop-color="#C19F00" />
                </linearGradient>
                <linearGradient id="paint1_linear_101_5254" x1="22" y1="4.08777" x2="22" y2="18.4999" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#FCD935" />
                  <stop offset="1" stop-color="#C19F00" />
                </linearGradient>
                <linearGradient id="paint2_linear_101_5254" x1="30.7423" y1="6.65994" x2="26.3142" y2="16.4992" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#FCD935" />
                  <stop offset="1" stop-color="#C19F00" />
                </linearGradient>
                <linearGradient id="paint3_linear_101_5254" x1="38.4991" y1="12.6649" x2="29.4992" y2="18.9399" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#FCD935" />
                  <stop offset="1" stop-color="#C19F00" />
                </linearGradient>
                <linearGradient id="paint4_linear_101_5254" x1="41.2536" y1="22.3738" x2="26.9904" y2="22.0001" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#FCD935" />
                  <stop offset="1" stop-color="#C19F00" />
                </linearGradient>
                <linearGradient id="paint5_linear_101_5254" x1="38.1675" y1="31.5009" x2="27.4992" y2="23.5009" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#FCD935" />
                  <stop offset="1" stop-color="#C19F00" />
                </linearGradient>
                <linearGradient id="paint6_linear_101_5254" x1="31.3339" y1="38.4664" x2="24.9647" y2="28.9187" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#FCD935" />
                  <stop offset="1" stop-color="#C19F00" />
                </linearGradient>
                <linearGradient id="paint7_linear_101_5254" x1="22" y1="40.4998" x2="21.5" y2="29.5936" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#FCD935" />
                  <stop offset="1" stop-color="#C19F00" />
                </linearGradient>
                <linearGradient id="paint8_linear_101_5254" x1="12.6649" y1="37.499" x2="18.4996" y2="28.0928" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#FCD935" />
                  <stop offset="1" stop-color="#C19F00" />
                </linearGradient>
                <linearGradient id="paint9_linear_101_5254" x1="5.83088" y1="31.5009" x2="19.5043" y2="23.1011" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#FCD935" />
                  <stop offset="1" stop-color="#C19F00" />
                </linearGradient>
                <linearGradient id="paint10_linear_101_5254" x1="3.3304" y1="22" x2="24.9288" y2="22" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#FCD935" />
                  <stop offset="1" stop-color="#C19F00" />
                </linearGradient>
                <linearGradient id="paint11_linear_101_5254" x1="5.83172" y1="12.6664" x2="24.5364" y2="23.4656" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#FCD935" />
                  <stop offset="1" stop-color="#C19F00" />
                </linearGradient>
                <linearGradient id="paint12_linear_101_5254" x1="12.6654" y1="5.83243" x2="23.4645" y2="24.5371" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#FCD935" />
                  <stop offset="1" stop-color="#C19F00" />
                </linearGradient>
              </defs>
            </svg>Índice de Radiação Ultravioleta</h1>
          <span class="card--nums" id="uv_index">1</span>
        </div>
        <div class="card c5">
          <div class="c5-info">
            <h1 class="card--title"><svg xmlns="http://www.w3.org/2000/svg" width="27" height="45" viewBox="0 0 27 45" fill="none">
                <path fill-rule="evenodd" clip-rule="evenodd" d="M19.3141 24.901V7.82898C19.3141 6.33023 18.7187 4.89336 17.6586 3.83323C16.5985 2.77311 15.1616 2.17773 13.6629 2.17773C12.1641 2.17773 10.7259 2.77311 9.66574 3.83323C8.60699 4.89336 8.01162 6.33023 8.01162 7.82898V24.901C5.49262 26.6775 3.84674 29.6104 3.84674 32.9255C3.84674 38.343 8.24537 42.7402 13.6629 42.7402C19.0804 42.7402 23.4776 38.343 23.4776 32.9255C23.4776 29.6117 21.8317 26.6789 19.3141 24.901Z" fill="url(#paint0_linear_101_5168)" />
                <path fill-rule="evenodd" clip-rule="evenodd" d="M7.85405 32.4008C7.73305 32.5809 7.7193 32.7596 7.7193 32.9453C7.7193 36.2274 10.3827 38.8907 13.6648 38.8907C16.9456 38.8907 19.6103 36.2274 19.6103 32.9453C19.6103 32.4544 19.5498 31.9773 19.4371 31.5208C19.4371 31.5208 19.3642 31.2361 19.1373 31.0106L19.1359 31.0093C18.0566 29.9299 17.0487 29.5504 16.1728 29.5119C14.8432 29.4541 13.7308 30.2159 12.9347 31.012C12.3434 31.6046 11.2517 32.1244 10.1709 31.5263C9.67455 31.2471 9.05992 31.2526 8.56217 31.5441C8.22805 31.7408 7.98055 32.046 7.85405 32.4008Z" fill="url(#paint1_linear_101_5168)" />
                <path fill-rule="evenodd" clip-rule="evenodd" d="M19.4742 32.4008C19.5952 32.5809 19.6103 32.7596 19.6103 32.9453C19.6103 36.2274 16.9456 38.8907 13.6648 38.8907C10.3827 38.8907 7.7193 36.2274 7.7193 32.9453C7.7193 32.4544 7.77842 31.9773 7.89117 31.5208C7.89117 31.5208 7.96405 31.2361 8.19092 31.0106L8.1923 31.0093C9.27305 29.9299 10.2809 29.5504 11.1568 29.5119C12.485 29.4541 13.5974 30.2159 14.3936 31.012C14.9862 31.6046 16.0766 32.1244 17.1573 31.5263C17.6551 31.2471 18.2683 31.2526 18.7661 31.5441C19.1002 31.7408 19.3491 32.046 19.4742 32.4008Z" fill="url(#paint2_linear_101_5168)" />
                <path fill-rule="evenodd" clip-rule="evenodd" d="M19.3155 21.4293H15.5342C14.965 21.4293 14.503 21.8927 14.503 22.4606C14.503 23.0298 14.965 23.4918 15.5342 23.4918H19.3155V21.4293ZM19.3155 16.8093H15.5342C14.965 16.8093 14.503 17.2727 14.503 17.8406C14.503 18.4098 14.965 18.8718 15.5342 18.8718H19.3155V16.8093ZM19.3155 12.1893H15.5342C14.965 12.1893 14.503 12.6527 14.503 13.2206C14.503 13.7898 14.965 14.2518 15.5342 14.2518H19.3155V12.1893ZM19.3086 7.56934H15.5342C14.965 7.56934 14.503 8.03271 14.503 8.60059C14.503 9.16984 14.965 9.63184 15.5342 9.63184H19.3155V7.83059C19.3155 7.74396 19.3127 7.65734 19.3086 7.56934Z" fill="url(#paint3_linear_101_5168)" />
                <defs>
                  <linearGradient id="paint0_linear_101_5168" x1="13.9904" y1="34.7515" x2="13.9904" y2="71.8765" gradientUnits="userSpaceOnUse">
                    <stop stop-color="#6DBEFF" />
                    <stop offset="1" stop-color="#0085F0" />
                  </linearGradient>
                  <linearGradient id="paint1_linear_101_5168" x1="17.2531" y1="30.1634" x2="16.6431" y2="35.2" gradientUnits="userSpaceOnUse">
                    <stop stop-color="#E2F4FD" />
                    <stop offset="1" stop-color="#4DC4FF" />
                  </linearGradient>
                  <linearGradient id="paint2_linear_101_5168" x1="12.4933" y1="34.752" x2="12.4933" y2="50.3945" gradientUnits="userSpaceOnUse">
                    <stop stop-color="#E2F4FD" />
                    <stop offset="1" stop-color="#4DC4FF" />
                  </linearGradient>
                  <linearGradient id="paint3_linear_101_5168" x1="18.2334" y1="18.0204" x2="18.2334" y2="39.5656" gradientUnits="userSpaceOnUse">
                    <stop stop-color="#E2F4FD" />
                    <stop offset="1" stop-color="#4DC4FF" />
                  </linearGradient>
                </defs>
              </svg>Temperatura</h1>
            <span class="card--nums" id="temperature">1</span>

          </div>

          <div class="c5-info">
            <h1 class="card--title"><svg xmlns="http://www.w3.org/2000/svg" width="45" height="45" viewBox="0 0 45 45" fill="none">
              <path fill-rule="evenodd" clip-rule="evenodd" d="M25.1513 4.31233C25.1499 4.31095 25.1499 4.30958 25.1486 4.3082C24.6687 3.30033 23.6526 2.6582 22.5361 2.6582C21.4196 2.6582 20.4034 3.30033 19.9236 4.3082C19.9222 4.30958 19.9222 4.31095 19.9208 4.31233C19.9208 4.31233 10.9489 23.4482 10.9489 31.6336C10.9489 38.0287 16.1409 43.2207 22.5361 43.2207C28.9312 43.2207 34.1232 38.0287 34.1232 31.6336C34.1232 23.4482 25.1513 4.31233 25.1513 4.31233Z" fill="url(#paint0_linear_30_4317)"/>
              <path fill-rule="evenodd" clip-rule="evenodd" d="M29.2832 25.0937C29.9679 27.5811 30.3983 29.8704 30.3983 31.6346C30.3983 35.9727 26.8755 39.4954 22.536 39.4954C18.1965 39.4954 14.6738 35.9727 14.6738 31.6346C14.6738 30.9924 14.7288 30.2857 14.8539 29.5281C14.9337 28.9753 15.2815 28.4954 15.7848 28.2493C16.2935 27.9991 16.893 28.0197 17.3839 28.3043C17.3908 28.3084 17.3977 28.3126 17.4045 28.3167C19.6265 29.6738 21.3632 28.8419 23.8698 26.3367C24.9134 25.2917 25.8952 24.5313 26.8302 24.0253C26.8398 24.0198 26.8508 24.0143 26.8618 24.0088C27.3224 23.7806 27.86 23.7709 28.3289 23.9799C28.7964 24.1903 29.147 24.5987 29.2832 25.0937Z" fill="url(#paint1_linear_30_4317)"/>
              <path fill-rule="evenodd" clip-rule="evenodd" d="M15.7889 25.0937C15.1042 27.5811 14.6738 29.8704 14.6738 31.6346C14.6738 35.9727 18.1965 39.4954 22.536 39.4954C26.8755 39.4954 30.3983 35.9727 30.3983 31.6346C30.3983 30.9924 30.3433 30.2857 30.2182 29.5281C30.1384 28.9753 29.7905 28.4954 29.2873 28.2493C28.7785 27.9991 28.179 28.0197 27.6882 28.3043C27.6813 28.3084 27.6744 28.3126 27.6675 28.3167C25.4455 29.6738 23.7089 28.8419 21.2023 26.3367C20.1587 25.2917 19.1769 24.5313 18.2419 24.0253C18.2323 24.0198 18.2213 24.0143 18.2103 24.0088C17.7497 23.7806 17.212 23.7709 16.7432 23.9799C16.2757 24.1903 15.925 24.5987 15.7889 25.0937Z" fill="url(#paint2_linear_30_4317)"/>
              <defs>
                <linearGradient id="paint0_linear_30_4317" x1="23.2667" y1="32.8529" x2="23.2667" y2="75.7826" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#56C2EF"/>
                  <stop offset="1" stop-color="#1687C9"/>
                </linearGradient>
                <linearGradient id="paint1_linear_30_4317" x1="27.1365" y1="25.6904" x2="24.5985" y2="34.6279" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#E2F4FD"/>
                  <stop offset="1" stop-color="#41B3E6"/>
                </linearGradient>
                <linearGradient id="paint2_linear_30_4317" x1="22.536" y1="32.5654" x2="22.536" y2="67.7117" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#E2F4FD"/>
                  <stop offset="1" stop-color="#41B3E6"/>
                </linearGradient>
              </defs>
            </svg>Umidade</h1>
            <span class="card--nums" id="humidity"></span>
          </div>

          <div class="c5-info">
            <h1 class="card--title"><svg xmlns="http://www.w3.org/2000/svg" width="44" height="45" viewBox="0 0 44 45" fill="none">
                <path fill-rule="evenodd" clip-rule="evenodd" d="M40.22 5.84973C40.22 6.29386 40.044 6.71873 39.7305 7.03223C39.417 7.34573 38.9907 7.52173 38.548 7.52173H26.4741C25.9049 7.52173 25.4429 7.98511 25.4429 8.55298C25.4429 9.12223 25.9049 9.58423 26.4741 9.58423C26.4741 9.58423 34.9634 9.58423 38.548 9.58423C39.538 9.58423 40.4881 9.19098 41.188 8.49111C41.8892 7.79123 42.2825 6.84111 42.2825 5.84973C42.2825 4.85973 41.8892 3.90961 41.188 3.20973C40.4881 2.50986 39.538 2.11523 38.548 2.11523C37.9787 2.11523 37.5167 2.57861 37.5167 3.14648C37.5167 3.71573 37.9787 4.17773 38.548 4.17773C38.9907 4.17773 39.417 4.35511 39.7305 4.66861C40.044 4.98211 40.22 5.40698 40.22 5.84973Z" fill="url(#paint0_linear_101_5185)" />
                <path fill-rule="evenodd" clip-rule="evenodd" d="M5.45325 6.74023C4.46325 6.74023 3.51313 7.13348 2.81325 7.83473C2.112 8.53461 1.71875 9.48473 1.71875 10.4747C1.71875 10.4747 1.71875 11.044 1.71875 10.4747C1.71875 11.4661 2.112 12.4149 2.81325 13.1161C3.51313 13.816 4.46325 14.2092 5.45325 14.2092C9.03788 14.2092 17.5271 14.2092 17.5271 14.2092C18.0964 14.2092 18.5584 13.7472 18.5584 13.178C18.5584 12.6087 18.0964 12.1467 17.5271 12.1467C17.5271 12.1467 9.03788 12.1467 5.45325 12.1467C5.0105 12.1467 4.58425 11.9707 4.27075 11.6572C3.95725 11.3437 3.78125 10.9189 3.78125 10.4747C3.78125 10.4747 3.78125 11.044 3.78125 10.4747C3.78125 10.032 3.95725 9.60574 4.27075 9.29223C4.58425 8.97873 5.0105 8.80273 5.45325 8.80273C6.0225 8.80273 6.4845 8.34073 6.4845 7.77148C6.4845 7.20223 6.0225 6.74023 5.45325 6.74023Z" fill="url(#paint1_linear_101_5185)" />
                <path fill-rule="evenodd" clip-rule="evenodd" d="M32.5768 2.11523C30.2709 2.11523 23.8772 2.11523 23.8772 2.11523C23.3079 2.11523 22.8459 2.57861 22.8459 3.14648C22.8459 3.71573 23.3079 4.17773 23.8772 4.17773C23.8772 4.17773 30.2709 4.17773 32.5768 4.17773C33.1461 4.17773 33.6081 3.71573 33.6081 3.14648C33.6081 2.57861 33.1461 2.11523 32.5768 2.11523Z" fill="url(#paint2_linear_101_5185)" />
                <path fill-rule="evenodd" clip-rule="evenodd" d="M11.4243 8.80273C13.7302 8.80273 20.1239 8.80273 20.1239 8.80273C20.6932 8.80273 21.1552 8.34073 21.1552 7.77148C21.1552 7.20223 20.6932 6.74023 20.1239 6.74023C20.1239 6.74023 13.7302 6.74023 11.4243 6.74023C10.8551 6.74023 10.3931 7.20223 10.3931 7.77148C10.3931 8.34073 10.8551 8.80273 11.4243 8.80273Z" fill="url(#paint3_linear_101_5185)" />
                <path fill-rule="evenodd" clip-rule="evenodd" d="M34.1349 18.7023C34.1349 18.8893 34.0606 19.0694 33.9286 19.2014C33.7953 19.3348 33.6151 19.409 33.4281 19.409H24.7285C24.1593 19.409 23.6973 19.871 23.6973 20.4403C23.6973 21.0095 24.1593 21.4715 24.7285 21.4715C24.7285 21.4715 31.1223 21.4715 33.4281 21.4715C34.1624 21.4715 34.8678 21.18 35.3861 20.6603C35.9059 20.1405 36.1974 19.4365 36.1974 18.7023C36.1974 17.9666 35.9059 17.2626 35.3861 16.7429C34.8678 16.2231 34.1624 15.9316 33.4281 15.9316C32.8589 15.9316 32.3969 16.3936 32.3969 16.9629C32.3969 17.5321 32.8589 17.9941 33.4281 17.9941C33.6151 17.9941 33.7953 18.0684 33.9286 18.2018C34.0606 18.3338 34.1349 18.5139 34.1349 18.7023Z" fill="url(#paint4_linear_101_5185)" />
                <path fill-rule="evenodd" clip-rule="evenodd" d="M38.8788 12.0098H21.5139C20.9447 12.0098 20.4827 12.4718 20.4827 13.041C20.4827 13.6103 20.9447 14.0723 21.5139 14.0723H38.8788C39.448 14.0723 39.91 13.6103 39.91 13.041C39.91 12.4718 39.448 12.0098 38.8788 12.0098Z" fill="url(#paint5_linear_101_5185)" />
                <path fill-rule="evenodd" clip-rule="evenodd" d="M5.12134 18.6982H22.4862C23.0555 18.6982 23.5175 18.2362 23.5175 17.667C23.5175 17.0977 23.0555 16.6357 22.4862 16.6357H5.12134C4.55209 16.6357 4.09009 17.0977 4.09009 17.667C4.09009 18.2362 4.55209 18.6982 5.12134 18.6982Z" fill="url(#paint6_linear_101_5185)" />
                <path fill-rule="evenodd" clip-rule="evenodd" d="M8.03825 22.8829C4.53063 23.0025 1.71875 25.8886 1.71875 29.4265C1.71875 31.8437 3.00988 35.9756 7.90213 35.9756C19.6721 35.9756 19.6721 35.9756 19.6721 35.9756C19.8234 35.9756 19.9705 35.9715 20.1163 35.9619C20.5796 35.9316 20.9674 35.5961 21.0609 35.1396C21.406 33.4621 22.6903 32.1242 24.3389 31.7021C24.7844 31.588 25.1006 31.1934 25.1144 30.7341L25.1171 30.5306C25.1171 27.8205 23.1371 25.5724 20.5452 25.1557C19.8027 22.1115 17.0555 19.8496 13.7844 19.8496C11.4001 19.8496 9.29363 21.0514 8.03825 22.8829Z" fill="url(#paint7_linear_101_5185)" />
                <path fill-rule="evenodd" clip-rule="evenodd" d="M25.2258 29.504C21.7181 29.6236 18.9062 32.5097 18.9062 36.0476C18.9062 38.4648 20.1974 42.5967 25.0896 42.5967C36.8596 42.5967 36.8596 42.5967 36.8596 42.5967C38.6334 42.5967 39.9836 41.9601 40.9008 40.9756C41.8138 39.9952 42.3046 38.6477 42.3046 37.1517C42.3046 34.4416 40.3246 32.1935 37.7327 31.7768C36.9902 28.7326 34.243 26.4707 30.9719 26.4707C28.5876 26.4707 26.4811 27.6725 25.2258 29.504Z" fill="url(#paint8_linear_101_5185)" />
                <defs>
                  <linearGradient id="paint0_linear_101_5185" x1="23.9265" y1="14.064" x2="23.9265" y2="50.427" gradientUnits="userSpaceOnUse">
                    <stop stop-color="#6DBEFF" />
                    <stop offset="1" stop-color="#0085F0" />
                  </linearGradient>
                  <linearGradient id="paint1_linear_101_5185" x1="23.9253" y1="14.0635" x2="23.9253" y2="50.4265" gradientUnits="userSpaceOnUse">
                    <stop stop-color="#6DBEFF" />
                    <stop offset="1" stop-color="#0085F0" />
                  </linearGradient>
                  <linearGradient id="paint2_linear_101_5185" x1="23.9256" y1="14.064" x2="23.9256" y2="50.427" gradientUnits="userSpaceOnUse">
                    <stop stop-color="#6DBEFF" />
                    <stop offset="1" stop-color="#0085F0" />
                  </linearGradient>
                  <linearGradient id="paint3_linear_101_5185" x1="23.9261" y1="14.0635" x2="23.9261" y2="50.4265" gradientUnits="userSpaceOnUse">
                    <stop stop-color="#6DBEFF" />
                    <stop offset="1" stop-color="#0085F0" />
                  </linearGradient>
                  <linearGradient id="paint4_linear_101_5185" x1="23.9244" y1="14.0658" x2="23.9244" y2="50.4287" gradientUnits="userSpaceOnUse">
                    <stop stop-color="#6DBEFF" />
                    <stop offset="1" stop-color="#0085F0" />
                  </linearGradient>
                  <linearGradient id="paint5_linear_101_5185" x1="23.9259" y1="14.064" x2="23.9259" y2="50.427" gradientUnits="userSpaceOnUse">
                    <stop stop-color="#6DBEFF" />
                    <stop offset="1" stop-color="#0085F0" />
                  </linearGradient>
                  <linearGradient id="paint6_linear_101_5185" x1="23.9247" y1="14.0645" x2="23.9247" y2="50.4275" gradientUnits="userSpaceOnUse">
                    <stop stop-color="#6DBEFF" />
                    <stop offset="1" stop-color="#0085F0" />
                  </linearGradient>
                  <linearGradient id="paint7_linear_101_5185" x1="13.0625" y1="30.565" x2="13.0625" y2="49.815" gradientUnits="userSpaceOnUse">
                    <stop stop-color="#E2F4FD" />
                    <stop offset="1" stop-color="#4DC4FF" />
                  </linearGradient>
                  <linearGradient id="paint8_linear_101_5185" x1="31.1119" y1="35.378" x2="31.1119" y2="53.253" gradientUnits="userSpaceOnUse">
                    <stop stop-color="#E2F4FD" />
                    <stop offset="1" stop-color="#4DC4FF" />
                  </linearGradient>
                </defs>
              </svg>Velocidade do Vento</h1>
            <span class="card--nums" id="wind_speed">1</span>
          </div>

        </div>

    </main>

    <footer>
      <svg width="110" height="32" viewBox="0 0 110 32" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M39.9694 19.9315H37.666L38.2017 16.8247H40.505L40.6657 15.9408C40.9514 14.4231 41.6031 13.2804 42.6209 12.5126C43.6387 11.727 45.0046 11.3341 46.7187 11.3341H48.6203L48.0579 14.441H46.2098C45.7099 14.441 45.2903 14.557 44.951 14.7892C44.6296 15.0034 44.4154 15.4052 44.3082 15.9944L44.1475 16.8247H47.3615L46.8259 19.9315H43.6119L41.7906 30.1895H38.1481L39.9694 19.9315ZM51.9657 15.5659C51.3765 15.5659 50.9033 15.4052 50.5462 15.0838C50.1891 14.7624 50.0105 14.3428 50.0105 13.825C50.0105 13.0393 50.2516 12.4055 50.7337 11.9234C51.2336 11.4234 51.8943 11.1734 52.7156 11.1734C53.3049 11.1734 53.778 11.3341 54.1351 11.6555C54.4922 11.9769 54.6708 12.3965 54.6708 12.9143C54.6708 13.7 54.4208 14.3428 53.9209 14.8427C53.4388 15.3248 52.7871 15.5659 51.9657 15.5659ZM49.9034 16.8247H53.5459L51.189 30.1895H47.5465L49.9034 16.8247ZM59.8422 30.4037C58.3067 30.4037 57.0836 30.0555 56.173 29.3592C55.2802 28.6628 54.8338 27.7254 54.8338 26.5469C54.8338 26.2791 54.8606 26.0113 54.9141 25.7435H58.5031C58.4852 25.8149 58.4763 25.9131 58.4763 26.0381C58.4763 26.4487 58.6102 26.7701 58.8781 27.0023C59.1459 27.2344 59.5208 27.3504 60.0029 27.3504H62.4134C62.9312 27.3504 63.3419 27.279 63.6454 27.1362C63.949 26.9755 64.1275 26.7523 64.1811 26.4666L64.2615 26.0113C64.2972 25.8327 64.2347 25.672 64.074 25.5292C63.9311 25.3685 63.7169 25.2614 63.4312 25.2078L58.9316 24.4043C57.9853 24.2257 57.2443 23.8954 56.7086 23.4133C56.173 22.9134 55.9051 22.3152 55.9051 21.6189C55.9051 21.5117 55.923 21.351 55.9587 21.1368L56.1194 20.2529C56.3158 19.1102 56.905 18.2174 57.8871 17.5746C58.887 16.9318 60.1636 16.6104 61.7171 16.6104H63.8061C65.2524 16.6104 66.3952 16.9407 67.2344 17.6014C68.0914 18.2442 68.52 19.1102 68.52 20.1993C68.52 20.4315 68.4932 20.6814 68.4396 20.9493H64.8507C64.8685 20.8957 64.8775 20.8154 64.8775 20.7082C64.8775 20.3868 64.7614 20.1369 64.5293 19.9583C64.315 19.7619 64.0204 19.6637 63.6454 19.6637H61.6099C61.0743 19.6637 60.6368 19.7351 60.2976 19.878C59.9762 20.0208 59.7887 20.2172 59.7351 20.4672L59.6548 20.8957C59.6191 21.0743 59.6637 21.235 59.7887 21.3778C59.9137 21.5206 60.119 21.6189 60.4047 21.6724L65.1185 22.5563C66.0113 22.7348 66.7076 23.0741 67.2076 23.574C67.7254 24.0561 67.9843 24.6186 67.9843 25.2614C67.9843 25.4399 67.9754 25.5738 67.9575 25.6631L67.7968 26.6273C67.6004 27.8236 67.0112 28.7521 66.0291 29.4127C65.065 30.0734 63.8061 30.4037 62.2527 30.4037H59.8422ZM71.1133 30.4573C70.5598 30.4573 70.1134 30.2966 69.7742 29.9752C69.4349 29.6538 69.2653 29.2342 69.2653 28.7164C69.2653 27.9307 69.4974 27.2969 69.9617 26.8148C70.4438 26.3148 71.0776 26.0649 71.8633 26.0649C72.4168 26.0649 72.8632 26.2256 73.2024 26.5469C73.5417 26.8683 73.7113 27.2879 73.7113 27.8058C73.7113 28.5914 73.4702 29.2342 72.9882 29.7341C72.5239 30.2162 71.899 30.4573 71.1133 30.4573ZM87.9126 25.8238H80.8687L78.4582 30.1895H74.4675L85.1004 11.4413H86.761C87.9216 11.4413 88.6179 11.9769 88.85 13.0483L92.4925 30.1895H88.7697L87.9126 25.8238ZM82.4221 22.717H87.4573L86.1717 15.9676H86.1449L82.4221 22.717ZM97.8134 11.4413H101.509L98.2151 30.1895H94.5191L97.8134 11.4413Z" fill="white" />
        <path d="M11.0517 21.4659L14.14 28.0333L10.3875 31.5877L4.22559 29.2224L1.10611 23.3945L4.15219 19.2162L11.0517 21.4659ZM15.997 16.3463L11.6463 21.2237L14.7217 27.7984L22.0506 30.4078L27.3079 26.3231L24.3847 18.7996L15.997 16.3463ZM4.06961 5.80428L0.636353 11.5937L4.14485 18.5941L11.0958 20.8273L15.4447 15.8417L11.9711 7.76771L4.06961 5.80428ZM17.9146 0.413086L12.7161 7.48512L16.1732 15.6013L24.6747 18.029L31.0733 12.0175L27.8492 2.43157L17.9146 0.413086Z" fill="white" />
      </svg>

      <svg class="logo_footer" width="391" height="26" viewBox="0 0 391 26" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M11.9858 9.34855C12.863 10.0379 13.3006 11.0122 13.2985 12.2713C13.2985 14.0897 12.7113 15.4943 11.5368 16.485C10.3624 17.4758 8.74933 17.9712 6.69765 17.9712H2.40956L1.48074 22.6648H0.421875L3.29195 8.31445H8.29523C9.88043 8.31445 11.1106 8.65915 11.9858 9.34855ZM10.7969 15.8503C11.7546 15.0577 12.2335 13.8957 12.2335 12.3641C12.2574 11.927 12.1756 11.4906 11.995 11.0918C11.8145 10.6929 11.5405 10.3435 11.1963 10.073C10.5069 9.53638 9.51922 9.26908 8.23331 9.27115H4.15266L2.58914 17.0269H6.69765C8.47481 17.0269 9.84121 16.6306 10.7969 15.838V15.8503Z" fill="white" />
        <path d="M18.0356 22.0304C17.0965 21.5808 16.3144 20.8591 15.7909 19.9591C15.2625 19.0143 14.9964 17.9453 15.02 16.863C15.0078 15.36 15.3707 13.8776 16.0758 12.5502C16.7719 11.2405 17.8152 10.1479 19.0914 9.39216C20.4603 8.58947 22.0251 8.1822 23.6117 8.21565C24.8388 8.18327 26.0566 8.43659 27.1691 8.95561C28.1122 9.40397 28.8986 10.1257 29.4261 11.0269C29.9522 11.9725 30.2172 13.0411 30.1939 14.123C30.2059 15.6265 29.8385 17.1088 29.1258 18.4327C28.4298 19.7394 27.3903 20.8313 26.1195 21.5908C24.7448 22.3959 23.1734 22.8032 21.5806 22.7673C20.3577 22.8014 19.1437 22.5491 18.0356 22.0304ZM25.5808 20.7703C26.6957 20.1008 27.6042 19.1366 28.2063 17.9838C28.8255 16.805 29.1445 15.4917 29.1351 14.1601C29.1351 12.6276 28.6552 11.417 27.6923 10.5191C26.7294 9.62127 25.3362 9.17543 23.5312 9.17543C22.1608 9.14997 20.8107 9.50815 19.6332 10.2095C18.5166 10.8799 17.6053 11.8437 16.9984 12.996C16.3753 14.1734 16.056 15.4877 16.0696 16.8197C16.0696 18.3368 16.5546 19.5463 17.5247 20.4483C18.4948 21.3503 19.8819 21.8013 21.6859 21.8013C23.0549 21.8271 24.4038 21.47 25.5808 20.7703Z" fill="white" />
        <path d="M53.8975 8.31445L46.1572 22.6648H45.0488L43.1633 9.83154L36.1197 22.6648H35.0113L33.002 8.31445H34.0484L35.8535 21.2716L42.9497 8.31445H43.9312L45.8198 21.2716L52.8324 8.31445H53.8975Z" fill="white" />
        <path d="M57.7706 9.25616L56.6436 14.9158H64.2724L64.0866 15.8446H56.4609L55.272 21.7272H64.1269L63.9225 22.656H54.0398L56.9099 8.30566H66.5078L66.3003 9.23449L57.7706 9.25616Z" fill="white" />
        <path d="M79.4557 15.8914C78.5903 16.8732 77.4145 17.5289 76.1243 17.7491L78.8922 22.6687H77.7436L75.0593 17.9131C74.6196 17.941 74.2853 17.9534 74.053 17.9534H69.7464L68.8176 22.6687H67.7742L70.6442 8.31836H75.6568C77.2461 8.31836 78.4732 8.66306 79.3381 9.35245C80.2029 10.0418 80.6374 11.0161 80.6415 12.2752C80.6374 13.7489 80.2421 14.9543 79.4557 15.8914ZM78.1523 15.8388C79.1079 15.0462 79.5868 13.8841 79.5889 12.3526C79.6111 11.9177 79.5288 11.4839 79.3489 11.0875C79.169 10.691 78.8967 10.3434 78.5548 10.0738C77.8643 9.53822 76.8736 9.27196 75.5918 9.27196H71.4895L69.9414 17.0431H74.0623C75.8333 17.0328 77.1966 16.6314 78.1523 15.8388Z" fill="white" />
        <path d="M86.2517 9.25616L85.1247 14.9158H92.7503L92.5677 15.8446H84.9451L83.7562 21.7272H92.6141L92.4098 22.656H82.5209L85.3909 8.30566H94.9888L94.7845 9.23449L86.2517 9.25616Z" fill="white" />
        <path d="M99.1065 8.31457H104.45C105.695 8.28097 106.931 8.5253 108.07 9.02977C109.011 9.46364 109.8 10.1715 110.333 11.0608C110.867 11.9891 111.137 13.0459 111.113 14.1166C111.145 15.6625 110.769 17.1895 110.023 18.5441C109.292 19.8363 108.203 20.8899 106.887 21.5782C105.437 22.3269 103.822 22.7005 102.19 22.665H96.2365L99.1065 8.31457ZM102.246 21.7237C103.682 21.7556 105.102 21.4244 106.376 20.7609C107.524 20.1477 108.468 19.214 109.095 18.0735C109.743 16.8714 110.072 15.5226 110.048 14.1569C110.048 12.6398 109.563 11.4437 108.593 10.5685C107.623 9.69337 106.195 9.25579 104.308 9.25579H99.9734L97.4718 21.7237H102.246Z" fill="white" />
        <path d="M130.297 16.2997C130.748 16.8421 130.981 17.5331 130.95 18.2379C130.982 18.8766 130.852 19.513 130.573 20.0883C130.294 20.6635 129.874 21.1591 129.353 21.529C128.283 22.2927 126.8 22.6746 124.903 22.6746H118.442L121.315 8.32422H127.26C128.613 8.32422 129.671 8.5781 130.427 9.09205C130.793 9.33112 131.091 9.6616 131.291 10.0509C131.491 10.4402 131.586 10.8748 131.566 11.3119C131.6 12.2388 131.293 13.1459 130.706 13.8631C130.101 14.5589 129.3 15.0555 128.408 15.2873C129.13 15.4128 129.793 15.7679 130.297 16.2997ZM128.634 20.8603C129.048 20.5731 129.382 20.1854 129.604 19.7337C129.827 19.282 129.931 18.7811 129.907 18.2782C129.907 17.4174 129.605 16.7982 129.003 16.4205C128.4 16.0428 127.491 15.8508 126.275 15.8446H120.86L119.671 21.7705H125.003C126.575 21.7664 127.786 21.463 128.634 20.8603ZM121.027 14.9375H125.928C127.293 14.9375 128.393 14.6402 129.229 14.0458C129.635 13.7556 129.961 13.3677 130.177 12.918C130.394 12.4683 130.494 11.9713 130.467 11.4729C130.485 11.1376 130.412 10.8036 130.257 10.5057C130.102 10.2079 129.87 9.95707 129.585 9.77938C128.996 9.40475 128.157 9.21589 127.061 9.21589H122.176L121.027 14.9375Z" fill="white" />
        <path d="M138.925 17.8473L137.963 22.6648H136.916L137.901 17.7111L134.006 8.31445H135.102L138.607 16.8039L145.477 8.31445H146.644L138.925 17.8473Z" fill="white" />
        <path d="M154.917 3.33984H160.384V22.6656H154.917V3.33984Z" fill="white" />
        <path d="M182.652 3.33984V22.6656H178.137L169.617 12.368V22.6656H164.261V3.33984H168.762L177.292 13.6374V3.33984H182.652Z" fill="white" />
        <path d="M186.519 3.33984H191.983V22.6656H186.519V3.33984Z" fill="white" />
        <path d="M200.058 21.77C198.487 20.9491 197.174 19.7106 196.262 18.1909C195.331 16.6222 194.853 14.826 194.881 13.0018C194.853 11.1768 195.331 9.37962 196.262 7.80969C197.173 6.29136 198.487 5.05478 200.058 4.2368C201.741 3.36257 203.616 2.92101 205.513 2.95193C207.153 2.92373 208.78 3.24016 210.29 3.88075C211.671 4.48047 212.884 5.40958 213.823 6.58674L210.337 9.74475C209.084 8.23386 207.565 7.47841 205.779 7.47841C204.806 7.46413 203.846 7.70199 202.993 8.16884C202.183 8.62057 201.52 9.29686 201.086 10.1163C200.624 11.0068 200.392 11.9988 200.411 13.0018C200.391 14.005 200.623 14.997 201.086 15.8874C201.519 16.7074 202.182 17.384 202.993 17.8348C203.846 18.3017 204.806 18.5395 205.779 18.5253C207.579 18.5253 209.098 17.7719 210.337 16.2651L213.814 19.4138C212.875 20.591 211.662 21.5201 210.281 22.1198C208.771 22.7604 207.144 23.0769 205.504 23.0487C203.611 23.079 201.74 22.6397 200.058 21.77Z" fill="white" />
        <path d="M216.254 3.33984H221.721V22.6656H216.254V3.33984Z" fill="white" />
        <path d="M238.561 18.9101H230.39L228.87 22.6656H223.297L231.824 3.33984H237.208L245.769 22.6656H240.081L238.561 18.9101ZM236.96 14.8852L234.483 8.69298L232.006 14.8852H236.96Z" fill="white" />
        <path d="M250.462 7.67437H244.527V3.33984H261.84V7.67437H255.93V22.6656H250.462V7.67437Z" fill="white" />
        <path d="M263.899 3.33984H269.348V22.6656H263.899V3.33984Z" fill="white" />
        <path d="M292.789 3.33984L284.507 22.6656H279.123L270.865 3.33984H276.776L282.021 15.9285L287.377 3.33984H292.789Z" fill="white" />
        <path d="M306.21 18.9101H298.037L296.52 22.6656H290.947L299.473 3.33984H304.858L313.418 22.6656H307.731L306.21 18.9101ZM304.61 14.8852L302.133 8.69298L299.656 14.8852H304.61Z" fill="white" />
        <path d="M320.431 7.56291V11.8169H328.963V16.04H320.431V22.6656H314.963V3.33984H330.134V7.56291H320.431Z" fill="white" />
        <path d="M332.691 3.33984H338.156V22.6656H332.691V3.33984Z" fill="white" />
        <path d="M344.286 22.4734C343.008 22.1731 341.793 21.649 340.698 20.9253L342.49 16.9004C343.422 17.5022 344.436 17.9672 345.5 18.2813C346.59 18.6235 347.725 18.8009 348.868 18.8076C350.967 18.8076 352.017 18.2823 352.017 17.2317C352.017 16.6806 351.718 16.2678 351.119 15.9933C350.185 15.6254 349.219 15.3435 348.234 15.1511C346.997 14.8976 345.78 14.5604 344.589 14.1418C343.62 13.7866 342.756 13.1936 342.075 12.4173C341.376 11.6247 341.027 10.5565 341.029 9.21282C341.016 8.07582 341.353 6.96232 341.995 6.02385C342.719 5.01241 343.72 4.23183 344.877 3.77609C346.375 3.18479 347.977 2.90458 349.586 2.95253C350.851 2.9518 352.111 3.09515 353.342 3.37979C354.485 3.63085 355.584 4.05472 356.599 4.6368L354.924 8.69577C353.292 7.75793 351.45 7.24481 349.568 7.20346C348.481 7.20346 347.692 7.36445 347.193 7.68645C346.969 7.81168 346.783 7.99396 346.652 8.21476C346.522 8.43555 346.452 8.68698 346.45 8.94346C346.45 9.46051 346.76 9.84442 347.333 10.1045C348.253 10.4579 349.205 10.7253 350.175 10.9033C351.417 11.1519 352.64 11.4892 353.834 11.9126C354.798 12.2702 355.66 12.858 356.345 13.6247C357.053 14.4091 357.408 15.4721 357.41 16.8137C357.421 17.9369 357.084 19.0359 356.444 19.9593C355.711 20.9692 354.706 21.7498 353.546 22.2102C352.055 22.8103 350.456 23.097 348.85 23.0523C347.31 23.0572 345.776 22.8626 344.286 22.4734Z" fill="white" />
        <path d="M372.41 11.0134C373.51 10.6083 374.58 11.678 374.175 12.7789L371.776 19.2998C371.723 19.4443 371.634 19.5731 371.518 19.6743C371.402 19.7755 371.263 19.8459 371.113 19.8789C370.962 19.912 370.806 19.9067 370.658 19.8635C370.511 19.8202 370.376 19.7405 370.267 19.6316L365.558 14.922C365.449 14.8132 365.369 14.6788 365.326 14.5311C365.283 14.3835 365.278 14.2274 365.311 14.0773C365.344 13.9271 365.414 13.7876 365.515 13.6717C365.616 13.5558 365.745 13.4672 365.889 13.4141L372.41 11.0125V11.0134Z" fill="url(#paint0_linear_101_5103)" />
        <path d="M372.41 11.0134C373.51 10.6083 374.58 11.678 374.175 12.7789L371.776 19.2998C371.723 19.4443 371.634 19.5731 371.518 19.6743C371.402 19.7755 371.263 19.8459 371.113 19.8789C370.962 19.912 370.806 19.9067 370.658 19.8635C370.511 19.8202 370.376 19.7405 370.267 19.6316L365.558 14.922C365.449 14.8132 365.369 14.6788 365.326 14.5311C365.283 14.3835 365.278 14.2274 365.311 14.0773C365.344 13.9271 365.414 13.7876 365.515 13.6717C365.616 13.5558 365.745 13.4672 365.889 13.4141L372.41 11.0125V11.0134Z" fill="url(#paint1_radial_101_5103)" />
        <path d="M372.41 11.0134C373.51 10.6083 374.58 11.678 374.175 12.7789L371.776 19.2998C371.723 19.4443 371.634 19.5731 371.518 19.6743C371.402 19.7755 371.263 19.8459 371.113 19.8789C370.962 19.912 370.806 19.9067 370.658 19.8635C370.511 19.8202 370.376 19.7405 370.267 19.6316L365.558 14.922C365.449 14.8132 365.369 14.6788 365.326 14.5311C365.283 14.3835 365.278 14.2274 365.311 14.0773C365.344 13.9271 365.414 13.7876 365.515 13.6717C365.616 13.5558 365.745 13.4672 365.889 13.4141L372.41 11.0125V11.0134Z" fill="url(#paint2_linear_101_5103)" />
        <path d="M377.909 16.5134C379.01 16.1083 380.08 17.178 379.675 18.2789L377.274 24.7998C377.221 24.9441 377.132 25.0727 377.016 25.1738C376.901 25.2749 376.761 25.3452 376.611 25.3782C376.461 25.4113 376.305 25.406 376.157 25.3629C376.009 25.3198 375.875 25.2403 375.766 25.1316L371.056 20.422C370.948 20.3132 370.868 20.1788 370.825 20.0311C370.782 19.8835 370.777 19.7274 370.81 19.5773C370.843 19.4271 370.913 19.2876 371.014 19.1717C371.115 19.0558 371.244 18.9672 371.388 18.9141L377.909 16.5125V16.5134Z" fill="url(#paint3_linear_101_5103)" />
        <path d="M377.909 16.5134C379.01 16.1083 380.08 17.178 379.675 18.2789L377.274 24.7998C377.221 24.9441 377.132 25.0727 377.016 25.1738C376.901 25.2749 376.761 25.3452 376.611 25.3782C376.461 25.4113 376.305 25.406 376.157 25.3629C376.009 25.3198 375.875 25.2403 375.766 25.1316L371.056 20.422C370.948 20.3132 370.868 20.1788 370.825 20.0311C370.782 19.8835 370.777 19.7274 370.81 19.5773C370.843 19.4271 370.913 19.2876 371.014 19.1717C371.115 19.0558 371.244 18.9672 371.388 18.9141L377.909 16.5125V16.5134Z" fill="url(#paint4_radial_101_5103)" />
        <path d="M377.909 16.5134C379.01 16.1083 380.08 17.178 379.675 18.2789L377.274 24.7998C377.221 24.9441 377.132 25.0727 377.016 25.1738C376.901 25.2749 376.761 25.3452 376.611 25.3782C376.461 25.4113 376.305 25.406 376.157 25.3629C376.009 25.3198 375.875 25.2403 375.766 25.1316L371.056 20.422C370.948 20.3132 370.868 20.1788 370.825 20.0311C370.782 19.8835 370.777 19.7274 370.81 19.5773C370.843 19.4271 370.913 19.2876 371.014 19.1717C371.115 19.0558 371.244 18.9672 371.388 18.9141L377.909 16.5125V16.5134Z" fill="url(#paint5_radial_101_5103)" />
        <g filter="url(#filter0_i_101_5103)">
          <path d="M383.243 1.69328C383.268 1.68333 383.295 1.68098 383.322 1.68653C383.348 1.69207 383.372 1.70525 383.391 1.72445L388.786 7.16009C388.805 7.17916 388.818 7.20339 388.823 7.22979C388.828 7.25619 388.826 7.28359 388.816 7.30859C387.523 10.4801 385.742 13.8534 383.358 16.2384C381.035 18.5612 377.107 20.5402 373.559 21.9958L368.526 16.9617C369.982 13.4143 371.961 9.48651 374.284 7.16376C376.676 4.77134 380.062 2.98665 383.242 1.6942L383.243 1.69328Z" fill="url(#paint6_linear_101_5103)" />
          <path d="M383.243 1.69328C383.268 1.68333 383.295 1.68098 383.322 1.68653C383.348 1.69207 383.372 1.70525 383.391 1.72445L388.786 7.16009C388.805 7.17916 388.818 7.20339 388.823 7.22979C388.828 7.25619 388.826 7.28359 388.816 7.30859C387.523 10.4801 385.742 13.8534 383.358 16.2384C381.035 18.5612 377.107 20.5402 373.559 21.9958L368.526 16.9617C369.982 13.4143 371.961 9.48651 374.284 7.16376C376.676 4.77134 380.062 2.98665 383.242 1.6942L383.243 1.69328Z" fill="url(#paint7_radial_101_5103)" />
          <path d="M383.243 1.69328C383.268 1.68333 383.295 1.68098 383.322 1.68653C383.348 1.69207 383.372 1.70525 383.391 1.72445L388.786 7.16009C388.805 7.17916 388.818 7.20339 388.823 7.22979C388.828 7.25619 388.826 7.28359 388.816 7.30859C387.523 10.4801 385.742 13.8534 383.358 16.2384C381.035 18.5612 377.107 20.5402 373.559 21.9958L368.526 16.9617C369.982 13.4143 371.961 9.48651 374.284 7.16376C376.676 4.77134 380.062 2.98665 383.242 1.6942L383.243 1.69328Z" fill="url(#paint8_radial_101_5103)" />
          <path d="M383.243 1.69328C383.268 1.68333 383.295 1.68098 383.322 1.68653C383.348 1.69207 383.372 1.70525 383.391 1.72445L388.786 7.16009C388.805 7.17916 388.818 7.20339 388.823 7.22979C388.828 7.25619 388.826 7.28359 388.816 7.30859C387.523 10.4801 385.742 13.8534 383.358 16.2384C381.035 18.5612 377.107 20.5402 373.559 21.9958L368.526 16.9617C369.982 13.4143 371.961 9.48651 374.284 7.16376C376.676 4.77134 380.062 2.98665 383.242 1.6942L383.243 1.69328Z" fill="url(#paint9_radial_101_5103)" />
          <path d="M383.243 1.69328C383.268 1.68333 383.295 1.68098 383.322 1.68653C383.348 1.69207 383.372 1.70525 383.391 1.72445L388.786 7.16009C388.805 7.17916 388.818 7.20339 388.823 7.22979C388.828 7.25619 388.826 7.28359 388.816 7.30859C387.523 10.4801 385.742 13.8534 383.358 16.2384C381.035 18.5612 377.107 20.5402 373.559 21.9958L368.526 16.9617C369.982 13.4143 371.961 9.48651 374.284 7.16376C376.676 4.77134 380.062 2.98665 383.242 1.6942L383.243 1.69328Z" fill="url(#paint10_radial_101_5103)" />
        </g>
        <g filter="url(#filter1_iii_101_5103)">
          <path d="M385.168 8.5795C385.175 8.98836 385.1 9.39454 384.949 9.77434C384.797 10.1541 384.571 10.4999 384.285 10.7916C383.998 11.0832 383.656 11.3149 383.279 11.473C382.902 11.6311 382.497 11.7125 382.088 11.7125C381.679 11.7125 381.275 11.6311 380.897 11.473C380.52 11.3149 380.178 11.0832 379.892 10.7916C379.605 10.4999 379.379 10.1541 379.228 9.77434C379.076 9.39454 379.002 8.98836 379.009 8.5795C379.023 7.77198 379.353 7.00225 379.929 6.43611C380.505 5.86997 381.281 5.55273 382.088 5.55273C382.896 5.55273 383.671 5.86997 384.247 6.43611C384.823 7.00225 385.154 7.77198 385.168 8.5795Z" fill="url(#paint11_linear_101_5103)" />
          <path d="M385.168 8.5795C385.175 8.98836 385.1 9.39454 384.949 9.77434C384.797 10.1541 384.571 10.4999 384.285 10.7916C383.998 11.0832 383.656 11.3149 383.279 11.473C382.902 11.6311 382.497 11.7125 382.088 11.7125C381.679 11.7125 381.275 11.6311 380.897 11.473C380.52 11.3149 380.178 11.0832 379.892 10.7916C379.605 10.4999 379.379 10.1541 379.228 9.77434C379.076 9.39454 379.002 8.98836 379.009 8.5795C379.023 7.77198 379.353 7.00225 379.929 6.43611C380.505 5.86997 381.281 5.55273 382.088 5.55273C382.896 5.55273 383.671 5.86997 384.247 6.43611C384.823 7.00225 385.154 7.77198 385.168 8.5795Z" fill="url(#paint12_radial_101_5103)" />
        </g>
        <path d="M384.22 8.5791C384.226 8.86275 384.175 9.14472 384.071 9.40849C383.966 9.67226 383.81 9.91253 383.612 10.1152C383.413 10.3179 383.176 10.4789 382.915 10.5888C382.653 10.6988 382.372 10.7554 382.088 10.7554C381.805 10.7554 381.524 10.6988 381.262 10.5888C381.001 10.4789 380.764 10.3179 380.565 10.1152C380.367 9.91253 380.211 9.67226 380.106 9.40849C380.002 9.14472 379.951 8.86275 379.957 8.5791C379.968 8.02141 380.198 7.49046 380.596 7.10014C380.995 6.70982 381.531 6.49121 382.088 6.49121C382.646 6.49121 383.182 6.70982 383.58 7.10014C383.979 7.49046 384.208 8.02141 384.22 8.5791Z" fill="url(#paint13_radial_101_5103)" />
        <g filter="url(#filter2_i_101_5103)">
          <path d="M364.931 25.5108C364.283 24.8627 364.544 20.3675 366.835 19.4509C366.835 19.4509 369.127 18.5342 370.604 20.0009C372.08 21.4675 371.418 23.1174 371.418 23.1174C370.77 25.0616 368.011 25.8343 367.687 25.5098C367.508 25.3311 367.83 25.0057 367.687 24.8627C367.544 24.7188 367.322 24.8829 366.715 25.1863C366.283 25.4026 365.191 25.7702 364.931 25.5108Z" fill="url(#paint14_radial_101_5103)" />
          <path d="M364.931 25.5108C364.283 24.8627 364.544 20.3675 366.835 19.4509C366.835 19.4509 369.127 18.5342 370.604 20.0009C372.08 21.4675 371.418 23.1174 371.418 23.1174C370.77 25.0616 368.011 25.8343 367.687 25.5098C367.508 25.3311 367.83 25.0057 367.687 24.8627C367.544 24.7188 367.322 24.8829 366.715 25.1863C366.283 25.4026 365.191 25.7702 364.931 25.5108Z" fill="url(#paint15_radial_101_5103)" />
        </g>
        <path d="M368.265 17.6726C368.393 17.5448 368.545 17.4434 368.712 17.3743C368.878 17.3051 369.057 17.2695 369.238 17.2695C369.419 17.2695 369.597 17.3051 369.764 17.3743C369.931 17.4434 370.083 17.5448 370.21 17.6726L373.451 20.9138C373.697 21.1738 373.832 21.5196 373.827 21.8776C373.822 22.2356 373.678 22.5776 373.425 22.8308C373.171 23.0841 372.83 23.2286 372.472 23.2337C372.113 23.2387 371.768 23.1039 371.507 22.858L368.265 19.6177C368.138 19.49 368.036 19.3384 367.967 19.1715C367.898 19.0046 367.862 18.8257 367.862 18.6451C367.862 18.4645 367.898 18.2856 367.967 18.1187C368.036 17.9519 368.138 17.8002 368.265 17.6726Z" fill="url(#paint16_linear_101_5103)" />
        <path d="M368.265 17.6726C368.393 17.5448 368.545 17.4434 368.712 17.3743C368.878 17.3051 369.057 17.2695 369.238 17.2695C369.419 17.2695 369.597 17.3051 369.764 17.3743C369.931 17.4434 370.083 17.5448 370.21 17.6726L373.451 20.9138C373.697 21.1738 373.832 21.5196 373.827 21.8776C373.822 22.2356 373.678 22.5776 373.425 22.8308C373.171 23.0841 372.83 23.2286 372.472 23.2337C372.113 23.2387 371.768 23.1039 371.507 22.858L368.265 19.6177C368.138 19.49 368.036 19.3384 367.967 19.1715C367.898 19.0046 367.862 18.8257 367.862 18.6451C367.862 18.4645 367.898 18.2856 367.967 18.1187C368.036 17.9519 368.138 17.8002 368.265 17.6726Z" fill="url(#paint17_radial_101_5103)" />
        <path d="M368.265 17.6726C368.393 17.5448 368.545 17.4434 368.712 17.3743C368.878 17.3051 369.057 17.2695 369.238 17.2695C369.419 17.2695 369.597 17.3051 369.764 17.3743C369.931 17.4434 370.083 17.5448 370.21 17.6726L373.451 20.9138C373.697 21.1738 373.832 21.5196 373.827 21.8776C373.822 22.2356 373.678 22.5776 373.425 22.8308C373.171 23.0841 372.83 23.2286 372.472 23.2337C372.113 23.2387 371.768 23.1039 371.507 22.858L368.265 19.6177C368.138 19.49 368.036 19.3384 367.967 19.1715C367.898 19.0046 367.862 18.8257 367.862 18.6451C367.862 18.4645 367.898 18.2856 367.967 18.1187C368.036 17.9519 368.138 17.8002 368.265 17.6726Z" fill="url(#paint18_radial_101_5103)" />
        <path d="M389.451 1.07069C388.583 0.202632 387.06 0.300712 385.951 0.682032C385.114 0.968808 384.285 1.27659 383.463 1.60508C383.449 1.61071 383.437 1.61971 383.427 1.63128C383.417 1.64286 383.411 1.65666 383.408 1.67144C383.404 1.68623 383.405 1.70155 383.409 1.71604C383.414 1.73053 383.421 1.74374 383.432 1.7545L388.758 7.11589C388.768 7.12632 388.781 7.13397 388.796 7.13818C388.81 7.14238 388.825 7.14303 388.84 7.14004C388.855 7.13706 388.868 7.13055 388.88 7.12107C388.891 7.11158 388.9 7.09942 388.906 7.08564C389.239 6.25559 389.55 5.41721 389.84 4.57131C390.216 3.47685 390.519 2.13857 389.451 1.07069Z" fill="url(#paint19_linear_101_5103)" />
        <path d="M389.451 1.07069C388.583 0.202632 387.06 0.300712 385.951 0.682032C385.114 0.968808 384.285 1.27659 383.463 1.60508C383.449 1.61071 383.437 1.61971 383.427 1.63128C383.417 1.64286 383.411 1.65666 383.408 1.67144C383.404 1.68623 383.405 1.70155 383.409 1.71604C383.414 1.73053 383.421 1.74374 383.432 1.7545L388.758 7.11589C388.768 7.12632 388.781 7.13397 388.796 7.13818C388.81 7.14238 388.825 7.14303 388.84 7.14004C388.855 7.13706 388.868 7.13055 388.88 7.12107C388.891 7.11158 388.9 7.09942 388.906 7.08564C389.239 6.25559 389.55 5.41721 389.84 4.57131C390.216 3.47685 390.519 2.13857 389.451 1.07069Z" fill="url(#paint20_radial_101_5103)" />
        <path d="M389.451 1.07069C388.583 0.202632 387.06 0.300712 385.951 0.682032C385.114 0.968808 384.285 1.27659 383.463 1.60508C383.449 1.61071 383.437 1.61971 383.427 1.63128C383.417 1.64286 383.411 1.65666 383.408 1.67144C383.404 1.68623 383.405 1.70155 383.409 1.71604C383.414 1.73053 383.421 1.74374 383.432 1.7545L388.758 7.11589C388.768 7.12632 388.781 7.13397 388.796 7.13818C388.81 7.14238 388.825 7.14303 388.84 7.14004C388.855 7.13706 388.868 7.13055 388.88 7.12107C388.891 7.11158 388.9 7.09942 388.906 7.08564C389.239 6.25559 389.55 5.41721 389.84 4.57131C390.216 3.47685 390.519 2.13857 389.451 1.07069Z" fill="url(#paint21_linear_101_5103)" />
        <path d="M375.16 13.7634C376.26 13.3583 377.33 14.428 376.925 15.5289L374.525 22.0498C374.472 22.1943 374.383 22.3231 374.267 22.4243C374.151 22.5255 374.012 22.5959 373.862 22.6289C373.711 22.662 373.555 22.6567 373.407 22.6135C373.26 22.5702 373.125 22.4905 373.016 22.3816L368.307 17.672C368.198 17.5632 368.118 17.4288 368.075 17.2811C368.032 17.1335 368.027 16.9774 368.06 16.8273C368.093 16.6771 368.163 16.5376 368.264 16.4217C368.366 16.3058 368.494 16.2172 368.638 16.1641L375.16 13.7625V13.7634Z" fill="url(#paint22_linear_101_5103)" />
        <path d="M375.16 13.7634C376.26 13.3583 377.33 14.428 376.925 15.5289L374.525 22.0498C374.472 22.1943 374.383 22.3231 374.267 22.4243C374.151 22.5255 374.012 22.5959 373.862 22.6289C373.711 22.662 373.555 22.6567 373.407 22.6135C373.26 22.5702 373.125 22.4905 373.016 22.3816L368.307 17.672C368.198 17.5632 368.118 17.4288 368.075 17.2811C368.032 17.1335 368.027 16.9774 368.06 16.8273C368.093 16.6771 368.163 16.5376 368.264 16.4217C368.366 16.3058 368.494 16.2172 368.638 16.1641L375.16 13.7625V13.7634Z" fill="url(#paint23_radial_101_5103)" />
        <path d="M375.16 13.7634C376.26 13.3583 377.33 14.428 376.925 15.5289L374.525 22.0498C374.472 22.1943 374.383 22.3231 374.267 22.4243C374.151 22.5255 374.012 22.5959 373.862 22.6289C373.711 22.662 373.555 22.6567 373.407 22.6135C373.26 22.5702 373.125 22.4905 373.016 22.3816L368.307 17.672C368.198 17.5632 368.118 17.4288 368.075 17.2811C368.032 17.1335 368.027 16.9774 368.06 16.8273C368.093 16.6771 368.163 16.5376 368.264 16.4217C368.366 16.3058 368.494 16.2172 368.638 16.1641L375.16 13.7625V13.7634Z" fill="url(#paint24_radial_101_5103)" />
        <path d="M375.16 13.7634C376.26 13.3583 377.33 14.428 376.925 15.5289L374.525 22.0498C374.472 22.1943 374.383 22.3231 374.267 22.4243C374.151 22.5255 374.012 22.5959 373.862 22.6289C373.711 22.662 373.555 22.6567 373.407 22.6135C373.26 22.5702 373.125 22.4905 373.016 22.3816L368.307 17.672C368.198 17.5632 368.118 17.4288 368.075 17.2811C368.032 17.1335 368.027 16.9774 368.06 16.8273C368.093 16.6771 368.163 16.5376 368.264 16.4217C368.366 16.3058 368.494 16.2172 368.638 16.1641L375.16 13.7625V13.7634Z" fill="url(#paint25_radial_101_5103)" />
        <g filter="url(#filter3_f_101_5103)">
          <path d="M371.148 18.648L376.304 14.6084L372.981 20.5097L371.148 18.648Z" fill="url(#paint26_linear_101_5103)" />
        </g>
        <defs>
          <filter id="filter0_i_101_5103" x="368.276" y="1.18359" width="20.5497" height="20.8125" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB">
            <feFlood flood-opacity="0" result="BackgroundImageFix" />
            <feBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape" />
            <feColorMatrix in="SourceAlpha" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 127 0" result="hardAlpha" />
            <feOffset dx="-0.25" dy="-0.5" />
            <feGaussianBlur stdDeviation="0.75" />
            <feComposite in2="hardAlpha" operator="arithmetic" k2="-1" k3="1" />
            <feColorMatrix type="matrix" values="0 0 0 0 0.745098 0 0 0 0 0.772549 0 0 0 0 0.952941 0 0 0 1 0" />
            <feBlend mode="normal" in2="shape" result="effect1_innerShadow_101_5103" />
          </filter>
          <filter id="filter1_iii_101_5103" x="378.908" y="5.45273" width="6.35979" height="6.51016" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB">
            <feFlood flood-opacity="0" result="BackgroundImageFix" />
            <feBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape" />
            <feColorMatrix in="SourceAlpha" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 127 0" result="hardAlpha" />
            <feOffset dy="0.25" />
            <feGaussianBlur stdDeviation="0.5" />
            <feComposite in2="hardAlpha" operator="arithmetic" k2="-1" k3="1" />
            <feColorMatrix type="matrix" values="0 0 0 0 0.866667 0 0 0 0 0.764706 0 0 0 0 0.847059 0 0 0 1 0" />
            <feBlend mode="normal" in2="shape" result="effect1_innerShadow_101_5103" />
            <feColorMatrix in="SourceAlpha" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 127 0" result="hardAlpha" />
            <feOffset dx="-0.1" dy="0.1" />
            <feGaussianBlur stdDeviation="0.05" />
            <feComposite in2="hardAlpha" operator="arithmetic" k2="-1" k3="1" />
            <feColorMatrix type="matrix" values="0 0 0 0 0.721569 0 0 0 0 0.690196 0 0 0 0 0.701961 0 0 0 1 0" />
            <feBlend mode="normal" in2="effect1_innerShadow_101_5103" result="effect2_innerShadow_101_5103" />
            <feColorMatrix in="SourceAlpha" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 127 0" result="hardAlpha" />
            <feOffset dx="0.1" dy="-0.1" />
            <feGaussianBlur stdDeviation="0.05" />
            <feComposite in2="hardAlpha" operator="arithmetic" k2="-1" k3="1" />
            <feColorMatrix type="matrix" values="0 0 0 0 0.615686 0 0 0 0 0.560784 0 0 0 0 0.65098 0 0 0 1 0" />
            <feBlend mode="normal" in2="effect2_innerShadow_101_5103" result="effect3_innerShadow_101_5103" />
          </filter>
          <filter id="filter2_i_101_5103" x="364.624" y="18.968" width="6.9425" height="6.63164" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB">
            <feFlood flood-opacity="0" result="BackgroundImageFix" />
            <feBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape" />
            <feColorMatrix in="SourceAlpha" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 127 0" result="hardAlpha" />
            <feOffset dy="-0.2" />
            <feGaussianBlur stdDeviation="0.2" />
            <feComposite in2="hardAlpha" operator="arithmetic" k2="-1" k3="1" />
            <feColorMatrix type="matrix" values="0 0 0 0 0.847059 0 0 0 0 0.505882 0 0 0 0 0.360784 0 0 0 1 0" />
            <feBlend mode="normal" in2="shape" result="effect1_innerShadow_101_5103" />
          </filter>
          <filter id="filter3_f_101_5103" x="370.148" y="13.6084" width="7.15613" height="7.90137" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB">
            <feFlood flood-opacity="0" result="BackgroundImageFix" />
            <feBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape" />
            <feGaussianBlur stdDeviation="0.5" result="effect1_foregroundBlur_101_5103" />
          </filter>
          <linearGradient id="paint0_linear_101_5103" x1="370.145" y1="14.3042" x2="365.562" y2="13.5488" gradientUnits="userSpaceOnUse">
            <stop stop-color="#AD24EE" />
            <stop offset="1" stop-color="#7A12AB" />
          </linearGradient>
          <radialGradient id="paint1_radial_101_5103" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(364.909 14.0796) rotate(-19.9576) scale(7.33462 1.24704)">
            <stop offset="0.164" stop-color="#CD8DFF" />
            <stop offset="1" stop-color="#621487" stop-opacity="0" />
          </radialGradient>
          <linearGradient id="paint2_linear_101_5103" x1="367.207" y1="16.527" x2="367.954" y2="15.7983" gradientUnits="userSpaceOnUse">
            <stop offset="0.491" stop-color="#9B46DD" />
            <stop offset="1" stop-color="#C846DD" stop-opacity="0" />
          </linearGradient>
          <linearGradient id="paint3_linear_101_5103" x1="379.111" y1="18.3045" x2="373.411" y2="22.7768" gradientUnits="userSpaceOnUse">
            <stop stop-color="#7A0FAC" />
            <stop offset="1" stop-color="#701091" />
          </linearGradient>
          <radialGradient id="paint4_radial_101_5103" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(376.075 18.7909) rotate(86.482) scale(7.00224 6.03701)">
            <stop offset="0.757" stop-color="#7219A9" stop-opacity="0" />
            <stop offset="0.951" stop-color="#7415BF" />
          </radialGradient>
          <radialGradient id="paint5_radial_101_5103" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(375.043 22.4862) rotate(-57.346) scale(4.83114 2.12207)">
            <stop stop-color="#6E15A4" />
            <stop offset="1" stop-color="#D458FF" stop-opacity="0" />
          </radialGradient>
          <linearGradient id="paint6_linear_101_5103" x1="375.072" y1="6.38828" x2="383.149" y2="14.5234" gradientUnits="userSpaceOnUse">
            <stop stop-color="#CCBBC0" />
            <stop offset="1" stop-color="#EAD2EC" />
          </linearGradient>
          <radialGradient id="paint7_radial_101_5103" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(384.682 18.2175) rotate(-142.447) scale(15.2866 28.7349)">
            <stop offset="0.811" stop-color="#E7E5E5" stop-opacity="0" />
            <stop offset="1" stop-color="#E7E5E5" />
          </radialGradient>
          <radialGradient id="paint8_radial_101_5103" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(371.126 17.9727) rotate(-56.929) scale(8.98651 4.22358)">
            <stop offset="0.281" stop-color="#B5A3A5" />
            <stop offset="1" stop-color="#B5A3A5" stop-opacity="0" />
          </radialGradient>
          <radialGradient id="paint9_radial_101_5103" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(368.526 16.8551) rotate(-73.625) scale(7.96665 1.34993)">
            <stop offset="0.208" stop-color="#B28F96" />
            <stop offset="1" stop-color="#B28F96" stop-opacity="0" />
          </radialGradient>
          <radialGradient id="paint10_radial_101_5103" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(387.56 4.9565) rotate(137.284) scale(12.0767 3.74967)">
            <stop stop-color="#FAECF1" />
            <stop offset="1" stop-color="#FAECF1" stop-opacity="0" />
          </radialGradient>
          <linearGradient id="paint11_linear_101_5103" x1="379.009" y1="8.0561" x2="385.168" y2="8.5795" gradientUnits="userSpaceOnUse">
            <stop stop-color="#A796A0" />
            <stop offset="1" stop-color="#A5959F" />
          </linearGradient>
          <radialGradient id="paint12_radial_101_5103" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(382.09 8.5795) rotate(90) scale(3.07933)">
            <stop offset="0.587" stop-color="#93859B" />
            <stop offset="1" stop-color="#93859B" stop-opacity="0" />
          </radialGradient>
          <radialGradient id="paint13_radial_101_5103" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(382.088 10.7112) rotate(-90) scale(4.44164 4.08476)">
            <stop stop-color="#72CDFF" />
            <stop offset="0.738" stop-color="#66ACFF" />
            <stop offset="1" stop-color="#3B57F4" />
          </radialGradient>
          <radialGradient id="paint14_radial_101_5103" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(370.219 20.6654) rotate(135) scale(5.3224 4.18353)">
            <stop stop-color="#D46213" />
            <stop offset="1" stop-color="#FF9542" />
          </radialGradient>
          <radialGradient id="paint15_radial_101_5103" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(370.322 24.9947) rotate(-131.186) scale(6.57643 6.93046)">
            <stop offset="0.871" stop-color="#FFC484" stop-opacity="0" />
            <stop offset="1" stop-color="#FFC484" />
          </radialGradient>
          <linearGradient id="paint16_linear_101_5103" x1="368.025" y1="18.5626" x2="373.067" y2="23.5179" gradientUnits="userSpaceOnUse">
            <stop stop-color="#452860" />
            <stop offset="1" stop-color="#51509F" />
          </linearGradient>
          <radialGradient id="paint17_radial_101_5103" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(368.971 18.1043) rotate(77.8285) scale(1.49448 1.32041)">
            <stop stop-color="#8E839A" />
            <stop offset="1" stop-color="#8E839A" stop-opacity="0" />
          </radialGradient>
          <radialGradient id="paint18_radial_101_5103" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(369.317 18.9888) rotate(47.9357) scale(5.69441 2.9849)">
            <stop offset="0.86" stop-color="#6175B9" stop-opacity="0" />
            <stop offset="1" stop-color="#6175B9" />
          </radialGradient>
          <linearGradient id="paint19_linear_101_5103" x1="389.455" y1="1.07527" x2="386.086" y2="4.44482" gradientUnits="userSpaceOnUse">
            <stop stop-color="#CB37FF" />
            <stop offset="1" stop-color="#A611DB" />
          </linearGradient>
          <radialGradient id="paint20_radial_101_5103" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(389.054 2.42449) rotate(135) scale(7.55928 1.81466)">
            <stop offset="0.189" stop-color="#D459FF" />
            <stop offset="1" stop-color="#D459FF" stop-opacity="0" />
          </radialGradient>
          <linearGradient id="paint21_linear_101_5103" x1="386.38" y1="4.66939" x2="386.716" y2="4.31832" gradientUnits="userSpaceOnUse">
            <stop stop-color="#AB1FDC" />
            <stop offset="1" stop-color="#C326EA" stop-opacity="0" />
          </linearGradient>
          <linearGradient id="paint22_linear_101_5103" x1="376.607" y1="14.0815" x2="370.661" y2="20.0268" gradientUnits="userSpaceOnUse">
            <stop stop-color="#5E0D84" />
            <stop offset="1" stop-color="#9315C0" />
          </linearGradient>
          <radialGradient id="paint23_radial_101_5103" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(368.427 16.242) rotate(-20.865) scale(6.8361 1.78963)">
            <stop stop-color="#6A1FC9" />
            <stop offset="1" stop-color="#60149C" stop-opacity="0" />
          </radialGradient>
          <radialGradient id="paint24_radial_101_5103" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(367.659 17.0542) rotate(44.7044) scale(4.22588 1.24829)">
            <stop offset="0.382" stop-color="#7717A4" />
            <stop offset="1" stop-color="#C246E1" stop-opacity="0" />
          </radialGradient>
          <radialGradient id="paint25_radial_101_5103" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(373.325 15.9835) rotate(84.6743) scale(6.78949 7.2352)">
            <stop offset="0.832" stop-color="#8E0FCA" stop-opacity="0" />
            <stop offset="1" stop-color="#850DE4" />
          </radialGradient>
          <linearGradient id="paint26_linear_101_5103" x1="375.53" y1="15.0383" x2="371.749" y2="18.9917" gradientUnits="userSpaceOnUse">
            <stop stop-color="#621089" />
            <stop offset="1" stop-color="#5E119B" />
          </linearGradient>
        </defs>
      </svg>
    </footer>

  </div>

</body>

</html>
"""

@app.route('/get_weather_data', methods=['GET'])
def get_weather_data():
    lat = str(request.args.get('lat'))
    lon = str(request.args.get('lon'))
    print('lat: ' + lat)
    print('long: ' + lon)
    current_time = datetime.now(timezone)
    current_hour = current_time.hour
    url = f'https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={openweathermap_key}'
    openweathermap_response = requests.get(url).json()

    cidade = "N/A"
    temperatura = "N/A"
    umidade = "N/A"
    velocidade_vento = "N/A"
    iuv = ""
    
    
    try:
        
        cidade = openweathermap_response['name']
        temperatura = round(openweathermap_response['main']['temp'] - 273.15)
        umidade = openweathermap_response['main']['humidity']
        velocidade_vento = round(openweathermap_response['wind']['speed'] * 3.6)
        
        openuvapi_key = 'openuv-byhyyvrlmp04mfe-io'
        url_uv = f'https://api.openuv.io/api/v1/uv?lat={lat}&lng={lon}'
        headers = {'x-access-token': openuvapi_key}
        
        response = requests.get(url_uv, headers=headers)
        data = response.json()        
        print(data)
        
        iuv = data['result']['uv']
        print('IUV... ', iuv)
        
        try:
          iuv = round(iuv)
        except:
          print('round... nope!')
          iuv = 0
        print('Aqui5')   
        if iuv == 0:
            str_iuv = 'Baixo'
            fps_recomendation = '-'
            
        elif 0 < iuv < 2.5:
            str_iuv = 'Baixo'
            if current_hour >= 18:
                fps_recomendation = '-'
            else:
                fps_recomendation = "15 FPS"
                
                
        elif 2.5 <= iuv < 5.5:
            str_iuv = 'Moderado'
            if current_hour >= 18:
                fps_recomendation = '-'
            else:
                fps_recomendation = "30 FPS"
                

        elif 5.5 <= iuv < 7.5:
            str_iuv = 'Alto'
            if current_hour >= 18:
                fps_recomendation = '-'
            else:
                fps_recomendation = "60 FPS"
                
        
        elif 7.5 <= iuv < 10.5:
            str_iuv = 'Muito Alto'
            if current_hour >= 18:
                fps_recomendation = '-'
            else:
                fps_recomendation = "90 FPS"
                
        
        elif iuv > 10.5:
            str_iuv = 'Extremo'
            if current_hour >= 18:
                fps_recomendation = '-'
            else:
                fps_recomendation = "120 FPS"
                
        else:
            str_iuv = ''
            fps_recomendation = '-'
        print('STR_IUV = ', str_iuv)
        
    except:
        str_iuv = 'Info indisponível'
        fps_recomendation = 'Info indisponível'
        pass
      
      
    if type(iuv) == int or type(iuv) == float:
      uv_index_toret = f"{iuv} - {str_iuv}"      
    else:
      uv_index_toret = 'Info indisponível'
      
        
    return jsonify({
        'city': str(cidade),
        'temperature': str(temperatura) + ' ºC',
        'humidity': str(umidade) + '%',
        'uv_index': uv_index_toret,
        'wind_speed': str(velocidade_vento) + ' km/h',
        'fps_recommendation': fps_recomendation,
        'cases_2023': '{:,}'.format(int(get_cases_2023())).replace(',', '.'),
        'cases_now': str(int(get_cases_now())) + " novos casos",
        'last_day': f"{cidade} - {current_time.day - 1}/{current_time.month}/{current_time.year}"   
    })

if __name__ == '__main__':
    app.run()