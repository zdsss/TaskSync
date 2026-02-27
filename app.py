import logging
import os

from flask import Flask

from stores import task_store as ts, knowledge_store as ks
from blueprints import tasks, knowledge, graph, skills, calendar

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

ts.init_db()
ks.init_db()

app.register_blueprint(tasks.bp)
app.register_blueprint(knowledge.bp)
app.register_blueprint(graph.bp)
app.register_blueprint(skills.bp)
app.register_blueprint(calendar.bp)

# Suppress werkzeug request body logging
logging.getLogger("werkzeug").setLevel(logging.ERROR)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
