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
    # 1. Добавляем параметр fields, чтобы запросить данные о рекламе
    graph_url = f"https://graph.facebook.com/v19.0/{leadgen_id}"
    params = {
        'access_token': PAGE_ACCESS_TOKEN,
        'fields': 'field_data,created_time,campaign_name,ad_name,platform'
    }
    
    response = requests.get(graph_url, params=params).json()
    
    # Полезно для дебага: в логах Render вы увидите весь ответ Meta
    print("META API RESPONSE:", response)
    
    if 'field_data' not in response:
        return

    # Базовые поля
    full_name = 'Не вказано'
    phone = 'Не вказано'
    
    # Список для сбора всех кастомных вопросов из формы
    custom_answers = []

    # 2. Динамический парсинг полей
    for field in response['field_data']:
        name = field['name']
        val = field['values'][0] if field['values'] else 'Не вказано'
        
        if name == 'full_name':
            full_name = val
        elif name == 'phone_number':
            phone = val
        else:
            # Все остальные вопросы формы (классы, предметы) попадут сюда автоматически
            # Meta пришлет свой короткий ключ, но мы выведем его вместе с ответом
            custom_answers.append(f"▫️ <b>{name}:</b> {val}")

    # Склеиваем кастомные вопросы в один текст
    custom_text = "\n".join(custom_answers) if custom_answers else "▫️ Немає додаткових відповідей"

    # 3. Достаем аналитику (если лид органический, этих полей может не быть)
    campaign = response.get('campaign_name', 'Органіка / Невідомо')
    ad_name = response.get('ad_name', 'Невідомо')
    platform = response.get('platform', 'fb').upper()
    created_time = response.get('created_time', 'Невідомо')

    # 4. Формируем красивое сообщение
    msg = (
        "🔥 <b>Новий лід!</b>\n\n"
        f"👤 <b>Ім'я:</b> {full_name}\n"
        f"📞 <b>Телефон:</b> {phone}\n\n"
        f"📋 <b>Відповіді з форми:</b>\n{custom_text}\n\n"
        f"📊 <b>Аналітика:</b>\n"
        f"📢 <b>Кампанія:</b> {campaign}\n"
        f"🎯 <b>Оголошення:</b> {ad_name}\n"
        f"📱 <b>Платформа:</b> {platform}\n\n"
        f"🕒 <i>Час заявки: {created_time}</i>"
    )
        
    tg_url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    
    requests.post(tg_url, json={
        'chat_id': TG_CHAT_ID, 
        'text': msg,
        'parse_mode': 'HTML'
    })

if __name__ == '__main__':
    app.run(port=5000)
