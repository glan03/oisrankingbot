from telepotpro.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton
from math import ceil


def settings_menu():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="👥 Team", callback_data="settings_team")
    ], [
        InlineKeyboardButton(text="📲 Notifiche", callback_data="settings_news")
    ]])


def settings_team():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔧 Cambia", callback_data="settings_changeTeam"),
        InlineKeyboardButton(text="❌ Rimuovi", callback_data="settings_removeTeam")
    ]])


def settings_newteam():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Aggiungi", callback_data="settings_changeTeam")
    ]])


def settings_selectnews():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⏰ Gara iniziata", callback_data="news_eventStart")
    ], [
        InlineKeyboardButton(text="📊 Classifica", callback_data="news_rankChanged"),
        InlineKeyboardButton(text="📈 Punti", callback_data="news_pointsChanged")
    ]])


def leaderboard(page: int, maxTeams: int):
    maxPages = ceil(maxTeams/10)
    if page == 1:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Next ▶️", callback_data="leaderboard_page#{}".format(page+1))
        ]])
    elif page == maxPages:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="◀️ Back", callback_data="leaderboard_page#{}".format(page-1))
        ]])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="◀️ Back", callback_data="leaderboard_page#{}".format(page-1)),
            InlineKeyboardButton(text="Next ▶️", callback_data="leaderboard_page#{}".format(page+1))
        ]])
