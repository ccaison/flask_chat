# flask_chat
An example implementation of a chat server in flask using flask-socketio. The project is for use with a my child's research expo project.

Server is implemented using [flask-socketio](https://flask-socketio.readthedocs.io/en/latest/).


## Creating the Service
The chat server is run in Gunicorn. To support socket.io use eventlet as the worker class.

```
[Unit]
Description=Gunicorn instance to serve turingbot
After=network.target

[Service]
User=turingbot
Group=www-data
WorkingDirectory=/home/ai_bot
Environment="PATH=/home/ai_bot/env/bin"
ExecStart=/home/ai_bot/env/bin/gunicorn -w 1 -b 127.0.0.1:5000 --worker-class eventlet wsgi:app

[Install]
WantedBy=multi-user.targety

```