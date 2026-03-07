from flask import Flask, render_template, request, redirect, session, send_from_directory
from flask_socketio import SocketIO, emit
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "secret123"

socketio = SocketIO(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

online_users = set()


def db():
    return sqlite3.connect("chat.db")


def init_db():

    conn = db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS messages(
        id INTEGER PRIMARY KEY,
        sender TEXT,
        receiver TEXT,
        message TEXT,
        status TEXT
    )
    """)

    conn.commit()
    conn.close()


init_db()


@app.route("/", methods=["GET","POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = db()
        c = conn.cursor()

        c.execute("SELECT * FROM users WHERE username=?", (username,))
        user = c.fetchone()

        if not user:
            c.execute(
                "INSERT INTO users(username,password) VALUES(?,?)",
                (username,password)
            )
            conn.commit()

        session["user"] = username

        return redirect("/search")

    return render_template("login.html")


@app.route("/search", methods=["GET","POST"])
def search():

    if request.method == "POST":

        return redirect("/chat/" + request.form["username"])

    return render_template("search.html")


@app.route("/chat/<user>")
def chat(user):

    me = session["user"]

    conn = db()
    c = conn.cursor()

    c.execute("""
    SELECT sender,message FROM messages
    WHERE (sender=? AND receiver=?)
    OR (sender=? AND receiver=?)
    """,(me,user,user,me))

    msgs = c.fetchall()

    return render_template("chat.html", msgs=msgs, user=user, me=me)


@app.route("/upload", methods=["POST"])
def upload():

    file = request.files["file"]

    path = os.path.join(UPLOAD_FOLDER, file.filename)

    file.save(path)

    return {"name": file.filename}


@app.route("/uploads/<name>")
def file(name):

    return send_from_directory(UPLOAD_FOLDER, name)


@socketio.on("send")
def send_msg(data):

    sender = data["sender"]
    receiver = data["receiver"]
    msg = data["msg"]
    mid = data["id"]

    conn = db()
    c = conn.cursor()

    c.execute(
        "INSERT INTO messages(sender,receiver,message,status) VALUES(?,?,?,?)",
        (sender,receiver,msg,"sent")
    )

    conn.commit()

    emit("receive", data, broadcast=True)

    emit("delivered", mid, broadcast=True)


@socketio.on("read")
def read_msg(data):

    emit("read", data["id"], broadcast=True)


@socketio.on("typing")
def typing(data):

    emit("typing", data, broadcast=True)


@socketio.on("online")
def online(user):

    online_users.add(user)

    emit("status", list(online_users), broadcast=True)


@socketio.on("disconnect")
def offline():

    pass


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)