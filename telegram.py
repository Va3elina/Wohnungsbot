# -*- coding: utf-8 -*-
import sqlite3
import json
import logging
import os
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    KeyboardButton, ReplyKeyboardMarkup, WebAppInfo,
    LabeledPrice, PreCheckoutQuery
)
from aiogram.filters.command import CommandObject
from aiogram.fsm.storage.memory import MemoryStorage
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# === Load environment ===
load_dotenv()

TOKEN = os.getenv("TELEGRAM_USERBOT_TOKEN", "CHANGE_ME")
BOT_USERNAME = os.getenv("BOT_USERNAME", "WohnungsBot")
HELP_USERNAME = os.getenv("HELP_USERNAME", "@WohnungsBotInfo")

WEBAPP_URLS = {
    "en": "https://va3elina.github.io/WebApp/filtersEN.html",
    "de": "https://va3elina.github.io/WebApp/filtersDE.html",
    "ru": "https://va3elina.github.io/WebApp/filtersRU.html",
    "ar": "https://va3elina.github.io/WebApp/filtersAR.html",
    "tr": "https://va3elina.github.io/WebApp/filtersTU.html"
}

PRODUCT_SLUG = "pro_month"
BOT_USERNAME = "AutoWohnBot"
HELP_USERNAME = "@WohnungsBotInfo"

# === Logging ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Bot Initialization ===
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# === Translations ===
SUPPORTED_LANGUAGES = ["en", "de", "ru", "ar", "tr"]
DEFAULT_LANGUAGE = "en"
translations = {
    "en": {
        "start": "Welcome to Wohnungsbot Bot!",
        "trial": "Free trial activated until",
        "menu": ["🔎 Start Search", "⛔ Stop Search", "🏠 Set Filters", "💳 Subscribe", "ℹ️ My Subscription",
                 "👥 Invite Friends", "🆘 Help"],
        "back_to_menu": "🔙 Back to Menu",
        "change_language": "🌐 Change Language",
        "help_button": "🆘 Help",
        "help_text": "For any questions, please contact {help_username}",
        "welcome_message": "👋 *Welcome to FlatFinder Bot!*\n\n"
"📢 You've received a *7-day free trial* - active until *{date}* ({days} days)\n\n"
"🏠 FlatFinder helps you be the first to see new rental listings in Germany.\n"
"🔔 We instantly notify you about listings that match your filters.\n\n"
"📍 Set your city, price, size and other preferences.\n"
"📬 All listings will be sent directly here in Telegram.",
        "subscription": {
            "active": "📅 Your subscription is active until: *{date}* ({days} days)",
            "expired": "❌ Your subscription *has expired*. You can renew it via 💳 *Subscribe*",
            "none": "❌ You don't have an active subscription.\n\n💡 When you first start, you get a *free 7-day trial period*.",
            "activated": "✅ Subscription activated until *{date}*! Thank you!",
            "will_expire_in_days": "⚠️ Your subscription will expire in {days} days.",
            "will_expire_tomorrow": "⚠️ Your subscription will expire *tomorrow*.",
            "expired_notice": "❌ Your subscription *has expired*. Please renew via 💳 *Subscribe*.",
        },
        "webapp_error": "Please set filters first through 🏠 Set Filters.",
        "invoice": {
            "title": "Subscription",
            "description": "You will get access to automatic listing updates for 30 days"
        },
        "filters": {
            "open": "📋 Click the button below to set your filters:",
            "saved": "✅ *Filter saved!*\n💰 Price: {min_price}€ – {max_price}€\n📏 Size: {min_size}m² – {max_size}m²\n🏷️ Swap apartments: {tauschwohnung}\n📄 WBS required: {wbs}\n🌐 Websites: {websites}\n\n🔎 *Search is ON!* You will receive new listings as they appear.",
            "not_set": "not set",
            "yes": "Yes",
            "no": "No"
        },
        "search": {
            "started": "🔎 Search started. You will receive new listings.",
            "stopped": "⛔ Search stopped. You will no longer receive listings."
        },
        "open_webapp": "🏠 Open Filter Settings",
        "data_error": "Please check your numbers.",
        "invite_friends_text": "👥 Invite a friend and get 14 days free subscription!",
        "referral": {
            "success": "🎉 You got *+{days} days* subscription for inviting *{new_user}*!",
            "new_user_notification": "👋 You joined via referral link! Your free trial has been activated.",
            "self_invite": "❌ You can't invite yourself!",
            "already_invited": "⚠️ You've already invited this user"
        }
    },
    "de": {
        "start": "Willkommen beim Wohnungsbot Bot!",
        "trial": "Kostenlose Testphase aktiviert bis",
        "menu": ["🔎 Suche starten", "⛔ Suche stoppen", "🏠 Filter setzen", "💳 Abonnieren", "ℹ️ Mein Abo",
                 "👥 Freunde einladen", "🆘 Hilfe"],
        "back_to_menu": "🔙 Zurück zum Menü",
        "change_language": "🌐 Sprache ändern",
        "help_button": "🆘 Hilfe",
        "help_text": "Bei Fragen wenden Sie sich bitte an {help_username}",
        "welcome_message": "👋 *Willkommen beim FlatFinder Bot!*\n\n"
"📢 Sie haben eine *7-tägige kostenlose Testphase* – aktiv bis *{date}* ({days} Tage)\n\n"
"🏠 FlatFinder hilft Ihnen, als Erster neue Wohnungsanzeigen in Deutschland zu sehen.\n"
"🔔 Wir benachrichtigen Sie sofort über passende Angebote nach Ihren Filtern.\n\n"
"📍 Geben Sie Stadt, Preis, Größe und weitere Kriterien an.\n"
"📬 Alle Angebote werden direkt hier in Telegram gesendet.",
        "subscription": {
            "active": "📅 Ihr Abonnement ist aktiv bis: *{date}* ({days} Tage)",
            "expired": "❌ Ihr Abonnement *ist abgelaufen*. Sie können es über 💳 *Abonnieren* erneuern",
            "none": "❌ Sie haben kein aktives Abonnement.\n\n💡 Bei der ersten Nutzung erhalten Sie eine *kostenlose 7-tägige Testphase*.",
            "activated": "✅ Abonnement aktiviert bis *{date}*! Vielen Dank!",
            "will_expire_in_days": "⚠️ Ihr Abonnement läuft in {days} Tagen ab.",
            "will_expire_tomorrow": "⚠️ Ihr Abonnement läuft *morgen* ab.",
            "expired_notice": "❌ Ihr Abonnement *ist abgelaufen*. Bitte erneuern Sie es über 💳 *Abonnieren*.",
        },
        "webapp_error": "Bitte setzen Sie zuerst die Filter über 🏠 Filter setzen.",
        "invoice": {
            "title": "Abonnement",
            "description": "Sie erhalten 30 Tage lang Zugang zu automatischen Wohnungsangeboten"
        },
        "filters": {
            "open": "📋 Klicken Sie auf die Schaltfläche unten, um Ihre Filter einzustellen:",
            "saved": "✅ *Filter gespeichert!*\n💰 Preis: {min_price}€ – {max_price}€\n📏 Größe: {min_size}m² – {max_size}m²\n🏷️ Wohnungstausch: {tauschwohnung}\n📄 WBS erforderlich: {wbs}\n🌐 Websites: {websites}\n\n🔎 *Suche ist AKTIV!* Sie erhalten neue Angebote, sobald sie erscheinen.",
            "not_set": "nicht festgelegt",
            "yes": "Ja",
            "no": "Nein"
        },
        "search": {
            "started": "🔎 Suche gestartet. Sie erhalten neue Angebote.",
            "stopped": "⛔ Suche gestoppt. Sie erhalten keine weiteren Angebote."
        },
        "open_webapp": "🏠 Filtereinstellungen öffnen",
        "data_error": "Bitte überprüfen Sie Ihre Eingaben.",
        "invite_friends_text": "👥 Laden Sie einen Freund ein und erhalten Sie 14 Tage kostenloses Abonnement!",
        "referral": {
            "success": "🎉 Sie haben *+{days} Tage* Abonnement für die Einladung von *{new_user}* erhalten!",
            "new_user_notification": "👋 Sie sind über einen Empfehlungslink beigetreten! Ihre kostenlose Testversion wurde aktiviert.",
            "self_invite": "❌ Sie können sich nicht selbst einladen!",
            "already_invited": "⚠️ Sie haben diesen Benutzer bereits eingeladen"
        }
    },
    "ru": {
        "start": "Добро пожаловать в Wohnungsbot Bot!",
        "trial": "Бесплатный пробный период до",
        "menu": ["🔎 Начать поиск", "⛔ Остановить поиск", "🏠 Установить фильтры", "💳 Подписка", "ℹ️ Моя подписка",
                 "👥 Пригласить друга", "🆘 Помощь"],
        "back_to_menu": "🔙 Назад в меню",
        "change_language": "🌐 Сменить язык",
        "help_button": "🆘 Помощь",
        "help_text": "По всем вопросам обращайтесь к {help_username}",
        "welcome_message": "👋 *Добро пожаловать в FlatFinder Bot!*\n\n"
"📢 Вы получили *бесплатный пробный период на 7 дней* – он активен до *{date}* ({days} дн.)\n\n"
"🏠 FlatFinder помогает вам первыми узнавать о новых объявлениях по аренде жилья в Германии.\n"
"🔔 Мы моментально уведомляем вас о новых предложениях, которые соответствуют вашим фильтрам.\n\n"
"📍 Укажите город, цену, площадь и другие параметры.\n"
"📬 Все предложения будут приходить прямо сюда, в Telegram.",
        "subscription": {
            "active": "📅 Ваша подписка активна до: *{date}* ({days} дн.)",
            "expired": "❌ Ваша подписка *истекла*. Вы можете оформить новую через 💳 *Подписка*",
            "none": "❌ У вас нет активной подписки.\n\n💡 При первом запуске вам доступен *бесплатный пробный период на 7 дней*.",
            "activated": "✅ Подписка активирована до *{date}*! Спасибо!",
            "will_expire_in_days": "⚠️ Ваша подписка истекает через {days} дн.",
            "will_expire_tomorrow": "⚠️ Ваша подписка истекает *завтра*.",
            "expired_notice": "❌ Ваша подписка *истекла*. Пожалуйста, оформите новую через 💳 *Подписка*.",
        },
        "webapp_error": "Пожалуйста, сначала установите фильтры через 🏠 Установить фильтры.",
        "invoice": {
            "title": "Подписка на сервис",
            "description": "Вы получите доступ к автоматической рассылке новых объявлений на 30 дней"
        },
        "filters": {
            "open": "📋 Нажмите кнопку ниже, чтобы установить фильтры:",
            "saved": "✅ *Фильтры сохранены!*\n💰 Цена: {min_price}€ – {max_price}€\n📏 Размер: {min_size}m² – {max_size}m²\n🏷️ Обмен квартир: {tauschwohnung}\n📄 Требуется WBS: {wbs}\n🌐 Сайты: {websites}\n\n🔎 *Поиск ВКЛЮЧЕН!* Вы будете получать новые объявления по мере их появления.",
            "not_set": "не установлено",
            "yes": "Да",
            "no": "Нет"
        },
        "search": {
            "started": "🔎 Поиск начат. Вы будете получать новые объявления.",
            "stopped": "⛔ Поиск остановлен. Вы больше не будете получать объявления."
        },
        "open_webapp": "🏠 Открыть настройки фильтров",
        "data_error": "Пожалуйста, проверьте ваши числа.",
        "invite_friends_text": "👥 Пригласите друга и получите 14 дней подписки бесплатно!",
        "referral": {
            "success": "🎉 Вы получили *+{days} дней* подписки за приглашение *{new_user}*!",
            "new_user_notification": "👋 Вы присоединились по реферальной ссылке! Ваш пробный период активирован.",
            "self_invite": "❌ Вы не можете пригласить самого себя!",
            "already_invited": "⚠️ Вы уже приглашали этого пользователя"
        }
    },
    "ar": {
        "start": "مرحبًا بك في بوت Wohnungsbot!",
        "trial": "تم تفعيل الفترة التجريبية المجانية حتى",
        "menu": ["🔎 بدء البحث", "⛔ إيقاف البحث", "🏠 إعداد الفلاتر", "💳 الاشتراك", "ℹ️ اشتراكي",
                 "👥 دعوة الأصدقاء", "🆘 مساعدة"],
        "back_to_menu": "🔙 العودة إلى القائمة",
        "change_language": "🌐 تغيير اللغة",
        "help_button": "🆘 مساعدة",
        "help_text": "لأي استفسارات، يرجى التواصل مع {help_username}",
        "welcome_message": "👋 *مرحبًا بك في FlatFinder Bot!*\n\n"
                       "📢 لقد حصلت على *فترة تجريبية مجانية لمدة 7 أيام* – سارية حتى *{date}* ({days} يومًا)\n\n"
                       "🏠 يساعدك FlatFinder في العثور على أحدث عروض الإيجار في ألمانيا.\n"
                       "🔔 نُرسل لك إشعارات فورية بالعروض التي تطابق فلاترك.\n\n"
                       "📍 قم بتحديد مدينتك، السعر، المساحة وتفضيلات أخرى.\n"
                       "📬 سيتم إرسال جميع الإعلانات هنا على Telegram.",
        "subscription": {
            "active": "📅 اشتراكك فعال حتى: *{date}* ({days} يومًا)",
            "expired": "❌ انتهت صلاحية اشتراكك. يمكنك تجديده عبر 💳 *الاشتراك*",
            "none": "❌ لا يوجد لديك اشتراك نشط.\n\n💡 عند البدء لأول مرة، تحصل على *فترة تجريبية مجانية لمدة 7 أيام*.",
            "activated": "✅ تم تفعيل الاشتراك حتى *{date}*! شكرًا لك!",
            "will_expire_in_days": "⚠️ سينتهي اشتراكك خلال {days} يومًا.",
            "will_expire_tomorrow": "⚠️ سينتهي اشتراكك *غدًا*.",
            "expired_notice": "❌ انتهت صلاحية اشتراكك. يرجى التجديد عبر 💳 *الاشتراك*."
        },
        "webapp_error": "يرجى إعداد الفلاتر أولاً عبر 🏠 إعداد الفلاتر.",
        "invoice": {
            "title": "الاشتراك",
            "description": "سوف تحصل على تحديثات تلقائية للعروض لمدة 30 يومًا"
        },
        "filters": {
            "open": "📋 انقر على الزر أدناه لإعداد الفلاتر:",
            "saved": "✅ *تم حفظ الفلاتر!*\n💰 السعر: {min_price}€ – {max_price}€\n📏 المساحة: {min_size}م² – {max_size}م²\n🏷️ تبادل الشقق: {tauschwohnung}\n📄 مطلوب WBS: {wbs}\n🌐 المواقع: {websites}\n\n🔎 *البحث مفعل!* سيتم إرسال العروض الجديدة إليك فور توفرها.",
            "not_set": "غير محدد",
            "yes": "نعم",
            "no": "لا"
        },
        "search": {
            "started": "🔎 تم بدء البحث. ستتلقى العروض الجديدة.",
            "stopped": "⛔ تم إيقاف البحث. لن تتلقى أي عروض جديدة."
        },
        "open_webapp": "🏠 إعدادات الفلاتر",
        "data_error": "يرجى التحقق من الأرقام المدخلة.",
        "invite_friends_text": "👥 ادعُ صديقًا واحصل على اشتراك مجاني لمدة 14 يومًا!",
        "referral": {
            "success": "🎉 حصلت على *+{days} يومًا* من الاشتراك لدعوة *{new_user}*!",
            "new_user_notification": "👋 لقد انضممت عبر رابط الإحالة! تم تفعيل الفترة التجريبية الخاصة بك.",
            "self_invite": "❌ لا يمكنك دعوة نفسك!",
            "already_invited": "⚠️ لقد دعوت هذا المستخدم من قبل"
        }
    },
    "tr": {
        "start": "Wohnungsbot Bot'a hoş geldiniz!",
        "trial": "Ücretsiz deneme süresi şu tarihe kadar aktif:",
        "menu": ["🔎 Aramayı Başlat", "⛔ Aramayı Durdur", "🏠 Filtreleri Ayarla", "💳 Abone Ol", "ℹ️ Aboneliğim",
                 "👥 Arkadaş Davet Et", "🆘 Yardım"],
        "back_to_menu": "🔙 Menüye Dön",
        "change_language": "🌐 Dili Değiştir",
        "help_button": "🆘 Yardım",
        "help_text": "Herhangi bir sorunuz için lütfen {help_username} ile iletişime geçin",
        "welcome_message": "👋 *FlatFinder Bot'a Hoş Geldiniz!*\n\n"
                       "📢 *7 günlük ücretsiz deneme süresi* kazandınız – geçerlilik tarihi: *{date}* ({days} gün)\n\n"
                       "🏠 FlatFinder, Almanya'daki yeni kiralık ilanları ilk sizin görmenizi sağlar.\n"
                       "🔔 Filtrelerinize uyan ilanlar anında size bildirilir.\n\n"
                       "📍 Şehir, fiyat, büyüklük ve diğer tercihlerinizi belirleyin.\n"
                       "📬 Tüm ilanlar doğrudan Telegram'a gönderilecektir.",
        "subscription": {
            "active": "📅 Aboneliğinizin bitiş tarihi: *{date}* ({days} gün)",
            "expired": "❌ Aboneliğiniz *sona erdi*. 💳 *Abone Ol* ile yenileyebilirsiniz.",
            "none": "❌ Aktif bir aboneliğiniz yok.\n\n💡 Başlangıçta *7 günlük ücretsiz deneme süresi* verilir.",
            "activated": "✅ Abonelik *{date}* tarihine kadar etkinleştirildi! Teşekkürler!",
            "will_expire_in_days": "⚠️ Aboneliğiniz {days} gün içinde sona erecek.",
            "will_expire_tomorrow": "⚠️ Aboneliğiniz *yarın* sona erecek.",
            "expired_notice": "❌ Aboneliğiniz sona erdi. Lütfen 💳 *Abone Ol* üzerinden yenileyin."
        },
        "webapp_error": "Lütfen önce 🏠 Filtreleri Ayarla üzerinden filtreleri ayarlayın.",
        "invoice": {
            "title": "Abonelik",
            "description": "30 gün boyunca otomatik ilan güncellemelerine erişim kazanırsınız"
        },
        "filters": {
            "open": "📋 Filtrelerinizi ayarlamak için aşağıdaki butona tıklayın:",
            "saved": "✅ *Filtre kaydedildi!*\n💰 Fiyat: {min_price}€ – {max_price}€\n📏 Büyüklük: {min_size}m² – {max_size}m²\n🏷️ Daire takası: {tauschwohnung}\n📄 WBS gerekli: {wbs}\n🌐 Web siteleri: {websites}\n\n🔎 *Arama açık!* Yeni ilanlar geldiğinde gönderilecektir.",
            "not_set": "ayarlanmadı",
            "yes": "Evet",
            "no": "Hayır"
        },
        "search": {
            "started": "🔎 Arama başlatıldı. Yeni ilanlar size gönderilecek.",
            "stopped": "⛔ Arama durduruldu. Artık ilan almayacaksınız."
        },
        "open_webapp": "🏠 Filtre Ayarlarını Aç",
        "data_error": "Lütfen sayıların doğruluğunu kontrol edin.",
        "invite_friends_text": "👥 Bir arkadaş davet et ve 14 gün ücretsiz abonelik kazan!",
        "referral": {
            "success": "🎉 *{new_user}* kişisini davet ettiğiniz için *+{days} gün* abonelik kazandınız!",
            "new_user_notification": "👋 Referans linkiyle katıldınız! Ücretsiz denemeniz etkinleştirildi.",
            "self_invite": "❌ Kendinizi davet edemezsiniz!",
            "already_invited": "⚠️ Bu kullanıcıyı zaten davet ettiniz"
        }
    }
}

# === Create users table ===
def create_users_table():
    conn = sqlite3.connect("seen_ids.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            language TEXT DEFAULT 'en',
            location TEXT,
            min_price INTEGER DEFAULT NULL,
            max_price INTEGER DEFAULT NULL,
            min_size INTEGER DEFAULT NULL,
            max_size INTEGER DEFAULT NULL,
            tauschwohnung BOOLEAN DEFAULT 0,
            wbs BOOLEAN DEFAULT 0,
            use_immoscout BOOLEAN DEFAULT 1,
            use_kleinanzeigen BOOLEAN DEFAULT 1,
            use_immowelt BOOLEAN DEFAULT 1,
            subscribed_until TEXT,
            is_searching BOOLEAN DEFAULT 0,
            referred_by INTEGER DEFAULT NULL,
            use_inberlinwohnen BOOLEAN DEFAULT 1
        )
    """)

    # Add missing columns if they don't exist
    for column, col_type in [
        ("first_name", "TEXT"),
        ("last_name", "TEXT"),
        ("username", "TEXT"),
        ("language", "TEXT DEFAULT 'en'"),
        ("referred_by", "INTEGER DEFAULT NULL"),
        ("use_inberlinwohnen", "BOOLEAN DEFAULT 1")
    ]:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {column} {col_type}")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()

# === Language management ===
def get_user_language(user_id):
    conn = sqlite3.connect("seen_ids.db")
    cursor = conn.cursor()
    cursor.execute("SELECT language FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE

def set_user_language(user_id, lang):
    if lang not in SUPPORTED_LANGUAGES:
        return
    conn = sqlite3.connect("seen_ids.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET language = ? WHERE id = ?", (lang, user_id))
    conn.commit()
    conn.close()

def get_language_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [
            KeyboardButton(text="🇬🇧 English"),
            KeyboardButton(text="🇩🇪 Deutsch"),
            KeyboardButton(text="🇷🇺 Русский"),
            KeyboardButton(text="🇦🇪 العربية"),  # Arabic
            KeyboardButton(text="🇹🇷 Türkçe")   # Turkish
        ]
    ], resize_keyboard=True)

def get_main_menu(lang):
    labels = translations[lang]["menu"]
    change_lang = translations[lang]["change_language"]
    help_btn = translations[lang]["help_button"]
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=labels[0]), KeyboardButton(text=labels[1])],
        [KeyboardButton(text=labels[2]), KeyboardButton(text=labels[3])],
        [KeyboardButton(text=labels[4]), KeyboardButton(text=labels[5])],
        [KeyboardButton(text=change_lang), KeyboardButton(text=help_btn)]
    ], resize_keyboard=True)

# === Sanitize surrogate pairs ===
def sanitize(text):
    if not text:
        return None
    return text.encode('utf-16', 'surrogatepass').decode('utf-16', 'ignore')

# === Add user if not exists ===
async def add_user_to_db(user: types.User, referrer_id=None):
    conn = sqlite3.connect("seen_ids.db")
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE id = ?", (user.id,))
    row = cursor.fetchone()

    if row is None:
        # New user - trial period + referral
        trial_end = datetime.now() + timedelta(days=7)
        cursor.execute("""
            INSERT INTO users (id, first_name, last_name, username, subscribed_until, is_searching, referred_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user.id,
            sanitize(user.first_name),
            sanitize(user.last_name),
            user.username,
            trial_end.isoformat(),
            0,
            referrer_id
        ))
        logger.info(f"[DB] New user added: {user.id} (referred_by={referrer_id})")

        # Bonus for referrer
        if referrer_id and referrer_id != user.id:
            cursor.execute("SELECT subscribed_until, language FROM users WHERE id = ?", (referrer_id,))
            ref_row = cursor.fetchone()
            if ref_row:
                try:
                    current_sub = datetime.fromisoformat(ref_row[0]) if ref_row[0] else datetime.now()
                except Exception:
                    current_sub = datetime.now()

                bonus_sub = current_sub + timedelta(days=14)
                cursor.execute("UPDATE users SET subscribed_until = ? WHERE id = ?",
                               (bonus_sub.isoformat(), referrer_id))
                logger.info(f"[REFERRAL] User {referrer_id} got +14 days for inviting {user.id}")

                # Notification to referrer
                ref_lang = ref_row[1] if ref_row[1] in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
                try:
                    await bot.send_message(
                        chat_id=referrer_id,
                        text=translations[ref_lang]["referral"]["success"].format(
                            days=14,
                            new_user=user.first_name or "New user"
                        ),
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"[REFERRAL] Error sending notification to {referrer_id}: {e}")
            else:
                logger.warning(f"[REFERRAL] Referrer {referrer_id} not found.")
    else:
        # Existing user - update name/username
        cursor.execute("""
            UPDATE users SET first_name = ?, last_name = ?, username = ? WHERE id = ?
        """, (
            sanitize(user.first_name),
            sanitize(user.last_name),
            user.username,
            user.id
        ))
        logger.info(f"[DB] Existing user {user.id} info updated.")

    conn.commit()
    conn.close()

# === Save user filters ===
def save_user_filters(user_id, location, min_price, max_price, min_size, max_size,
                      tauschwohnung=False, wbs=False,
                      use_immoscout=True, use_kleinanzeigen=True, use_immowelt=True, use_inberlinwohnen=True):
    try:
        conn = sqlite3.connect("seen_ids.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (id, location, min_price, max_price, min_size, max_size,
                              tauschwohnung, wbs,
                              use_immoscout, use_kleinanzeigen, use_immowelt, use_inberlinwohnen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO
            UPDATE SET
                location = excluded.location,
                min_price = excluded.min_price,
                max_price = excluded.max_price,
                min_size = excluded.min_size,
                max_size = excluded.max_size,
                tauschwohnung = excluded.tauschwohnung,
                wbs = excluded.wbs,
                use_immoscout = excluded.use_immoscout,
                use_kleinanzeigen = excluded.use_kleinanzeigen,
                use_immowelt = excluded.use_immowelt,
                use_inberlinwohnen = excluded.use_inberlinwohnen
        """, (user_id, location, min_price, max_price, min_size, max_size,
              tauschwohnung, wbs, use_immoscout, use_kleinanzeigen, use_immowelt, use_inberlinwohnen))
        conn.commit()
        conn.close()
        logger.info(f"[DB] User {user_id} filters updated")
    except sqlite3.Error as e:
        logger.error(f"[DB] Error saving filters: {e}")

# === Menu actions for all languages ===
MENU_ACTIONS = {
    # English
    "🔎 Start Search": "start_search",
    "⛔ Stop Search": "stop_search",
    "🏠 Set Filters": "set_filters",
    "💳 Subscribe": "subscribe",
    "ℹ️ My Subscription": "my_subscription",
    "👥 Invite Friends": "invite",
    "🔙 Back to Menu": "back_to_menu",
    "🌐 Change Language": "change_language",
    "🆘 Help": "help",

    # German
    "🔎 Suche starten": "start_search",
    "⛔ Suche stoppen": "stop_search",
    "🏠 Filter setzen": "set_filters",
    "💳 Abonnieren": "subscribe",
    "ℹ️ Mein Abo": "my_subscription",
    "👥 Freunde einladen": "invite",
    "🔙 Zurück zum Menü": "back_to_menu",
    "🌐 Sprache ändern": "change_language",
    "🆘 Hilfe": "help",

    # Russian
    "🔎 Начать поиск": "start_search",
    "⛔ Остановить поиск": "stop_search",
    "🏠 Установить фильтры": "set_filters",
    "💳 Подписка": "subscribe",
    "ℹ️ Моя подписка": "my_subscription",
    "👥 Пригласить друга": "invite",
    "🔙 Назад в меню": "back_to_menu",
    "🌐 Сменить язык": "change_language",
    "🆘 Помощь": "help",

    # Arabic
    "🔎 بدء البحث": "start_search",
    "⛔ إيقاف البحث": "stop_search",
    "🏠 إعداد الفلاتر": "set_filters",
    "💳 الاشتراك": "subscribe",
    "ℹ️ اشتراكي": "my_subscription",
    "👥 دعوة الأصدقاء": "invite",
    "🔙 العودة إلى القائمة": "back_to_menu",
    "🌐 تغيير اللغة": "change_language",
    "🆘 مساعدة": "help",

    # Turkish
    "🔎 Aramayı Başlat": "start_search",
    "⛔ Aramayı Durdur": "stop_search",
    "🏠 Filtreleri Ayarla": "set_filters",
    "💳 Abone Ol": "subscribe",
    "ℹ️ Aboneliğim": "my_subscription",
    "👥 Arkadaş Davet Et": "invite",
    "🔙 Menüye Dön": "back_to_menu",
    "🌐 Dili Değiştir": "change_language",
    "🆘 Yardım": "help"
}

@dp.message(Command("start"))
async def cmd_start(message: types.Message, command: CommandObject):
    referrer_id = None
    if command.args:
        try:
            referrer_id = int(command.args)
            if referrer_id == message.from_user.id:
                lang = get_user_language(message.from_user.id)
                await message.answer(translations[lang]["referral"]["self_invite"])
                referrer_id = None
        except ValueError:
            pass

    await add_user_to_db(message.from_user, referrer_id)

    # Notification to new user
    if referrer_id:
        lang = get_user_language(message.from_user.id)
        await message.answer(
            translations[lang]["referral"]["new_user_notification"],
            parse_mode="Markdown"
        )

    await message.answer(
        "Please select your language / Bitte wählen Sie Ihre Sprache / Пожалуйста, выберите язык / الرجاء اختيار اللغة / Lütfen dilinizi seçin:",
        reply_markup=get_language_keyboard()
    )

# Invite friends handler
@dp.message(F.text.in_(["👥 Пригласить друга", "👥 Invite Friends", "👥 Freunde einladen", "👥 دعوة الأصدقاء", "👥 Arkadaş Davet Et"]))
async def referral_link_handler(message: types.Message):
    user_id = message.chat.id
    lang = get_user_language(user_id)
    ref_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
    await message.answer(
        translations[lang]["invite_friends_text"] + f"\n\n🔗 {ref_link}"
    )

# Help handler
@dp.message(F.text.in_(["🆘 Help", "🆘 Hilfe", "🆘 Помощь", "🆘 مساعدة", "🆘 Yardım"]))
async def help_handler(message: types.Message):
    user_id = message.chat.id
    lang = get_user_language(user_id)
    await message.answer(
        translations[lang]["help_text"].format(help_username=HELP_USERNAME),
        parse_mode="Markdown"
    )

@dp.message(F.text.in_(["🇬🇧 English", "🇩🇪 Deutsch", "🇷🇺 Русский", "🇦🇪 العربية", "🇹🇷 Türkçe"]))
async def select_language(message: types.Message):
    user_id = message.chat.id
    lang_map = {
        "🇬🇧 English": "en",
        "🇩🇪 Deutsch": "de",
        "🇷🇺 Русский": "ru",
        "🇦🇪 العربية": "ar",
        "🇹🇷 Türkçe": "tr"
    }
    lang = lang_map.get(message.text, DEFAULT_LANGUAGE)
    set_user_language(user_id, lang)
    await add_user_to_db(message.from_user)

    conn = sqlite3.connect("seen_ids.db")
    cursor = conn.cursor()
    cursor.execute("SELECT subscribed_until FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    trial_end_text = ""
    if row and row[0]:
        try:
            sub_until = datetime.fromisoformat(row[0])
            days = (sub_until.date() - datetime.now().date()).days
            trial_end_text = translations[lang]["welcome_message"].format(
                date=sub_until.strftime("%d.%m.%Y"),
                days=days
            )
        except Exception as e:
            logger.warning(f"[START] Error parsing subscription date: {e}")

    await message.answer(
        trial_end_text,
        parse_mode="Markdown",
        reply_markup=get_main_menu(lang)
    )

async def subscribe_handler(message: types.Message):
    lang = get_user_language(message.chat.id)
    prices = [LabeledPrice(label="XTR", amount=250)]

    await message.answer_invoice(
        title=translations[lang]["invoice"]["title"],
        description=translations[lang]["invoice"]["description"],
        payload="subscription_30_days",
        provider_token="",  # Leave empty for Telegram Stars
        currency="XTR",
        prices=prices,
        start_parameter="pro_month"
    )

@dp.message(F.text.in_([
    "🌐 Change Language",
    "🌐 Sprache ändern",
    "🌐 Сменить язык",
    "🌐 تغيير اللغة",
    "🌐 Dili Değiştir"
]))
async def change_language(message: types.Message):
    await message.answer(
        "Please select your language / Bitte wählen Sie Ihre Sprache / Пожалуйста, выберите язык / الرجاء اختيار اللغة / Lütfen dilinizi seçin:",
        reply_markup=get_language_keyboard()
    )

@dp.pre_checkout_query()
async def pre_checkout_query(query: PreCheckoutQuery):
    await query.answer(ok=True)

# === Check subscription status ===
def check_subscription(user_id):
    conn = sqlite3.connect("seen_ids.db")
    cursor = conn.cursor()
    cursor.execute("SELECT subscribed_until, is_searching FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row[0]:
        return False

    try:
        sub_until = datetime.fromisoformat(row[0])
        now = datetime.now()
        if sub_until < now:
            # Subscription expired, disable searching
            conn = sqlite3.connect("seen_ids.db")
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_searching = 0 WHERE id = ?", (user_id,))
            conn.commit()
            conn.close()
            return False
        return True
    except Exception as e:
        logger.error(f"[DB] Error checking subscription: {e}")
        return False

def get_subscription_warning_message(subscribed_until: datetime, lang: str) -> str:
    now = datetime.now()
    days_left = (subscribed_until.date() - now.date()).days

    if days_left == 1:
        return translations[lang]["subscription"]["will_expire_tomorrow"]
    elif 1 < days_left <= 3:
        return translations[lang]["subscription"]["will_expire_in_days"].format(days=days_left)
    elif days_left < 0:
        return translations[lang]["subscription"]["expired_notice"]
    return ""

async def my_subscription_handler(message: types.Message):
    user_id = message.chat.id
    lang = get_user_language(user_id)
    conn = sqlite3.connect("seen_ids.db")
    cursor = conn.cursor()
    cursor.execute("SELECT subscribed_until FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if row and row[0]:
        try:
            sub_until = datetime.fromisoformat(row[0])
            if sub_until > datetime.now():
                remaining = (sub_until - datetime.now()).days
                warning_msg = get_subscription_warning_message(sub_until, lang)
                await message.answer(
                    translations[lang]["subscription"]["active"].format(
                        date=sub_until.date(),
                        days=remaining
                    ) + (f"\n\n{warning_msg}" if warning_msg else ""),
                    parse_mode="Markdown"
                )
            else:
                await message.answer(
                    translations[lang]["subscription"]["expired"],
                    parse_mode="Markdown"
                )
        except Exception as e:
            await message.answer("⚠️ Error checking subscription.")
            logger.warning(f"[Subscription] Date parsing error: {e}")
    else:
        await message.answer(
            translations[lang]["subscription"]["none"],
            parse_mode="Markdown"
        )

@dp.message(F.successful_payment)
async def handle_successful_payment(message: types.Message):
    user_id = message.chat.id
    lang = get_user_language(user_id)
    now = datetime.now()

    conn = sqlite3.connect("seen_ids.db")
    cursor = conn.cursor()
    cursor.execute("SELECT subscribed_until FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()

    if row and row[0]:
        try:
            current_until = datetime.fromisoformat(row[0])
            if current_until > now:
                new_until = current_until + timedelta(days=30)
            else:
                new_until = now + timedelta(days=30)
        except Exception as e:
            logger.warning(f"[PAYMENT] Date parsing error: {e}")
            new_until = now + timedelta(days=30)
    else:
        new_until = now + timedelta(days=30)

    cursor.execute("UPDATE users SET subscribed_until = ? WHERE id = ?", (new_until.isoformat(), user_id))
    conn.commit()
    conn.close()

    await message.answer(
        translations[lang]["subscription"]["activated"].format(
            date=new_until.strftime('%d.%m.%Y')
        ),
        parse_mode="Markdown"
    )

async def open_filters(message: types.Message):
    user_id = message.chat.id
    lang = get_user_language(user_id)
    await add_user_to_db(message.from_user)
    webapp_url = WEBAPP_URLS.get(lang, WEBAPP_URLS["de"])

    open_button = KeyboardButton(
        text=translations[lang]["open_webapp"],
        web_app=WebAppInfo(url=webapp_url)
    )

    back_button = KeyboardButton(text=translations[lang]["back_to_menu"])
    markup = ReplyKeyboardMarkup(keyboard=[[open_button], [back_button]], resize_keyboard=True)

    await message.answer(translations[lang]["filters"]["open"], reply_markup=markup)

@dp.message(F.content_type == types.ContentType.WEB_APP_DATA)
async def webapp_data_handler(message: types.Message):
    user_id = message.from_user.id
    lang = get_user_language(user_id)

    # Check subscription first
    if not check_subscription(user_id):
        await message.answer(
            translations[lang]["subscription"]["expired"],
            parse_mode="Markdown"
        )
        return

    if not message.web_app_data or not message.web_app_data.data:
        await message.answer(translations[lang]["webapp_error"])
        return

    try:
        data = json.loads(message.web_app_data.data)
        logger.info(f"[WEBAPP] Data received from {message.from_user.id}: {data}")
    except json.JSONDecodeError:
        await message.answer(translations[lang]["webapp_error"])
        return

    price = data.get("price") or [None, None]
    size = data.get("size") or [None, None]
    tauschwohnung = data.get("tauschwohnung", False)
    wbs = data.get("wbs", False)
    websites = data.get("websites", [])

    use_immoscout = "immobilienscout24" in websites
    use_kleinanzeigen = "kleinanzeigen" in websites
    use_immowelt = "immowelt" in websites
    use_inberlinwohnen = "inberlinwohnen" in websites

    location_text = None
    if "location" in data:
        loc = data["location"]
        if loc["type"] == "circle":
            location_text = f"{loc['center'][0]}, {loc['center'][1]}, {loc['radius']}"
        elif loc["type"] == "polygon":
            location_text = "; ".join([f"{p[0]}, {p[1]}" for p in loc["coordinates"]])

    try:
        min_price = int(float(price[0])) if price and len(price) > 0 and price[0] else None
        max_price = int(float(price[1])) if price and len(price) > 1 and price[1] else None
        min_size = int(float(size[0])) if size and len(size) > 0 and size[0] else None
        max_size = int(float(size[1])) if size and len(size) > 1 and size[1] else None
    except (ValueError, TypeError):
        await message.answer(translations[lang]["data_error"])
        return

    save_user_filters(
        user_id=user_id,
        location=location_text,
        min_price=min_price,
        max_price=max_price,
        min_size=min_size,
        max_size=max_size,
        tauschwohnung=tauschwohnung,
        wbs=wbs,
        use_immoscout=use_immoscout,
        use_kleinanzeigen=use_kleinanzeigen,
        use_immowelt=use_immowelt,
        use_inberlinwohnen=use_inberlinwohnen
    )

    # Enable is_searching after filters set
    conn = sqlite3.connect("seen_ids.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_searching = 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    logger.info(f"[DB] Search enabled after setting filters for user {user_id}")

    tauschwohnung_text = translations[lang]["filters"]["yes"] if tauschwohnung else translations[lang]["filters"]["no"]
    wbs_text = translations[lang]["filters"]["yes"] if wbs else translations[lang]["filters"]["no"]
    min_price_text = min_price if min_price else translations[lang]["filters"]["not_set"]
    max_price_text = max_price if max_price else translations[lang]["filters"]["not_set"]
    min_size_text = min_size if min_size else translations[lang]["filters"]["not_set"]
    max_size_text = max_size if max_size else translations[lang]["filters"]["not_set"]

    websites_list = []
    if use_immoscout:
        websites_list.append("Scout")
    if use_kleinanzeigen:
        websites_list.append("Kleinanzeigen")
    if use_immowelt:
        websites_list.append("Immowelt")
    websites_text = "/".join(websites_list) if websites_list else translations[lang]["filters"]["not_set"]

    await message.answer(
        translations[lang]["filters"]["saved"].format(
            min_price=min_price_text,
            max_price=max_price_text,
            min_size=min_size_text,
            max_size=max_size_text,
            tauschwohnung=tauschwohnung_text,
            wbs=wbs_text,
            websites=websites_text
        ),
        parse_mode="Markdown",
        reply_markup=get_main_menu(lang)
    )

@dp.message(F.text.in_(MENU_ACTIONS.keys()))
async def handle_menu_actions(message: types.Message):
    user_id = message.chat.id
    lang = get_user_language(user_id)
    text = message.text.strip()
    action = MENU_ACTIONS.get(text)

    # Help is always available
    if action == "help":
        await help_handler(message)
        return

    # Other actions require active subscription
    if action not in ["subscribe", "my_subscription", "help"]:
        if not check_subscription(user_id):
            await message.answer(
                translations[lang]["subscription"]["expired"],
                parse_mode="Markdown"
            )
            return

    if action == "start_search":
        conn = sqlite3.connect("seen_ids.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT location, use_immoscout, use_kleinanzeigen, use_immowelt
            FROM users WHERE id = ?
        """, (user_id,))
        row = cursor.fetchone()
        if not row:
            await message.answer("⚠️ User not found in database.")
            return

        location, scout, klein, welt = row
        if not location or not (scout or klein or welt):
            await message.answer(
                f"⚠️ {translations[lang]['webapp_error']}\n\n"
                f"{translations[lang]['filters']['open']}",
                reply_markup=get_main_menu(lang)
            )
            return

        cursor.execute("UPDATE users SET is_searching = 1 WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        logger.info(f"[DB] User {user_id} started search.")
        await message.answer(translations[lang]["search"]["started"])

    elif action == "stop_search":
        conn = sqlite3.connect("seen_ids.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_searching = 0 WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        logger.info(f"[DB] User {user_id} stopped search.")
        await message.answer(translations[lang]["search"]["stopped"])

    elif action == "set_filters":
        await open_filters(message)

    elif action == "subscribe":
        await subscribe_handler(message)

    elif action == "my_subscription":
        await my_subscription_handler(message)

    elif action == "invite":
        await referral_link_handler(message)

    elif action == "back_to_menu":
        await message.answer(
            translations[lang]["start"],
            reply_markup=get_main_menu(lang)
        )

    elif action == "change_language":
        await change_language(message)

async def subscription_reminder_loop():
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Europe/Berlin")  # Часовой пояс Берлина

    def get_next_run_time():
        now = datetime.now(tz)
        today_8 = now.replace(hour=8, minute=0, second=0, microsecond=0)
        today_16 = now.replace(hour=16, minute=0, second=0, microsecond=0)

        if now < today_8:
            return today_8
        elif now < today_16:
            return today_16
        else:
            return (now + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)

    logger.info("[REMINDER_LOOP] Started subscription reminder loop.")
    heartbeat_interval = 600  # 10 минут

    while True:
        try:
            logger.debug("[REMINDER_LOOP] Heartbeat: loop is alive.")
            now = datetime.now(tz)
            today_str = now.strftime('%Y-%m-%d')

            # Получаем список всех пользователей заранее
            with sqlite3.connect("seen_ids.db") as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, subscribed_until, language FROM users")
                users = cursor.fetchall()

            for user_id, sub_until_str, lang in users:
                if not sub_until_str:
                    continue
                try:
                    sub_until = datetime.fromisoformat(sub_until_str)
                except Exception:
                    continue

                days_left = (sub_until.date() - now.date()).days
                if days_left in [3, 2, 1, 0, -1]:
                    if lang not in SUPPORTED_LANGUAGES:
                        lang = DEFAULT_LANGUAGE
                    warning_text = get_subscription_warning_message(sub_until, lang)
                    if not warning_text:
                        continue

                    try:
                        with sqlite3.connect("seen_ids.db") as conn:
                            cursor = conn.cursor()
                            cursor.execute("SELECT last_warned FROM subscription_notifications WHERE user_id = ?", (user_id,))
                            row = cursor.fetchone()
                            if row and row[0] == today_str:
                                continue  # Уже отправляли сегодня

                            await bot.send_message(user_id, warning_text)
                            logger.info(f"[REMINDER] Sent to {user_id}: {warning_text}")

                            cursor.execute("""
                                INSERT INTO subscription_notifications (user_id, last_warned)
                                VALUES (?, ?)
                                ON CONFLICT(user_id) DO UPDATE SET last_warned = excluded.last_warned
                            """, (user_id, today_str))
                            conn.commit()

                    except Exception as e:
                        logger.warning(f"[REMINDER] Failed for {user_id}: {e}")

        except Exception as e:
            logger.error(f"[REMINDER_LOOP] Unexpected error: {e}")

        try:
            now = datetime.now(tz)
            next_run = get_next_run_time()
            wait_seconds = (next_run - now).total_seconds()
            logger.info(f"[REMINDER_LOOP] Sleeping for {int(wait_seconds)} seconds until {next_run}")
            await asyncio.sleep(wait_seconds)
        except Exception as e:
            logger.error(f"[REMINDER_LOOP] Sleep error: {e}")
            await asyncio.sleep(heartbeat_interval)

# === Entry point ===
async def main():
    create_users_table()
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("✅ Bot started with Help support.")

    # Start subscription reminder loop
    try:
        asyncio.create_task(subscription_reminder_loop())
        logger.info("[REMINDER_LOOP] Background task started.")
    except Exception as e:
        logger.error(f"[REMINDER_LOOP] Failed to start: {e}")

    # Start bot
    await dp.start_polling(bot)

@dp.message()
async def fallback_handler(message: types.Message):
    user_id = message.chat.id
    lang = get_user_language(user_id)
    menu_items = translations[lang]["menu"] + [
        translations[lang]["change_language"],
        translations[lang]["back_to_menu"],
        translations[lang]["help_button"]
    ]

    if message.text in menu_items:
        return  # Should be handled by other handlers

    if message.text.startswith("/"):
        return  # Ignore commands like /start

    # Check if user exists in DB
    conn = sqlite3.connect("seen_ids.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    user_exists = cursor.fetchone()
    conn.close()

    if not user_exists:
        await add_user_to_db(message.from_user)

    # Send language selection
    await message.answer(
        "Please select your language / Bitte wählen Sie Ihre Sprache / Пожалуйста, выберите язык / الرجاء اختيار اللغة / Lütfen dilinizi seçin:",
        reply_markup=get_language_keyboard()
    )

if __name__ == "__main__":
    asyncio.run(main())
