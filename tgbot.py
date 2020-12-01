# Python Libraries
from time import sleep
from telepotpro import Bot, glance
from telepotpro.exception import TelegramError, BotWasBlockedError
from threading import Thread
from pony.orm import db_session, select
from json import load as jsload

# Custom Modules
from modules import keyboards, helpers
from modules.database import TGUser
from modules.api import OISRankingAPI, NoEventRunning, TeamNameError

with open("settings.json") as settings_file:
    js_settings = jsload(settings_file)

bot = Bot(js_settings["tgToken"])
adminIds = js_settings["admins"]
api = OISRankingAPI()
roundStarted = False


@db_session
def sendRoundStarted():
    if not api.debug:
        users = select(user for user in TGUser if "eventStart" in user.news)[:]
    else:
        users = select(user for user in TGUser if ("eventStart" in user.news) and (user.chatId in adminIds))[:]
    for user in users:
        bot.sendMessage(user.chatId, "🔔 <b>Gara iniziata!</b>\n"
                                     "La classifica è attiva, puoi visualizzare le informazioni della tua squadra con /team.\n"
                                     "Buona fortuna!", parse_mode="HTML")


@db_session
def sendLeaderboardNews():
    # Send team rank changed
    teams = api.teams()
    users = select(user for user in TGUser if ("rankChanged" in user.news) and (user.teamName in teams))[:]
    for user in users:
        teamInfo = api.teamInfo(user.teamName)
        prevTeamInfo = api.teamInfo(user.teamName, oldData=True)
        newRank = teamInfo["rank"]
        oldRank = prevTeamInfo["rank"]
        gained = oldRank - newRank
        if gained > 0:
            bot.sendMessage(user.chatId, "📈 La squadra <b>{}</b> è salita di <b>{}</b> posizioni!\n"
                                         "📊 Rank attuale: {}".format(teamInfo["name"], gained, newRank), parse_mode="HTML")
        elif gained < 0:
            bot.sendMessage(user.chatId, "📉 La squadra <b>{}</b> è scesa di <b>{}</b> posizioni.\n"
                                         "📊 Rank attuale: {}".format(teamInfo["name"], -gained, newRank), parse_mode="HTML")

    # Send team points changed
    teams = api.teams()
    users = select(user for user in TGUser if ("pointsChanged" in user.news) and (user.teamName in teams))[:]
    for user in users:
        message = ""
        for quest in api.questions():
            score = api.getTeamPartial(user.teamName, quest)
            oldScore = api.getTeamPartial(user.teamName, quest, oldData=True)
            gained = score - oldScore
            if gained > 0:
                message += "🟢 <code>{}</code>: {}/100 (+{})\n".format(quest, score, gained)
            elif gained < 0:
                message += "🔴 <code>{}</code>: {}/100 (-{})\n".format(quest, score, -gained)
        if message != "":
            bot.sendMessage(user.chatId, "📊 <b>Nuovi punteggi!</b>\n\n" + message, parse_mode="HTML")


def runUpdates():
    global roundStarted
    try:
        api.refresh()
        # At this point, an event is running
        if not roundStarted:
            sendRoundStarted()
        else:
            sendLeaderboardNews()
        roundStarted = True
    except NoEventRunning:
        roundStarted = False


@db_session
def reply(msg):
    global api
    chatId = msg["chat"]["id"]
    name = msg["from"]["first_name"]
    if "text" in msg:
        text = msg["text"]
    else:
        bot.sendMessage(chatId, "🤨 Formato file non supportato. /help")
        return

    if not TGUser.exists(lambda u: u.chatId == chatId):
        TGUser(chatId=chatId)
    user = TGUser.get(chatId=chatId)

    if text == "/about":
        bot.sendMessage(chatId, "ℹ️ <b>Informazioni sul bot</b>\n"
                                "OISRankingBot è un bot creato e sviluppato da Filippo Pesavento, che ti permette "
                                "di visualizzare la classifica dei round OIS, di seguire una squadra automaticamente "
                                "e di ricevere una notifica quando inizia un nuovo round.\n"
                                "<i>Nota: Durante una gara, la classifica verrà aggiornata ogni 60 secondi.</i>\n\n"
                                "<b>Sviluppo:</b> <a href=\"https://t.me/pesaventofilippo\">Filippo Pesavento</a>\n"
                                "<b>Hosting:</b> Filippo Pesavento", parse_mode="HTML", disable_web_page_preview=True)

    elif text == "/help":
        bot.sendMessage(chatId, "Ciao, serve aiuto? 👋🏻\n"
                                "Posso visualizzare la classifica dei round attivi, e inviarti notifiche se ci sono novità sulla tua squadra.\n\n"
                                "<b>Lista dei comandi</b>:\n"
                                "- /start - Avvia il bot\n"
                                "- /team - Visualizza info sulla tua squadra\n"
                                "- /partials - Visualizza i punteggi singoli dei problemi\n"
                                "- /leaderboard - Visualizza la classifica completa\n"
                                "- /top - Visualizza top team\n"
                                "- /settings - Modifica le tue impostazioni\n"
                                "- /about - Informazioni sul bot\n"
                                "- /annulla - Annulla il comando attuale\n"
                                "- /support - Contatta lo staff (emergenze)\n\n"
                                "<b>Impostazioni</b>: con /settings puoi cambiare varie impostazioni, come quali notifiche ricevere e che squadra seguire."
                                "", parse_mode="HTML")

    elif user.status != "normal":
        if text == "/annulla":
            user.status = "normal"
            bot.sendMessage(chatId, "Comando annullato!")

        elif user.status == "calling_support":
            user.status = "normal"
            for a in adminIds:
                bot.sendMessage(a, "🆘 <b>Richiesta di aiuto</b>\n"
                                    "Da: <a href=\"tg://user?id={0}\">{1}</a>\n\n"
                                    "<i>Rispondi al messaggio per parlare con l'utente.</i>".format(chatId, name), parse_mode="HTML")
                if "reply_to_message" in msg:
                    bot.forwardMessage(a, chatId, msg["reply_to_message"]["message_id"])
                bot.forwardMessage(a, chatId, msg["message_id"], disable_notification=True)
            bot.sendMessage(chatId, "<i>Richiesta inviata.</i>\n"
                                    "Un admin ti risponderà il prima possibile.", parse_mode="HTML")

        elif user.status == "changing_team":
            user.status = "normal"
            user.teamName = text
            bot.sendMessage(chatId, "✅ La tua squadra è <b>{}</b>!".format(user.teamName), parse_mode="HTML")

    elif text.startswith("/broadcast ") and chatId in adminIds:
        bdText = text.split(" ", 1)[1]
        pendingUsers = select(u.chatId for u in TGUser)[:]
        userCount = len(pendingUsers)
        for u in pendingUsers:
            try:
                bot.sendMessage(u, bdText, parse_mode="HTML", disable_web_page_preview=True)
            except (TelegramError, BotWasBlockedError):
                userCount -= 1
        bot.sendMessage(chatId, "📢 Messaggio inviato correttamente a {0} utenti!".format(userCount))

    elif text == "/users" and chatId in adminIds:
        totalUsers = len(select(u for u in TGUser)[:])
        bot.sendMessage(chatId, "👤 Utenti totali: <b>{}</b>".format(totalUsers), parse_mode="HTML")

    elif text == "/debug" and chatId in adminIds:
        api = OISRankingAPI(_debug=True)
        bot.sendMessage(chatId, "Debug mode active!\n"
                                "Press /nodebug to disable.")

    elif text == "/nodebug" and chatId in adminIds:
        api = OISRankingAPI(_debug=False)
        bot.sendMessage(chatId, "Debug mode disabled!")

    elif "reply_to_message" in msg:
        if chatId in adminIds:
            try:
                userId = msg["reply_to_message"]["forward_from"]["id"]
                bot.sendMessage(userId, "💬 <b>Risposta dello staff</b>\n"
                                        "{0}".format(text), parse_mode="HTML")
                bot.sendMessage(chatId, "Risposta inviata!")
            except Exception:
                bot.sendMessage(chatId, "Errore nell'invio.\n"
                                        "L'utente ha un account privato?")
        else:
            bot.sendMessage(chatId, "Scrivi /support per parlare con lo staff.")

    elif text == "/annulla":
        bot.sendMessage(chatId, "😴 Nessun comando da annullare!")

    elif text == "/start":
        if roundStarted:
            bot.sendMessage(chatId, "Bentornato, <b>{0}</b>!\n"
                                    "🟢 <i>La gara è iniziata! Cosa aspetti?</i>\n\n"
                                    "Cosa posso fare per te? 😊".format(name), parse_mode="HTML")
        else:
            bot.sendMessage(chatId, "Bentornato, <b>{0}</b>!\n"
                                    "🔴 <i>Attualmente nessuna competizione è in corso.</i>\n\n"
                                    "Cosa posso fare per te? 😊".format(name), parse_mode="HTML")

    elif text == "/team":
        if user.teamName:
            if roundStarted:
                try:
                    teamInfo = api.teamInfo(user.teamName)
                except TeamNameError:
                    bot.sendMessage(chatId, "⚠️ La squadra che hai inserito non è presente nella classifica!\n"
                                            "Premi /settings per cambiare il nome della squadra.", parse_mode="HTML")
                    return
                teams = api.teams()
                bot.sendMessage(chatId, "👥 Team: <b>{}</b>\n\n"
                                        "📊 Rank: <b>{}°</b> / {}\n"
                                        "📈 Total Score: <b>{}</b> / {}pts.\n\n"
                                        "<i>Usa </i>/partials<i> per vedere i punteggi singoli dei quesiti.</i>"
                                        "".format(teamInfo["name"], teamInfo["rank"], len(teams),
                                                  teamInfo["totalScore"], len(api.questions())*100), parse_mode="HTML")
            else:
                bot.sendMessage(chatId, "👥 La tua squadra è <b>{}</b>.\n"
                                        "Posso visualizzare più informazioni quando è attiva una gara.".format(user.teamName),
                                parse_mode="HTML")
        else:
            sent = bot.sendMessage(chatId, "Non hai impostato la tua squadra!\n"
                                           "Vuoi impostarla ora?", parse_mode="HTML")
            bot.editMessageReplyMarkup((chatId, sent["message_id"]), reply_markup=keyboards.settings_newteam())

    elif text == "/partials":
        if user.teamName:
            if roundStarted:
                questList = api.questions()
                try:
                    teamInfo = api.teamInfo(user.teamName)
                except TeamNameError:
                    bot.sendMessage(chatId, "⚠️ La squadra che hai inserito non è presente nella classifica!\n"
                                            "Premi /settings per cambiare il nome della squadra.", parse_mode="HTML")
                    return
                longestName = max(questList, key=len)
                questPoints = teamInfo["partialScores"]
                message = "👥 Team: <b>{}</b>\n\n".format(user.teamName)
                for quest, score in zip(questList, questPoints):
                    padding = " " * (len(longestName) - len(quest))
                    message += "{}<code> {}: {}</code><b>{}</b> pts.\n".format(helpers.getStatIcon(score), quest, padding, score)
                message += "\n📈 Total: <b>{}</b> / {}pts.".format(teamInfo["totalScore"], len(questPoints)*100)
                bot.sendMessage(chatId, message, parse_mode="HTML")
            else:
                bot.sendMessage(chatId, "👥 La tua squadra è <b>{}</b>.\n"
                                        "Posso visualizzare più informazioni quando è attiva una gara.".format(user.teamName),
                                parse_mode="HTML")
        else:
            sent = bot.sendMessage(chatId, "Non hai impostato la tua squadra!\n"
                                           "Vuoi impostarla ora?", parse_mode="HTML")
            bot.editMessageReplyMarkup((chatId, sent["message_id"]), reply_markup=keyboards.settings_newteam())

    elif text == "/leaderboard":
        if roundStarted:
            teams = api.teams()
            message = "🏆 <b>Leaderboard</b>\n"
            for pos in range(10):
                teamInfo = api.teamInfo(teams[pos])
                message += "\n{} <b>{}</b> ({} pts.)".format(helpers.getRankIcon(teamInfo["rank"]), teamInfo["name"], teamInfo["totalScore"])
            bot.sendMessage(chatId, message, parse_mode="HTML", reply_markup=keyboards.leaderboard(1, len(teams)))
        else:
            bot.sendMessage(chatId, "Nessuna gara è attualmente in corso!")

    elif text == "/top":
        if roundStarted:
            teams = api.teams()
            message = "🏆 <b>Top Teams</b>\n"
            for pos in range(3):
                teamInfo = api.teamInfo(teams[pos])
                message += "\n{} <b>{}</b> ({} pts.)".format(helpers.getRankIcon(teamInfo["rank"]), teamInfo["name"], teamInfo["totalScore"])
            if user.teamName:
                try:
                    teamInfo = api.teamInfo(user.teamName)
                    message += "\n\n{} <b>{}</b> ({} pts.)".format(helpers.getRankIcon(teamInfo["rank"]), teamInfo["name"],
                                                                 teamInfo["totalScore"])
                except TeamNameError:
                    pass
            bot.sendMessage(chatId, message, parse_mode="HTML")
        else:
            bot.sendMessage(chatId, "Nessuna gara è attualmente in corso!")

    elif text == "/settings":
        sent = bot.sendMessage(chatId, "🛠 <b>Impostazioni</b>\n"
                                        "Ecco le impostazioni del bot. Cosa vuoi modificare?", parse_mode="HTML", reply_markup=None)
        bot.editMessageReplyMarkup((chatId, sent["message_id"]), keyboards.settings_menu())

    elif (text == "/support") or (text == "/start support"):
        user.status = "calling_support"
        bot.sendMessage(chatId, "🆘 <b>Richiesta di supporto</b>\n"
                                "Se hai qualche problema che non riesci a risolvere, scrivi qui un messaggio, e un admin "
                                "ti contatterà il prima possibile.\n\n"
                                "<i>Per annullare, premi</i> /annulla.", parse_mode="HTML")

    else:
        bot.sendMessage(chatId, "Non ho capito...\n"
                                "Serve aiuto? Premi /help")


@db_session
def button_press(msg):
    chatId, query_data = glance(msg, flavor="callback_query")[1:3]
    query_split = query_data.split("#", 1)
    msgId = int(msg["message"]["message_id"])
    button = str(query_split[0])
    data = str(query_split[1]) if len(query_split) > 1 else None
    user = TGUser.get(chatId=chatId)

    def editNotifSelection():
        bot.editMessageText((chatId, msgId), "📲 <b>Gestione Notifiche</b>\n\n"
                                             "⏰ Inizio gara: {}\n"
                                             "📊 Nuova posizione in classifica: {}\n"
                                                  "📈 Punteggio modificato: {}\n\n"
                                                  "Quali notifiche vuoi ricevere? (Clicca per cambiare)"
                                                  "".format(
                                                  "🔔 Attivo" if "eventStart" in user.news else "🔕 Disattivo",
                                                  "🔔 Attivo" if "rankChanged" in user.news else "🔕 Disattivo",
                                                  "🔔 Attivo" if "pointsChanged" in user.news else "🔕 Disattivo"),
                            parse_mode="HTML", reply_markup=keyboards.settings_selectnews())

    if button == "settings_main":
        bot.editMessageText((chatId, msgId), "🛠 <b>Impostazioni</b>\n"
                                                    "Ecco le impostazioni del bot. Cosa vuoi modificare?",
                                                     parse_mode="HTML", reply_markup=keyboards.settings_menu())

    elif button == "settings_team":
        if user.teamName:
            bot.editMessageText((chatId, msgId), "👥 <b>Selezione Team</b>\n"
                                                      "La tua squadra attuale è <b>{}</b>.\n\n"
                                                      "Vuoi cambiarlo?".format(user.teamName),
                                parse_mode="HTML", reply_markup=keyboards.settings_team())
        else:
            bot.editMessageText((chatId, msgId), "👥 <b>Selezione Team</b>\n"
                                                      "Attualmente non hai impostato nessuna squadra.\n\n"
                                                      "Vuoi farlo?",
                                parse_mode="HTML", reply_markup=keyboards.settings_newteam())

    elif button == "settings_news":
        editNotifSelection()

    elif button.startswith("news_"):
        newsId = button.replace("news_", "")
        if newsId in user.news:
            user.news.remove(newsId)
        else:
            user.news.append(newsId)
        editNotifSelection()

    elif button == "settings_changeTeam":
        user.status = "changing_team"
        bot.editMessageText((chatId, msgId), "Scrivi il nome della tua squadra.\n"
                                "<b>Attenzione!</b> Il nome della squadra è case-sensitive, quindi assicurati di "
                                "inserirlo correttamente.\n\n"
                                "<i>Per annullare, premi</i> /annulla.", parse_mode="HTML", reply_markup=None)

    elif button == "settings_removeTeam":
        user.teamName = ""
        bot.editMessageText((chatId, msgId), "❌ Il nome della squadra è stato rimosso.", reply_markup=None)

    elif button == "leaderboard_page":
        page = int(data)
        if roundStarted:
            teams = api.teams()
            message = "🏆 <b>Leaderboard</b>\n"
            for pos in range(10):
                pos += 10*(page-1)
                teamInfo = api.teamInfo(teams[pos])
                message += "\n{} <b>{}</b> ({} pts.)".format(helpers.getRankIcon(teamInfo["rank"]), teamInfo["name"], teamInfo["totalScore"])
            bot.editMessageText((chatId, msgId), message, parse_mode="HTML", reply_markup=keyboards.leaderboard(page, len(teams)))
        else:
            bot.editMessageText((chatId, msgId), "Nessuna gara è attualmente in corso!",
                                parse_mode="HTML", reply_markup=None)


def accept_message(msg):
    Thread(target=reply, args=[msg]).start()

def accept_button(msg):
    Thread(target=button_press, args=[msg]).start()

bot.message_loop(callback={'chat': accept_message, 'callback_query': accept_button})

while True:
    runUpdates()
    sleep(60)
