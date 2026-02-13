#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ramazan Ayı İftar ve Sahur Saatleri Telegram Botu
Bu bot, kullanıcılara şehirlerine göre iftar ve sahur saatlerini gösterir.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler
)

# Logging ayarları
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Kullanıcı verilerini saklamak için basit bir veritabanı (production'da SQLite veya Redis kullanılmalı)
user_data_file = "user_data.json"

# Türkiye'deki şehirler için örnek namaz vakitleri (Ramazan 2025 - 1 Mart tarihi için örnek)
# Gerçek uygulamada bir API'den alınmalı (örn: Diyanet API)
PRAYER_TIMES = {
    "istanbul": {
        "name": "İstanbul",
        "iftar": "18:45",
        "sahur": "05:15"
    },
    "ankara": {
        "name": "Ankara",
        "iftar": "18:42",
        "sahur": "05:12"
    },
    "izmir": {
        "name": "İzmir",
        "iftar": "18:52",
        "sahur": "05:22"
    },
    "bursa": {
        "name": "Bursa",
        "iftar": "18:47",
        "sahur": "05:17"
    },
    "antalya": {
        "name": "Antalya",
        "iftar": "18:55",
        "sahur": "05:25"
    },
    "adana": {
        "name": "Adana",
        "iftar": "18:48",
        "sahur": "05:18"
    },
    "konya": {
        "name": "Konya",
        "iftar": "18:45",
        "sahur": "05:15"
    },
    "gaziantep": {
        "name": "Gaziantep",
        "iftar": "18:43",
        "sahur": "05:13"
    },
    "kayseri": {
        "name": "Kayseri",
        "iftar": "18:40",
        "sahur": "05:10"
    },
    "trabzon": {
        "name": "Trabzon",
        "iftar": "18:35",
        "sahur": "05:05"
    }
}


class UserDataManager:
    """Kullanıcı verilerini yöneten sınıf"""
    
    def __init__(self):
        self.data = self.load_data()
    
    def load_data(self) -> Dict:
        """JSON dosyasından verileri yükle"""
        if os.path.exists(user_data_file):
            try:
                with open(user_data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Veri yükleme hatası: {e}")
                return {}
        return {}
    
    def save_data(self):
        """Verileri JSON dosyasına kaydet"""
        try:
            with open(user_data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Veri kaydetme hatası: {e}")
    
    def get_user_city(self, user_id: int) -> Optional[str]:
        """Kullanıcının kayıtlı şehrini getir"""
        user_id_str = str(user_id)
        return self.data.get(user_id_str, {}).get('city')
    
    def set_user_city(self, user_id: int, city: str):
        """Kullanıcının şehrini kaydet"""
        user_id_str = str(user_id)
        if user_id_str not in self.data:
            self.data[user_id_str] = {}
        self.data[user_id_str]['city'] = city
        self.save_data()
    
    def get_user_reminders(self, user_id: int) -> Dict:
        """Kullanıcının hatırlatıcılarını getir"""
        user_id_str = str(user_id)
        return self.data.get(user_id_str, {}).get('reminders', {})
    
    def set_user_reminder(self, user_id: int, reminder_type: str, minutes_before: int):
        """Kullanıcının hatırlatıcısını kaydet"""
        user_id_str = str(user_id)
        if user_id_str not in self.data:
            self.data[user_id_str] = {}
        if 'reminders' not in self.data[user_id_str]:
            self.data[user_id_str]['reminders'] = {}
        self.data[user_id_str]['reminders'][reminder_type] = minutes_before
        self.save_data()
    
    def remove_user_reminder(self, user_id: int, reminder_type: str):
        """Kullanıcının hatırlatıcısını sil"""
        user_id_str = str(user_id)
        if user_id_str in self.data and 'reminders' in self.data[user_id_str]:
            self.data[user_id_str]['reminders'].pop(reminder_type, None)
            self.save_data()


# Global veri yöneticisi
user_manager = UserDataManager()


def calculate_time_remaining(target_time_str: str) -> tuple:
    """Belirli bir saate kalan süreyi hesapla"""
    now = datetime.now()
    target_hour, target_minute = map(int, target_time_str.split(':'))
    
    target_time = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
    
    # Eğer hedef zaman geçmişte ise, yarına ekle
    if target_time <= now:
        target_time += timedelta(days=1)
    
    time_diff = target_time - now
    hours = time_diff.seconds // 3600
    minutes = (time_diff.seconds % 3600) // 60
    
    return hours, minutes


def format_prayer_time_message(city_name: str, prayer_type: str, prayer_time: str) -> str:
    """Namaz vakti mesajını formatla"""
    hours, minutes = calculate_time_remaining(prayer_time)
    
    # Saat ve dakika formatı
    if hours > 0:
        time_remaining = f"{hours} saat {minutes} dakika"
    else:
        time_remaining = f"{minutes} dakika"
    
    prayer_label = "İftar" if prayer_type == "iftar" else "Sahur"
    
    message = f"📍 {city_name}\n"
    message += f"🕌 {prayer_label} Saati: {prayer_time}\n"
    message += f"⏰ Kalan Süre: {time_remaining}"
    
    return message


def normalize_city_name(city: str) -> str:
    """Şehir adını normalize et (küçük harf, Türkçe karakterler)"""
    city = city.lower().strip()
    # Türkçe karakter dönüşümleri
    replacements = {
        'ı': 'i', 'ğ': 'g', 'ü': 'u', 'ş': 's', 'ö': 'o', 'ç': 'c',
        'İ': 'i', 'Ğ': 'g', 'Ü': 'u', 'Ş': 's', 'Ö': 'o', 'Ç': 'c'
    }
    for old, new in replacements.items():
        city = city.replace(old, new)
    return city


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start komutu - hoş geldiniz mesajı"""
    user = update.effective_user
    
    welcome_message = (
        f"🌙 Hoş geldin {user.first_name}!\n\n"
        "Bu bot, Ramazan ayında iftar ve sahur saatlerini öğrenmenize yardımcı olur.\n\n"
        "📋 *Komutlar:*\n"
        "/iftar [şehir] - İftar saatini öğren\n"
        "/sahur [şehir] - Sahur saatini öğren\n"
        "/sehir - Şehir seç veya değiştir\n"
        "/hatirlatici - Hatırlatıcı ayarla\n"
        "/bugun - Bugünün saatlerini gör\n"
        "/yardim - Yardım mesajını görüntüle\n\n"
        "💡 *İpucu:* Bir kez şehir belirttikten sonra, sadece /iftar veya /sahur "
        "yazarak son kullandığınız şehrin saatlerini görebilirsiniz.\n\n"
        "Başlamak için /sehir komutuyla şehrinizi seçin!"
    )
    
    await update.message.reply_text(welcome_message, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yardım komutu"""
    help_text = (
        "🌙 *Ramazan Botu Kullanım Kılavuzu*\n\n"
        "📋 *Temel Komutlar:*\n"
        "• /iftar - İftar saatini göster\n"
        "• /sahur - Sahur saatini göster\n"
        "• /sehir - Şehir seç\n"
        "• /bugun - Bugünün iftar ve sahur saatlerini göster\n"
        "• /hatirlatici - Hatırlatıcı ayarla\n\n"
        "🏙 *Şehir ile Kullanım:*\n"
        "• /iftar İstanbul\n"
        "• /sahur Ankara\n\n"
        "💡 *İpuçları:*\n"
        "• Bir kez şehir seçtikten sonra tekrar belirtmenize gerek yok\n"
        "• Hatırlatıcılar sayesinde iftar ve sahur vakitlerini kaçırmayın\n"
        "• /bugun komutuyla günün tüm vakitlerini tek seferde görebilirsiniz\n\n"
        "❓ Sorularınız için: @destek"
    )
    
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def iftar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """İftar saati komutu"""
    user_id = update.effective_user.id
    
    # Argüman var mı kontrol et
    if context.args:
        city = ' '.join(context.args)
    else:
        # Kayıtlı şehri kullan
        city = user_manager.get_user_city(user_id)
        if not city:
            keyboard = [
                [InlineKeyboardButton("🏙 Şehir Seç", callback_data='select_city')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "❌ Lütfen önce bir şehir seçin veya şehir adını yazın.\n"
                "Örnek: /iftar İstanbul",
                reply_markup=reply_markup
            )
            return
    
    # Şehir adını normalize et
    normalized_city = normalize_city_name(city)
    
    # Şehir verilerini kontrol et
    if normalized_city not in PRAYER_TIMES:
        available_cities = ", ".join([data['name'] for data in PRAYER_TIMES.values()])
        await update.message.reply_text(
            f"❌ '{city}' şehri bulunamadı.\n\n"
            f"Mevcut şehirler: {available_cities}\n\n"
            "Şehir seçmek için /sehir komutunu kullanabilirsiniz."
        )
        return
    
    # Şehri kaydet
    user_manager.set_user_city(user_id, normalized_city)
    
    # Vakitleri al
    city_data = PRAYER_TIMES[normalized_city]
    message = format_prayer_time_message(
        city_data['name'],
        'iftar',
        city_data['iftar']
    )
    
    # Hatırlatıcı butonu ekle
    keyboard = [
        [InlineKeyboardButton("⏰ Hatırlatıcı Ayarla", callback_data='reminder_iftar')],
        [InlineKeyboardButton("📅 Bugünün Vakitleri", callback_data='today')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(message, reply_markup=reply_markup)


async def sahur_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sahur saati komutu"""
    user_id = update.effective_user.id
    
    # Argüman var mı kontrol et
    if context.args:
        city = ' '.join(context.args)
    else:
        # Kayıtlı şehri kullan
        city = user_manager.get_user_city(user_id)
        if not city:
            keyboard = [
                [InlineKeyboardButton("🏙 Şehir Seç", callback_data='select_city')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "❌ Lütfen önce bir şehir seçin veya şehir adını yazın.\n"
                "Örnek: /sahur İstanbul",
                reply_markup=reply_markup
            )
            return
    
    # Şehir adını normalize et
    normalized_city = normalize_city_name(city)
    
    # Şehir verilerini kontrol et
    if normalized_city not in PRAYER_TIMES:
        available_cities = ", ".join([data['name'] for data in PRAYER_TIMES.values()])
        await update.message.reply_text(
            f"❌ '{city}' şehri bulunamadı.\n\n"
            f"Mevcut şehirler: {available_cities}\n\n"
            "Şehir seçmek için /sehir komutunu kullanabilirsiniz."
        )
        return
    
    # Şehri kaydet
    user_manager.set_user_city(user_id, normalized_city)
    
    # Vakitleri al
    city_data = PRAYER_TIMES[normalized_city]
    message = format_prayer_time_message(
        city_data['name'],
        'sahur',
        city_data['sahur']
    )
    
    # Hatırlatıcı butonu ekle
    keyboard = [
        [InlineKeyboardButton("⏰ Hatırlatıcı Ayarla", callback_data='reminder_sahur')],
        [InlineKeyboardButton("📅 Bugünün Vakitleri", callback_data='today')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(message, reply_markup=reply_markup)


async def city_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Şehir seçme komutu"""
    # Şehirleri alfabetik sırayla düzenle
    cities = sorted(PRAYER_TIMES.items(), key=lambda x: x[1]['name'])
    
    # Inline keyboard oluştur (her satırda 2 şehir)
    keyboard = []
    row = []
    for i, (city_key, city_data) in enumerate(cities):
        row.append(InlineKeyboardButton(
            city_data['name'],
            callback_data=f'setcity_{city_key}'
        ))
        if len(row) == 2 or i == len(cities) - 1:
            keyboard.append(row)
            row = []
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    user_id = update.effective_user.id
    current_city = user_manager.get_user_city(user_id)
    current_city_name = PRAYER_TIMES.get(current_city, {}).get('name', 'Seçilmedi')
    
    await update.message.reply_text(
        f"🏙 *Şehir Seçimi*\n\n"
        f"Mevcut şehir: *{current_city_name}*\n\n"
        "Lütfen şehrinizi seçin:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bugünün iftar ve sahur saatlerini göster"""
    user_id = update.effective_user.id
    city = user_manager.get_user_city(user_id)
    
    if not city:
        keyboard = [
            [InlineKeyboardButton("🏙 Şehir Seç", callback_data='select_city')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "❌ Lütfen önce bir şehir seçin.",
            reply_markup=reply_markup
        )
        return
    
    city_data = PRAYER_TIMES[city]
    
    # İftar için kalan süre
    iftar_hours, iftar_minutes = calculate_time_remaining(city_data['iftar'])
    if iftar_hours > 0:
        iftar_remaining = f"{iftar_hours} saat {iftar_minutes} dakika"
    else:
        iftar_remaining = f"{iftar_minutes} dakika"
    
    # Sahur için kalan süre
    sahur_hours, sahur_minutes = calculate_time_remaining(city_data['sahur'])
    if sahur_hours > 0:
        sahur_remaining = f"{sahur_hours} saat {sahur_minutes} dakika"
    else:
        sahur_remaining = f"{sahur_minutes} dakika"
    
    today = datetime.now().strftime('%d %B %Y')
    
    message = (
        f"📅 *{today}*\n"
        f"📍 *{city_data['name']}*\n\n"
        f"🌅 *Sahur Saati:* {city_data['sahur']}\n"
        f"⏰ Kalan Süre: {sahur_remaining}\n\n"
        f"🌙 *İftar Saati:* {city_data['iftar']}\n"
        f"⏰ Kalan Süre: {iftar_remaining}"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("⏰ İftar Hatırlatıcısı", callback_data='reminder_iftar'),
            InlineKeyboardButton("⏰ Sahur Hatırlatıcısı", callback_data='reminder_sahur')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)


async def reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hatırlatıcı ayarlama komutu"""
    keyboard = [
        [
            InlineKeyboardButton("🌙 İftar Hatırlatıcısı", callback_data='reminder_iftar'),
            InlineKeyboardButton("🌅 Sahur Hatırlatıcısı", callback_data='reminder_sahur')
        ],
        [InlineKeyboardButton("📋 Hatırlatıcılarımı Gör", callback_data='view_reminders')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "⏰ *Hatırlatıcı Ayarları*\n\n"
        "Hangi vakit için hatırlatıcı ayarlamak istersiniz?",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inline keyboard butonlarını işle"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == 'select_city':
        # Şehir seçme ekranını göster
        cities = sorted(PRAYER_TIMES.items(), key=lambda x: x[1]['name'])
        keyboard = []
        row = []
        for i, (city_key, city_data) in enumerate(cities):
            row.append(InlineKeyboardButton(
                city_data['name'],
                callback_data=f'setcity_{city_key}'
            ))
            if len(row) == 2 or i == len(cities) - 1:
                keyboard.append(row)
                row = []
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🏙 *Şehir Seçimi*\n\nLütfen şehrinizi seçin:",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    elif data.startswith('setcity_'):
        # Şehir ayarla
        city_key = data.replace('setcity_', '')
        user_manager.set_user_city(user_id, city_key)
        city_name = PRAYER_TIMES[city_key]['name']
        
        keyboard = [
            [InlineKeyboardButton("📅 Bugünün Vakitleri", callback_data='today')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ Şehriniz *{city_name}* olarak ayarlandı!\n\n"
            "Artık /iftar veya /sahur komutlarını kullanabilirsiniz.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    elif data == 'today':
        # Bugünün vakitlerini göster
        city = user_manager.get_user_city(user_id)
        if not city:
            await query.edit_message_text("❌ Lütfen önce bir şehir seçin.")
            return
        
        city_data = PRAYER_TIMES[city]
        
        iftar_hours, iftar_minutes = calculate_time_remaining(city_data['iftar'])
        if iftar_hours > 0:
            iftar_remaining = f"{iftar_hours} saat {iftar_minutes} dakika"
        else:
            iftar_remaining = f"{iftar_minutes} dakika"
        
        sahur_hours, sahur_minutes = calculate_time_remaining(city_data['sahur'])
        if sahur_hours > 0:
            sahur_remaining = f"{sahur_hours} saat {sahur_minutes} dakika"
        else:
            sahur_remaining = f"{sahur_minutes} dakika"
        
        today = datetime.now().strftime('%d %B %Y')
        
        message = (
            f"📅 *{today}*\n"
            f"📍 *{city_data['name']}*\n\n"
            f"🌅 *Sahur Saati:* {city_data['sahur']}\n"
            f"⏰ Kalan Süre: {sahur_remaining}\n\n"
            f"🌙 *İftar Saati:* {city_data['iftar']}\n"
            f"⏰ Kalan Süre: {iftar_remaining}"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("⏰ İftar Hatırlatıcısı", callback_data='reminder_iftar'),
                InlineKeyboardButton("⏰ Sahur Hatırlatıcısı", callback_data='reminder_sahur')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    
    elif data.startswith('reminder_'):
        # Hatırlatıcı ayarlama
        reminder_type = data.replace('reminder_', '')
        
        keyboard = [
            [InlineKeyboardButton("5 dakika önce", callback_data=f'setreminder_{reminder_type}_5')],
            [InlineKeyboardButton("10 dakika önce", callback_data=f'setreminder_{reminder_type}_10')],
            [InlineKeyboardButton("15 dakika önce", callback_data=f'setreminder_{reminder_type}_15')],
            [InlineKeyboardButton("30 dakika önce", callback_data=f'setreminder_{reminder_type}_30')],
            [InlineKeyboardButton("❌ Hatırlatıcıyı Kaldır", callback_data=f'removereminder_{reminder_type}')],
            [InlineKeyboardButton("◀️ Geri", callback_data='reminder_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        prayer_label = "İftar" if reminder_type == "iftar" else "Sahur"
        
        await query.edit_message_text(
            f"⏰ *{prayer_label} Hatırlatıcısı*\n\n"
            f"{prayer_label} vaktinden ne kadar önce hatırlatmak istersiniz?",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    elif data.startswith('setreminder_'):
        # Hatırlatıcı kaydet
        parts = data.split('_')
        reminder_type = parts[1]
        minutes = int(parts[2])
        
        user_manager.set_user_reminder(user_id, reminder_type, minutes)
        
        prayer_label = "İftar" if reminder_type == "iftar" else "Sahur"
        
        keyboard = [
            [InlineKeyboardButton("📋 Hatırlatıcılarımı Gör", callback_data='view_reminders')],
            [InlineKeyboardButton("◀️ Ana Menü", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ {prayer_label} hatırlatıcınız kaydedildi!\n\n"
            f"{prayer_label} vaktinden *{minutes} dakika önce* hatırlatılacaksınız.\n\n"
            "Not: Hatırlatıcılar şu an demo amaçlıdır. "
            "Gerçek uygulamada zamanlanmış bildirimler gönderilecektir.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    elif data.startswith('removereminder_'):
        # Hatırlatıcıyı kaldır
        reminder_type = data.replace('removereminder_', '')
        user_manager.remove_user_reminder(user_id, reminder_type)
        
        prayer_label = "İftar" if reminder_type == "iftar" else "Sahur"
        
        keyboard = [
            [InlineKeyboardButton("◀️ Ana Menü", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ {prayer_label} hatırlatıcınız kaldırıldı.",
            reply_markup=reply_markup
        )
    
    elif data == 'view_reminders':
        # Hatırlatıcıları göster
        reminders = user_manager.get_user_reminders(user_id)
        
        if not reminders:
            message = "📋 *Hatırlatıcılarım*\n\nHenüz hatırlatıcı ayarlamadınız."
        else:
            message = "📋 *Hatırlatıcılarım*\n\n"
            for reminder_type, minutes in reminders.items():
                prayer_label = "İftar" if reminder_type == "iftar" else "Sahur"
                message += f"• {prayer_label}: {minutes} dakika önce\n"
        
        keyboard = [
            [
                InlineKeyboardButton("⏰ İftar Hatırlatıcısı", callback_data='reminder_iftar'),
                InlineKeyboardButton("⏰ Sahur Hatırlatıcısı", callback_data='reminder_sahur')
            ],
            [InlineKeyboardButton("◀️ Ana Menü", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    
    elif data == 'reminder_menu':
        keyboard = [
            [
                InlineKeyboardButton("🌙 İftar Hatırlatıcısı", callback_data='reminder_iftar'),
                InlineKeyboardButton("🌅 Sahur Hatırlatıcısı", callback_data='reminder_sahur')
            ],
            [InlineKeyboardButton("📋 Hatırlatıcılarımı Gör", callback_data='view_reminders')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⏰ *Hatırlatıcı Ayarları*\n\n"
            "Hangi vakit için hatırlatıcı ayarlamak istersiniz?",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    elif data == 'main_menu':
        keyboard = [
            [InlineKeyboardButton("📅 Bugünün Vakitleri", callback_data='today')],
            [InlineKeyboardButton("🏙 Şehir Değiştir", callback_data='select_city')],
            [InlineKeyboardButton("⏰ Hatırlatıcılar", callback_data='reminder_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🌙 *Ana Menü*\n\nNe yapmak istersiniz?",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hata işleyici"""
    logger.error(f"Update {update} caused error {context.error}")


def main():
    """Ana fonksiyon"""
    # Bot token'ı
    TOKEN = "8387607009:AAG43nh85DHSEPXRvCSaZ0UNqDjWtPUVYwM"
    
    # Uygulama oluştur
    application = Application.builder().token(TOKEN).build()
    
    # Komut işleyicileri
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("yardim", help_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("iftar", iftar_command))
    application.add_handler(CommandHandler("sahur", sahur_command))
    application.add_handler(CommandHandler("sehir", city_command))
    application.add_handler(CommandHandler("bugun", today_command))
    application.add_handler(CommandHandler("hatirlatici", reminder_command))
    
    # Callback query işleyici
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Hata işleyici
    application.add_error_handler(error_handler)
    
    # Botu başlat
    logger.info("Bot başlatılıyor...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
