from flask import Flask
from threading import Thread

app = Flask('')


@app.route('/')
def home():
  return "le bot est en ligne jeux de mastermind !"


def run():
  app.run(host='0.0.0.0', port=8091)


def keep_alive():
  t = Thread(target=run)
  t.start()
