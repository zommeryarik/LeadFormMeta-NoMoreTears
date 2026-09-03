import os
import requests
from flask import Flask, request

app = Flask(__name__)

# Берем настройки из переменных окружения (безопасный метод)
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', 'secret_word_123') # Слово для привязки Meta
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
TG_BOT_TOKEN = os.environ.get('TG_BOT_TOKEN')
TG_CHAT_ID = os.environ.get('TG_CHAT_ID')

# 1. Эндпоинт для подтверждения вебхука от Meta (GET-запрос)
@app.route('/webhook', methods=['GET'])
def verify_webhook():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    if mode and token:
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            return challenge, 200
        else:
            return 'Forbidden', 403
    return 'OK', 200

# 2. Эндпоинт для приема самих лидов (POST-запрос)
@app.route('/webhook', methods=['POST'])
def handle_webhook():
    data = request.json
    
    # Meta требует быстрого ответа 200 OK
    if data.get('object') == 'page':
        for entry in data.get('entry', []):
            for change in entry.get('changes', []):
                if change.get('field') == 'leadgen':
                    leadgen_id = change['value']['leadgen_id']
                    # Отправляем лид на обработку
                    process_lead(leadgen_id)
                    
    return 'EVENT_RECEIVED', 200

def process_lead(leadgen_id):
    # Запрашиваем данные лида у Facebook Graph API
    graph_url = f"https://graph.facebook.com/v19.0/{leadgen_id}"
    params = {'access_token': PAGE_ACCESS_TOKEN}
    
    response = requests.get(graph_url, params=params).json()
    
    if 'field_data' not in response:
        return

    # Создаем словарь для удобного поиска полей
    lead_data = {}
    for field in response['field_data']:
        name = field['name']
        val = field['values'][0] if field['values'] else 'Не вказано'
        lead_data[name] = val

    # Достаем базовые поля (в Meta API они называются full_name и phone_number)
    full_name = lead_data.get('full_name', 'Не вказано')
    phone = lead_data.get('phone_number', 'Не вказано')
    
    # Достаем кастомные вопросы (берем точные названия из вашей формы)
    grade = lead_data.get('Оберіть у якому класі навчається дитина', 'Не вказано')
    subject = lead_data.get('Оберіть предмет', 'Не вказано')
    
    # Берем время создания лида и форматируем его
    created_time = response.get('created_time', 'Невідомо')

    # Формируем красивое сообщение для Telegram с эмодзи и HTML-разметкой
    msg = (
        "🔥 <b>Новий лід!</b>\n\n"
        f"👤 <b>Ім'я:</b> {full_name}\n"
        f"📞 <b>Телефон:</b> {phone}\n\n"
        f"🎓 <b>Клас:</b> {grade}\n"
        f"📚 <b>Предмет:</b> {subject}\n\n"
        f"🕒 <i>Час заявки: {created_time}</i>"
    )
        
    # Отправляем в Telegram
    tg_url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    
    # Добавляем parse_mode='HTML', чтобы бот понимал теги <b> и <i>
    requests.post(tg_url, json={
        'chat_id': TG_CHAT_ID, 
        'text': msg,
        'parse_mode': 'HTML'
    })

if __name__ == '__main__':
    app.run(port=5000)