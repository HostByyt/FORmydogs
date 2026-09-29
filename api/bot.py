from flask import Flask, request
from telegram import Bot

app = Flask(__name__)
bot = Bot(token="8692694648:AAHJ7iAdBJwSmQCKBjhzZXboM1jw90PFaXg")

@app.route('/api/bot', methods=['POST'])
def webhook():
    update = request.get_json()
    # هنا معالجة التحديث
    return '', 200
