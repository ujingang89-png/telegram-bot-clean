import gspread
import os
import json
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds_json = os.environ.get("GOOGLE_CREDENTIALS")
creds_dict = json.loads(creds_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

sheet = client.open("강철6부 가섭구인BOT").sheet1

def find_people(day, gender, age_min, age_max, target_time):
    data = sheet.get_all_records()
    result = []

    for p in data:
        days = str(p["요일"]).replace(" ", "").split(",")

        if (day in days) and \
           (p["성별"] == gender or gender == "무관") and \
           (age_min <= int(p["나이"]) <= age_max) and \
           (float(p["시작"]) <= target_time <= float(p["끝"])):

            result.append(p["이름"])

    return list(set(result))

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        day = context.args[0]
        gender = context.args[1]
        age_min = int(context.args[2])
        age_max = int(context.args[3])
        time = int(context.args[4])

        result = find_people(day, gender, age_min, age_max, time)

        if not result:
            await update.message.reply_text("조건에 맞는 사람이 없습니다.")
        else:
            text = "\n".join(result)
            await update.message.reply_text(f"가능한 사람:\n{text}")

    except Exception as e:
        await update.message.reply_text(f"오류 발생: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("검색 시작", callback_data="start_search")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("검색을 시작하세요", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()

        print("콜백 데이터:", query.data)

        # ✅ 1. 시작
        if query.data == "start_search":
            context.user_data["days"] = []

            days = ["월","화","수","목","금"]
            keyboard = []

            row = []
            for d in days:
                row.append(InlineKeyboardButton(d, callback_data=f"day_{d}"))
                if len(row) == 4:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)

            keyboard.append([InlineKeyboardButton("다음", callback_data="next_gender")])

            await query.edit_message_text("요일 선택 (복수 선택 가능)", reply_markup=InlineKeyboardMarkup(keyboard))

        # ✅ 2. 요일 선택 (토글)
        elif query.data.startswith("day_"):
            if "days" not in context.user_data:
                context.user_data["days"] = []

            selected_day = query.data.split("_")[1]

            if selected_day in context.user_data["days"]:
                context.user_data["days"].remove(selected_day)
            else:
                context.user_data["days"].append(selected_day)

            selected_days = context.user_data["days"]

            days = ["월","화","수","목","금"]
            keyboard = []

            row = []
            for d in days:
                text = f"✅{d}" if d in selected_days else d
                row.append(InlineKeyboardButton(text, callback_data=f"day_{d}"))
                if len(row) == 4:
                    keyboard.append(row)
                    row = []

            if row:
                keyboard.append(row)

            keyboard.append([InlineKeyboardButton("다음", callback_data="next_gender")])

            await query.edit_message_text("요일 선택 (복수 선택 가능)", reply_markup=InlineKeyboardMarkup(keyboard))

        # ✅ 3. 다음 → 성별
        elif query.data == "next_gender":
            if not context.user_data.get("days"):
                await query.answer("요일 선택하세요!", show_alert=True)
                return

            keyboard = [
                [InlineKeyboardButton("남자", callback_data="gender_남자"),
                 InlineKeyboardButton("여자", callback_data="gender_여자"),
                 InlineKeyboardButton("무관", callback_data="gender_무관")]
            ]

            await query.edit_message_text("성별 선택", reply_markup=InlineKeyboardMarkup(keyboard))

        # ✅ 4. 성별 → 시작시간 선택
        elif query.data.startswith("gender_"):
            selected_gender = query.data.split("_")[1]
            context.user_data["gender"] = selected_gender

            keyboard = []
            row = []
            for i in range(10, 24):
                for m in [0, 30]:
                    label = f"{i}:{str(m).zfill(2)}"
                    value = i + (0.5 if m == 30 else 0)
                    row.append(InlineKeyboardButton(label, callback_data=f"start_{value}"))
                    if len(row) == 4:
                        keyboard.append(row)
                        row = []
            if row:
                keyboard.append(row)

            await query.edit_message_text("시작 시간 선택", reply_markup=InlineKeyboardMarkup(keyboard))

        # ✅ 5. 시작시간 → 끝시간 선택
        elif query.data.startswith("start_"):
            start_time = float(query.data.split("_")[1])
            context.user_data["start_time"] = start_time

            keyboard = []
            row = []
            for i in range(int(start_time), 24):
                for m in [0, 30]:
                    value = i + (0.5 if m == 30 else 0)
                    if value > start_time:
                        label = f"{i}:{str(m).zfill(2)}"
                        row.append(InlineKeyboardButton(label, callback_data=f"end_{value}"))
                        if len(row) == 4:
                            keyboard.append(row)
                            row = []
            if row:
                keyboard.append(row)

            await query.edit_message_text("끝 시간 선택", reply_markup=InlineKeyboardMarkup(keyboard))

        # ✅ 6. 끝시간 → 결과
        elif query.data.startswith("end_"):
            end_time = float(query.data.split("_")[1])

            days = context.user_data.get("days", [])
            gender = context.user_data.get("gender")
            start_time = context.user_data.get("start_time")

            result = []
            data = sheet.get_all_records()

            for p in data:
                days_list = str(p["요일"]).replace(" ", "").split(",")

                for d in days:
                    if (d in days_list) and \
                       (p["성별"] == gender or gender == "무관") and \
                       (20 <= int(p["나이"]) <= 40) and \
                       (float(p["시작"]) <= end_time and float(p["끝"]) >= start_time):

                        result.append(p["이름"])

            result = list(set(result))

            if not result:
                text = "조건에 맞는 사람이 없습니다."
            else:
                text = "가능한 사람:\n" + "\n".join(result)

            await query.edit_message_text(text)
    except Exception as e:
        print("🔥 에러 발생:", e)
        await update.callback_query.message.reply_text(f"에러: {e}")

async def post_init(application):
    await application.bot.delete_webhook(drop_pending_updates=True)

app = ApplicationBuilder().token(os.environ.get("BOT_TOKEN")).post_init(post_init).build()

app.add_handler(CommandHandler("search", search))
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))

import requests
import schedule
import time
from datetime import datetime
import pytz
from flask import Flask
import threading

flask_app = Flask(__name__)

# ===== 자동 알림 설정 =====
CHAT_ID_1 = "-1003539680106"
MESSAGE_1 = """일보 부탁드립니다~\n1 2 3 4 5 6 7 8"""
CHAT_ID_2 = "-1002467111151"
MESSAGE_2 = "1 2 3 4 5 6 7 8"
THREAD_ID_2 = 30
CHAT_ID_3 = "-1002467111151"
THREAD_ID_3 = 6
MESSAGE_3 = """주일 19시 전팀모임양식\n올려주시면 감사하겠습니다!"""
CHAT_ID_4 = "-1002244734007"
MESSAGE_4 = "파트별 금주 논의사항 양식 올려주세요~!"
CHAT_ID_5 = "-1002244734007"
MESSAGE_5 = "주간회의 PPT 마무리해주세요~!"
CHAT_ID_JS = "-1003851451653"
MSG_MON_10 = "부장님 이번주 진성신 범위는 어디일까요?"
MSG_TUE = "진성신은 목요일 주간회의 전까지입니다."
MSG_WED = "진성신은 목요일까지입니다, 주간회의 전까지 입니다."
MSG_THU = "당일에 주시는 사유보고는 받지 않겠습니다. 주간회의 전까지 모두 마무리 부탁드립니다."
CHAT_ID_FEEL = "-1002697448961"
MSG_MON_FEEL = "교육 들으신 분들은 느낀점 마무리 해주시고 수정해주세요"
MSG_TUE_FEEL = "교육 들으신 분들은 느낀점 마무리 해주시고 수정해주세요"
MSG_WED_FEEL = "청취 요일 수정과 느낀점 마무리 해주세요. 토요일까지입니다!"
MSG_THU_FEEL = "토요일까지입니다. 모두 시간 맞춰 청취 부탁드립니다. 요일 수정해주세요"
MSG_FRI_FEEL = "교육과 주간회의는 모두 토요일까지입니다. 모두 시간 맞춰 청취 부탁드립니다. 요일 수정해주세요"
MSG_SAT_FEEL = """토요일까지 모두 완료해주세요!\n오늘까지 마무리 부탁드립니다.\n일요일까지도 이름 남아있는 사명자는 사유 물어보겠습니다.\n사유보고는 당일이 아닌, 미리 하는것이 사유보고입니다.\n당일에 사유보고 하신분들은 사유보고로 받지 않겠습니다."""
CHAT_ID_WORSHIP = "-1002058115709"
MSG_MON_WORSHIP = "구역예배 시간 올려주세요"
MSG_TUE_WORSHIP = "구역예배 시간 올려주세요! 구역예배 교안은 금요일 오전 8시까지입니다. 8:01분이 될시에도 벌금입니다!"
MSG_WED_WORSHIP = "구역예배 교안은 금요일 오전 8시까지입니다. 8:01분이 될시에도 벌금입니다!"
MSG_THU_WORSHIP = "구역예배 교안은 금요일 오전 8시까지입니다. 8:01분이 될시에도 벌금입니다!"
MSG_FRI_WORSHIP = "구역예배 교안 시간이 얼마 남지 않았습니다. 8:01분 되면 벌금입니다!"

def send_auto_message(chat_id, text, thread_id=None):
    token = os.environ.get("BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    if thread_id is not None:
        data["message_thread_id"] = thread_id
    requests.post(url, data=data)

last_sent_date = None
def job_if_kst():
    global last_sent_date
    kst = datetime.now(pytz.timezone("Asia/Seoul"))
    now_date = kst.strftime("%Y-%m-%d")
    if kst.strftime("%H:%M") in ["20:30", "20:31", "20:32"] and last_sent_date != now_date:
        last_sent_date = now_date
        send_auto_message(CHAT_ID_1, MESSAGE_1)
        send_auto_message(CHAT_ID_2, MESSAGE_2, THREAD_ID_2)

last_sent_date_sat = None
def job_saturday_2130():
    global last_sent_date_sat
    kst = datetime.now(pytz.timezone("Asia/Seoul"))
    now_date = kst.strftime("%Y-%m-%d")
    if kst.weekday() == 5 and kst.strftime("%H:%M") in ["21:30", "21:31", "21:32"] and last_sent_date_sat != now_date:
        last_sent_date_sat = now_date
        send_auto_message(CHAT_ID_3, MESSAGE_3, THREAD_ID_3)

last_sent_date_thu = None
def job_thursday_2300():
    global last_sent_date_thu
    kst = datetime.now(pytz.timezone("Asia/Seoul"))
    now_date = kst.strftime("%Y-%m-%d")
    if kst.weekday() == 3 and kst.strftime("%H:%M") in ["23:00", "23:01", "23:02"] and last_sent_date_thu != now_date:
        last_sent_date_thu = now_date
        send_auto_message(CHAT_ID_4, MESSAGE_4)

last_sent_date_wed = None
def job_wednesday_2300():
    global last_sent_date_wed
    kst = datetime.now(pytz.timezone("Asia/Seoul"))
    now_date = kst.strftime("%Y-%m-%d")
    if kst.weekday() == 2 and kst.strftime("%H:%M") in ["23:00", "23:01", "23:02"] and last_sent_date_wed != now_date:
        last_sent_date_wed = now_date
        send_auto_message(CHAT_ID_5, MESSAGE_5)

last_sent_mon = None
def job_monday_10():
    global last_sent_mon
    kst = datetime.now(pytz.timezone("Asia/Seoul"))
    now_date = kst.strftime("%Y-%m-%d")
    if kst.weekday() == 0 and kst.strftime("%H:%M") == "10:00" and last_sent_mon != now_date:
        last_sent_mon = now_date
        send_auto_message(CHAT_ID_JS, MSG_MON_10)

last_sent_tue = None
def job_tuesday():
    global last_sent_tue
    kst = datetime.now(pytz.timezone("Asia/Seoul"))
    now_date = kst.strftime("%Y-%m-%d")
    if kst.weekday() == 1 and kst.strftime("%H:%M") in ["10:00", "20:00"] and last_sent_tue != now_date:
        last_sent_tue = now_date
        send_auto_message(CHAT_ID_JS, MSG_TUE)

last_sent_wed = None
def job_wednesday():
    global last_sent_wed
    kst = datetime.now(pytz.timezone("Asia/Seoul"))
    now_date = kst.strftime("%Y-%m-%d")
    if kst.weekday() == 2 and kst.strftime("%H:%M") in ["10:00", "20:00"] and last_sent_wed != now_date:
        last_sent_wed = now_date
        send_auto_message(CHAT_ID_JS, MSG_WED)

last_sent_thu = None
def job_thursday():
    global last_sent_thu
    kst = datetime.now(pytz.timezone("Asia/Seoul"))
    now_date = kst.strftime("%Y-%m-%d")
    if kst.weekday() == 3 and kst.strftime("%H:%M") in ["10:00", "15:00", "21:00"] and last_sent_thu != now_date:
        last_sent_thu = now_date
        send_auto_message(CHAT_ID_JS, MSG_THU)

last_sent_feel_mon = None
def job_feel_monday():
    global last_sent_feel_mon
    kst = datetime.now(pytz.timezone("Asia/Seoul"))
    now_date = kst.strftime("%Y-%m-%d")
    if kst.weekday() == 0 and kst.strftime("%H:%M") == "21:00" and last_sent_feel_mon != now_date:
        last_sent_feel_mon = now_date
        send_auto_message(CHAT_ID_FEEL, MSG_MON_FEEL)

last_sent_feel_tue = None
def job_feel_tuesday():
    global last_sent_feel_tue
    kst = datetime.now(pytz.timezone("Asia/Seoul"))
    now_date = kst.strftime("%Y-%m-%d")
    if kst.weekday() == 1 and kst.strftime("%H:%M") in ["10:00", "18:00"] and last_sent_feel_tue != now_date:
        last_sent_feel_tue = now_date
        send_auto_message(CHAT_ID_FEEL, MSG_TUE_FEEL)

last_sent_feel_wed = None
def job_feel_wednesday():
    global last_sent_feel_wed
    kst = datetime.now(pytz.timezone("Asia/Seoul"))
    now_date = kst.strftime("%Y-%m-%d")
    if kst.weekday() == 2 and kst.strftime("%H:%M") in ["10:00", "18:00"] and last_sent_feel_wed != now_date:
        last_sent_feel_wed = now_date
        send_auto_message(CHAT_ID_FEEL, MSG_WED_FEEL)

last_sent_feel_thu = None
def job_feel_thursday():
    global last_sent_feel_thu
    kst = datetime.now(pytz.timezone("Asia/Seoul"))
    now_date = kst.strftime("%Y-%m-%d")
    if kst.weekday() == 3 and kst.strftime("%H:%M") in ["10:00", "18:00"] and last_sent_feel_thu != now_date:
        last_sent_feel_thu = now_date
        send_auto_message(CHAT_ID_FEEL, MSG_THU_FEEL)

last_sent_feel_fri = None
def job_feel_friday():
    global last_sent_feel_fri
    kst = datetime.now(pytz.timezone("Asia/Seoul"))
    now_date = kst.strftime("%Y-%m-%d")
    if kst.weekday() == 4 and kst.strftime("%H:%M") in ["10:00", "18:00"] and last_sent_feel_fri != now_date:
        last_sent_feel_fri = now_date
        send_auto_message(CHAT_ID_FEEL, MSG_FRI_FEEL)

last_sent_feel_sat = None
def job_feel_saturday():
    global last_sent_feel_sat
    kst = datetime.now(pytz.timezone("Asia/Seoul"))
    now_date = kst.strftime("%Y-%m-%d")
    if kst.weekday() == 5 and kst.strftime("%H:%M") in ["10:00", "15:00", "19:00", "21:00", "23:00"] and last_sent_feel_sat != now_date:
        last_sent_feel_sat = now_date
        send_auto_message(CHAT_ID_FEEL, MSG_SAT_FEEL)

last_sent_worship_mon = None
def job_worship_monday():
    global last_sent_worship_mon
    kst = datetime.now(pytz.timezone("Asia/Seoul"))
    now_date = kst.strftime("%Y-%m-%d")
    if kst.weekday() == 0 and kst.strftime("%H:%M") in ["10:00", "20:00"] and last_sent_worship_mon != now_date:
        last_sent_worship_mon = now_date
        send_auto_message(CHAT_ID_WORSHIP, MSG_MON_WORSHIP)

last_sent_worship_tue = None
def job_worship_tuesday():
    global last_sent_worship_tue
    kst = datetime.now(pytz.timezone("Asia/Seoul"))
    now_date = kst.strftime("%Y-%m-%d")
    if kst.weekday() == 1 and kst.strftime("%H:%M") in ["11:00", "20:00"] and last_sent_worship_tue != now_date:
        last_sent_worship_tue = now_date
        send_auto_message(CHAT_ID_WORSHIP, MSG_TUE_WORSHIP)

last_sent_worship_wed = None
def job_worship_wednesday():
    global last_sent_worship_wed
    kst = datetime.now(pytz.timezone("Asia/Seoul"))
    now_date = kst.strftime("%Y-%m-%d")
    if kst.weekday() == 2 and kst.strftime("%H:%M") in ["10:00", "18:00"] and last_sent_worship_wed != now_date:
        last_sent_worship_wed = now_date
        send_auto_message(CHAT_ID_WORSHIP, MSG_WED_WORSHIP)

last_sent_worship_thu = None
def job_worship_thursday():
    global last_sent_worship_thu
    kst = datetime.now(pytz.timezone("Asia/Seoul"))
    now_date = kst.strftime("%Y-%m-%d")
    if kst.weekday() == 3 and kst.strftime("%H:%M") in ["10:00", "20:00", "23:00", "23:58"] and last_sent_worship_thu != now_date:
        last_sent_worship_thu = now_date
        send_auto_message(CHAT_ID_WORSHIP, MSG_THU_WORSHIP)

last_sent_worship_fri = None
def job_worship_friday():
    global last_sent_worship_fri
    kst = datetime.now(pytz.timezone("Asia/Seoul"))
    now_date = kst.strftime("%Y-%m-%d")
    if kst.weekday() == 4 and kst.strftime("%H:%M") in ["05:00", "06:00", "07:00"] and last_sent_worship_fri != now_date:
        last_sent_worship_fri = now_date
        send_auto_message(CHAT_ID_WORSHIP, MSG_FRI_WORSHIP)

schedule.every().minute.do(job_if_kst)
schedule.every().minute.do(job_saturday_2130)
schedule.every().minute.do(job_thursday_2300)
schedule.every().minute.do(job_wednesday_2300)
schedule.every().minute.do(job_monday_10)
schedule.every().minute.do(job_tuesday)
schedule.every().minute.do(job_wednesday)
schedule.every().minute.do(job_thursday)
schedule.every().minute.do(job_feel_monday)
schedule.every().minute.do(job_feel_tuesday)
schedule.every().minute.do(job_feel_wednesday)
schedule.every().minute.do(job_feel_thursday)
schedule.every().minute.do(job_feel_friday)
schedule.every().minute.do(job_feel_saturday)
schedule.every().minute.do(job_worship_monday)
schedule.every().minute.do(job_worship_tuesday)
schedule.every().minute.do(job_worship_wednesday)
schedule.every().minute.do(job_worship_thursday)
schedule.every().minute.do(job_worship_friday)

@flask_app.route('/')
def home():
    return "Bot is running!"

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

def run_web():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_scheduler, daemon=True).start()
threading.Thread(target=run_web, daemon=True).start()
import signal

async def main():
    while True:
        try:
            await app.initialize()
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True)
            await app.updater.idle()
        except Exception as e:
            print(f"오류 발생, 5초 후 재시작: {e}")
            try:
                await app.updater.stop()
                await app.stop()
                await app.shutdown()
            except:
                pass
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
