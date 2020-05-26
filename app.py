# flask imports
from flask import Flask, render_template, escape
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import exists
from flask_security import (
    Security,
    SQLAlchemyUserDatastore,
    UserMixin,
    RoleMixin,
    login_required,
    current_user,
)
from flask_security import utils as fs_utils
from flask_socketio import SocketIO
from flask_login import LoginManager
import json, time

from flask_httpauth import HTTPBasicAuth

from temp_users import temp_users


# setup flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = "trevorisawesome"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
app.config["SECURITY_PASSWORD_SALT"] = "adfsadsf"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["DEBUG"] = True

db = SQLAlchemy(app)

bad_words = []
f = open("bad_words.txt", "r")
for word in f:
    bad_words.append(word.rstrip("\n"))

print("[-] Loaded {0} words from bad words list".format(len(bad_words)))

auth = HTTPBasicAuth()


# Define models
roles_users = db.Table(
    "roles_users",
    db.Column("user_id", db.Integer(), db.ForeignKey("user.id")),
    db.Column("role_id", db.Integer(), db.ForeignKey("role.id")),
)


class Role(db.Model, RoleMixin):
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True)
    password = db.Column(db.String(255))
    active = db.Column(db.Boolean())
    display_name = db.Column(db.String(50))
    confirmed_at = db.Column(db.DateTime())
    roles = db.relationship(
        "Role", secondary=roles_users, backref=db.backref("users", lazy="dynamic")
    )


# Setup Flask-Security
user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore)

login_manager = LoginManager()


# Create a user to test with
@app.before_first_request
def create_user():
    db.create_all()
    print("[-] Creating temp users")
    try:
        for user in temp_users:
            user_datastore.create_user(
                display_name=user["display_name"],
                email=user["email"],
                password=user["password"],
            )
        db.session.commit()
    except Exception as e:
        print("[!] Exception: {0}".format(e))


# start socketio
socketio = SocketIO(app)


@app.route("/")
def sessions():
    return render_template("session.html")


# Auth
@auth.verify_password
def verify_password(username, password):
    """
    Callback method for HTTPBasicAuth. Protects API, 
    only bot is allowed to connect. Bot must have appropriate creds.
    """
    if db.session.query(exists().where(User.email == username)).scalar():
        user = User.query.filter(User.email == username).first()
        if user.email == "bot@turingbot.io":
            if fs_utils.verify_password(password, user.password):
                return True
            else:
                return False
        else:
            return False
    else:
        return False


@auth.error_handler
def unauthorized():
    """
    Returns error for login failure against API.
    """
    return make_response(jsonify({"error": "Unauthorized access"}), 401)


@login_manager.user_loader
def load_user(user_id):
    return User.query.filter(User.id == user_id)


## SocketIO Logic


def message_received(user_name, msg, methods=["GET", "POST"]):
    print("[-] Adding '{0}' to input_q".format(msg))
    input_q.put(msg)
    while output_q.empty():
        pass
    reply = output_q.get()
    socketio.emit(
        "response_msg",
        {
            "user_name": "server",
            "message": '<span class="badge badge-secondary">@{0}</span> {1}'.format(
                user_name, reply
            ),
        },
    )


def connection_event(json_msg):
    if current_user.is_authenticated:
        name = current_user.display_name
    elif "auth" in json_msg.keys():
        username = json_msg["auth"]["username"]
        password = json_msg["auth"]["password"]
        user = User.query.filter(User.email == username).first()
        name = user.display_name
    else:
        return
    socketio.emit(
        "response_msg",
        {
            "user_name": "server",
            "message": 'Welcome <b><i>{0}</i></b> to the AI Chat Example. Use <span class="badge badge-light">@bot</span> to chat with the bot.'.format(
                name
            ),
        },
    )


@socketio.on("disconnect")
def handle_disconnect():
    if current_user.is_authenticated:
        name = current_user.display_name
    else:
        return
    socketio.emit(
        "response_msg",
        {"user_name": "localbot", "message": "{0} has disconnected.".format(name)},
    )


@socketio.on("connect")
def handle_connect():
    if current_user.is_authenticated:
        name = current_user.display_name
    else:
        return
    socketio.emit(
        "response_msg",
        {"user_name": "server", "message": "{0} has connected.".format(name)},
    )


@socketio.on("response_msg")
# @login_required
@auth.verify_password
def handle_my_custom_event(json_msg, methods=["GET", "POST"]):
    print("[-] Received message: ", json_msg)
    if json_msg["type"] == "connect":
        connection_event(json_msg)
    if json_msg["type"] == "msg":
        cleaned_msg = " ".join(
            "[censored]" if i in bad_words else i for i in json_msg["message"].split()
        )
        if current_user.is_authenticated:
            cleaned_msg = escape(cleaned_msg)
            socketio.emit(
                "response_msg",
                {"user_name": current_user.display_name, "message": cleaned_msg},
            )
        elif verify_password(
            json_msg["auth"]["username"], json_msg["auth"]["password"]
        ):
            socketio.emit(
                "response_msg",
                {"user_name": json_msg["user_name"], "message": cleaned_msg},
            )


if __name__ == "__main__":
    socketio.run(app, debug=True, host="127.0.0.1", port=5000)
