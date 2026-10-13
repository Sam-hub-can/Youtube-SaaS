from flask import Flask, redirect, url_for, session, render_template, jsonify
from announcer import active_notice
from auth import init_oauth, oauth
from db import init_db, get_pending, approve

app = Flask(__name__)
app.secret_key = "secret"

app.config.from_object("config.Config")

init_oauth(app)
init_db()


# ---------------- MAINTENANCE NOTICE ----------------
@app.context_processor
def inject_notice():
    return {"notice": active_notice()}


@app.route("/announcement")
def announcement():
    return jsonify(message=active_notice())


# ---------------- LOGIN ----------------
@app.route("/login")
def login():
    redirect_uri = url_for("auth", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@app.route("/auth")
def auth():
    token = oauth.google.authorize_access_token()
    session["user"] = token
    return redirect("/dashboard")


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    user = session.get("user")

    if not user:
        return redirect("/login")

    rows = get_pending(user["id"])

    return render_template("dashboard.html", rows=rows)


@app.route("/approve/<id>")
def approve_route(id):
    approve(id)
    return redirect("/dashboard")


if __name__ == "__main__":
    app.run(debug=True)
