
FROM python:3.11.3-bullseye
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN export FLASK_APP='back.py'
RUN flask run
COPY . .
EXPOSE 8000
CMD ["flask", "run", "--host", "0.0.0.0", "--port", "8000"]