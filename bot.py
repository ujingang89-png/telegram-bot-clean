import gspread
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds = ServiceAccountCredentials.from_json_keyfile_name("apt-index-492614-v9-53aa9fdf1795.json", scope)
client = gspread.authorize(creds)

sheet = client.open("섭외관리표").sheet1

def find_people(day, gender, age_min, age_max, target_time):
    data = sheet.get_all_records()
    result = []

    for p in data:
        days = str(p["요일"]).replace(" ", "").split(",")

        if (day in days) and \
           (p["성별"] == gender or gender == "무관") and \
           (age_min <= int(p["나이"]) <= age_max) and \
           (int(p["시작"]) <= target_time <= int(p["끝"])):

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

            days = ["월","화","수","목","금","토","일"]
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

            days = ["월","화","수","목","금","토","일"]
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
                row.append(InlineKeyboardButton(str(i), callback_data=f"start_{i}"))
                if len(row) == 4:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)

            await query.edit_message_text("시작 시간 선택", reply_markup=InlineKeyboardMarkup(keyboard))

        # ✅ 5. 시작시간 → 끝시간 선택
        elif query.data.startswith("start_"):
            start_time = int(query.data.split("_")[1])
            context.user_data["start_time"] = start_time

            keyboard = []
            row = []
            for i in range(start_time, 24):
                row.append(InlineKeyboardButton(str(i), callback_data=f"end_{i}"))
                if len(row) == 4:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)

            await query.edit_message_text("끝 시간 선택", reply_markup=InlineKeyboardMarkup(keyboard))


        # ✅ 6. 끝시간 → 결과
        elif query.data.startswith("end_"):
            end_time = int(query.data.split("_")[1])

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
                       (int(p["시작"]) <= end_time and int(p["끝"]) >= start_time):

                        result.append(p["이름"])

            result = list(set(result))

            # ⭐ 여기 안에 있어야 함
            if not result:
                text = "조건에 맞는 사람이 없습니다."
            else:
                text = "가능한 사람:\n" + "\n".join(result)

            await query.edit_message_text(text)
    except Exception as e:
        print("🔥 에러 발생:", e)
        await update.callback_query.message.reply_text(f"에러: {e}")
app = ApplicationBuilder().token("8703437303:AAEsfMv3-HjuRZfU7VRAxMvlYm-9ML4IOdc").build()

app.add_handler(CommandHandler("search", search))
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))

app.run_polling()