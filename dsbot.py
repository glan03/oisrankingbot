# Python Libraries
import discord
from discord.ext import commands, tasks
from pony.orm import db_session, select
from json import load as jsload

# Custom Modules
from modules import helpers
from modules.database import DSChat
from modules.api import OISRankingAPI, NoEventRunning, TeamNameError

with open("settings.json") as settings_file:
    js_settings = jsload(settings_file)

bot = commands.Bot(command_prefix='!')
bot.remove_command("help")
adminIds = js_settings["discord"]["admins"]
api = OISRankingAPI()
roundStarted = False

def async_db_session(fn):
    async def callback(*args, **kwargs):
        with db_session():
            return await fn(*args, **kwargs)
    return callback

def parseHTML(text: str):
    text = text.replace("<b>", "**").replace("</b>", "**")
    text = text.replace("<i>", "_").replace("</i>", "_")
    text = text.replace("<u>", "__").replace("</u>", "__")
    text = text.replace("<s>", "~~").replace("</s>", "~~")
    text = text.replace("<code>", "`").replace("</code>", "`")
    return text

@db_session
def parseContext(ctx):
    server = ctx.guild
    channel = ctx.channel
    user = ctx.author
    message = ctx.message

    if not DSChat.exists(lambda c: c.chatId == str(channel.id)):
        DSChat(chatId=str(channel.id))
    dbChatId = DSChat.get(chatId=str(channel.id)).id

    return server, channel, user, message, dbChatId

@async_db_session
async def sendRoundStarted():
    if not api.debug:
        channels = select(ch for ch in DSChat if "eventStart" in ch.news)[:]
        for channel in channels:
            chat = bot.get_channel(int(channel.chatId))
            await chat.send(parseHTML("🔔 <b>Gara iniziata!</b>\n"
                                      "La classifica è attiva, puoi visualizzare le informazioni della tua squadra con !team.\n"
                                      "Buona fortuna!"))

@async_db_session
async def sendLeaderboardNews():
    # Send team rank changed
    teams = api.teams()
    channels = select(ch for ch in DSChat if ("rankChanged" in ch.news) and (ch.teamName in teams))[:]
    for channel in channels:
        teamInfo = api.teamInfo(channel.teamName)
        prevTeamInfo = api.teamInfo(channel.teamName, oldData=True)
        newRank = teamInfo["rank"]
        oldRank = prevTeamInfo["rank"]
        gained = oldRank - newRank
        chat = bot.get_channel(int(channel.chatId))
        if gained > 0:
            await chat.send(parseHTML("📈 La squadra <b>{}</b> è salita di <b>{}</b> posizioni!\n"
                                      "📊 Rank attuale: {}".format(teamInfo["name"], gained, newRank)))
        elif gained < 0:
            await chat.send(parseHTML("📉 La squadra <b>{}</b> è scesa di <b>{}</b> posizioni.\n"
                                      "📊 Rank attuale: {}".format(teamInfo["name"], -gained, newRank)))

    # Send team points changed
    channels = select(ch for ch in DSChat if ("pointsChanged" in ch.news) and (ch.teamName in teams))[:]
    for channel in channels:
        message = ""
        for quest in api.questions():
            score = api.getTeamPartial(channel.teamName, quest)
            oldScore = api.getTeamPartial(channel.teamName, quest, oldData=True)
            gained = score - oldScore
            if gained > 0:
                message += "🟢 <code>{}:</code> {}/100 (+{})\n".format(quest, score, gained)
            elif gained < 0:
                message += "🔴 <code>{}:</code> {}/100 (-{})\n".format(quest, score, -gained)
        if message != "":
            chat = bot.get_channel(int(channel.chatId))
            await chat.send(parseHTML("📊 <b>Nuovi punteggi!</b>\n\n" + message))

@tasks.loop(minutes=1.0)
async def runUpdates():
    global roundStarted
    try:
        api.refresh()
        # At this point, an event is running
        if not roundStarted:
            await sendRoundStarted()
        else:
            await sendLeaderboardNews()
        roundStarted = True
    except NoEventRunning:
        roundStarted = False

@bot.event
async def on_ready():
    await bot.change_presence(
        activity=discord.Game(name="Type !help"),
        status=discord.Status.online
    )

@bot.event
async def on_command_error(ctx, error):
    await ctx.send(parseHTML("<code>An internal error occurred while running this command.</code>"))
    print(error)


## COMMANDS ##

@bot.command(name="start")
async def start(ctx):
    server, channel, user, message, dbChatId = parseContext(ctx)
    statusString = "🟢 <i>La gara è iniziata! Cosa aspetti?</i>" if roundStarted else "🔴 <i>Attualmente nessuna competizione è in corso.</i>"
    await channel.send(parseHTML("Bentornato, <b>{}</b>!\n"
                                 "{}\n\n"
                                 "Cosa posso fare per te? 😊".format(user.display_name, statusString)))

@bot.command(name="about")
@async_db_session
async def about(ctx):
    server, channel, user, message, dbChatId = parseContext(ctx)
    dbChat = DSChat.get(id=dbChatId)
    if dbChat.viewEmbed:
        embedVar = discord.Embed(title="ℹ️ Informazioni sul bot", color=0x277ecd)
        embedVar.add_field(name="Info", value="OISRankingBot è un bot creato e sviluppato da Filippo Pesavento, che ti permette "
                                              "di visualizzare la classifica dei round OIS, di seguire una squadra automaticamente "
                                              "e di ricevere una notifica quando inizia un nuovo round.", inline=False)
        embedVar.add_field(name="Nota", value="Durante una gara, la classifica verrà aggiornata ogni 60 secondi.", inline=False)
        embedVar.add_field(name="Sviluppo & Hosting", value="[Filippo Pesavento](https://pesaventofilippo.com)", inline=False)
        await channel.send(embed=embedVar)
    else:
        await channel.send(parseHTML("ℹ️ <b>Informazioni sul bot</b>\n"
                                     "OISRankingBot è un bot creato e sviluppato da Filippo Pesavento, che ti permette "
                                     "di visualizzare la classifica dei round OIS, di seguire una squadra automaticamente "
                                     "e di ricevere una notifica quando inizia un nuovo round.\n"
                                     "<i>Nota: Durante una gara, la classifica verrà aggiornata ogni 60 secondi.</i>\n\n"
                                     "<b>Sviluppo:</b> Filippo Pesavento\n"
                                     "<b>Hosting:</b> Filippo Pesavento"))

@bot.command(name="help")
@async_db_session
async def help(ctx):
    server, channel, user, message, dbChatId = parseContext(ctx)
    dbChat = DSChat.get(id=dbChatId)
    if dbChat.viewEmbed:
        embedVar = discord.Embed(title="Help Menu",
                                 description="Ciao, serve aiuto? 👋🏻\n"
                                             "Posso visualizzare la classifica dei round attivi, e inviarti notifiche se ci "
                                             "sono novità sulla tua squadra.", color=0x277ecd)
        embedVar.add_field(name="Comandi",
                           value="!start\n!help\n!team\n!partials\n!leaderboard\n!top\n!settings\n!about", inline=True)
        embedVar.add_field(name="Uso",
                           value="Avvia il bot\n"
                                 "Visualizza questo messaggio\n"
                                 "Visualizza info sulla tua squadra\n"
                                 "Visualizza i punteggi singoli dei problemi\n"
                                 "Visualizza la classifica completa\n"
                                 "Visualizza top team\n"
                                 "Modifica le tue impostazioni\n"
                                 "Informazioni sul bot", inline=True)
        embedVar.add_field(name="Impostazioni",
                           value="Con !settings puoi cambiare varie impostazioni, come quali notifiche ricevere e che squadra seguire.", inline=False)
        await channel.send(embed=embedVar)
    else:
        await channel.send(parseHTML("Ciao, serve aiuto? 👋🏻\n"
                                     "Posso visualizzare la classifica dei round attivi, e inviarti notifiche se ci "
                                     "sono novità sulla tua squadra.\n\n"
                                     "<b>Lista dei comandi</b>:\n"
                                     "- !start - Avvia il bot\n"
                                     "- !help - Visualizza questo messaggio\n"
                                     "- !team - Visualizza info sulla tua squadra\n"
                                     "- !partials - Visualizza i punteggi singoli dei problemi\n"
                                     "- !leaderboard - Visualizza la classifica completa\n"
                                     "- !top - Visualizza top team\n"
                                     "- !settings - Modifica le tue impostazioni\n"
                                     "- !about - Informazioni sul bot\n\n"
                                     "<b>Impostazioni</b>: con !settings puoi cambiare varie impostazioni, come quali notifiche ricevere e che squadra seguire."))

@bot.command(name="settings")
@async_db_session
async def settings(ctx):
    server, channel, user, message, dbChatId = parseContext(ctx)
    dbChat = DSChat.get(id=dbChatId)
    if dbChat.viewEmbed:
        embedVar = discord.Embed(title="🛠 Impostazioni",
                                 description="Per adesso, usa questi comandi per cambiare le impostazioni di questa chat.",
                                 color=0x277ecd)
        embedVar.add_field(name="Comandi",
                           value="!news\n!addnews <start|rank|points>\n\n!delnews <start|rank|points>\n\n!setteam <nome>\n"
                                 "!delteam\n!toggleview",
                           inline=True)
        embedVar.add_field(name="Uso",
                           value="Visualizza notifiche attive\n"
                                 "Attiva notifiche per: inizio gara, cambio classifica o cambio punteggi\n"
                                 "Rimuovi notifiche per: inizio gara, cambio classifica o cambio punteggi\n"
                                 "Imposta la tua squadra a 'nome'*\n"
                                 "Rimuovi la squadra associata a questa chat\n"
                                 "[Beta] Cambia tra visualizzazione normale/embed",
                           inline=True)
        embedVar.add_field(name="* Attenzione",
                           value="Il nome della squadra è case-sensitive e space-sensitive.",
                           inline=False)
        await channel.send(embed=embedVar)
    else:
        await channel.send(parseHTML("🛠 Impostazioni\n"
                                     "Per adesso, usa questi comandi per cambiare le impostazioni di questa chat.\n\n"
                                     "<b>Lista dei comandi</b>:\n"
                                     "- !news - Visualizza notifiche attive\n"
                                     "- !addnews <start|rank|points> - Attiva notifiche per: inizio gara, cambio classifica o cambio punteggi\n"
                                     "- !delnews <start|rank|points> - Rimuovi notifiche per: inizio gara, cambio classifica o cambio punteggi\n"
                                     "- !setteam <nome> - Imposta la tua squadra a 'nome'*\n"
                                     "- !delteam - Rimuovi la squadra associata a questa chat\n"
                                     "- !toggleview - [Beta] Cambia tra visualizzazione normale/embed\n\n"
                                     "* <b>Attenzione: il nome della squadra è case-sensitive.</b>"))

@bot.command(name="debug")
async def debug(ctx, *, active: bool=True):
    server, channel, user, message, dbChatId = parseContext(ctx)
    if str(user.id) in adminIds:
        api.debug = active
        await channel.send(parseHTML("✅ Modalità debug {}!".format("attivata" if active else "disattivata")))

@bot.command(name="forcerefresh")
async def forcerefresh(ctx):
    server, channel, user, message, dbChatId = parseContext(ctx)
    if str(user.id) in adminIds:
        try:
            runUpdates.start()
            await channel.send(parseHTML("✅ Dati classifica aggiornati!"))
        except RuntimeError:
            await channel.send(parseHTML("❌ La classifica si stava già aggiornando."))

@bot.command(name="broadcast")
@async_db_session
async def broadcast(ctx):
    server, channel, user, message, dbChatId = parseContext(ctx)
    text = message.content.split(" ", 1)[1]
    if str(user.id) in adminIds:
        channels = select(ch for ch in DSChat)[:]
        for ch in channels:
            chat = bot.get_channel(int(ch.chatId))
            await chat.send(parseHTML("📢 <b>Annuncio globale</b>\n\n{}".format(text)))

@bot.command(name="team")
@async_db_session
async def team(ctx):
    server, channel, user, message, dbChatId = parseContext(ctx)
    dbChat = DSChat.get(id=dbChatId)
    if dbChat.teamName:
        if roundStarted:
            try:
                teamInfo = api.teamInfo(dbChat.teamName)
            except TeamNameError:
                await channel.send(parseHTML("⚠️ La squadra che hai inserito non è presente nella classifica!\n"
                                             "Premi !settings per cambiare il nome della squadra."))
                return
            if dbChat.viewEmbed:
                embedVar = discord.Embed(title="👥 Info Team",
                                         color=0x277ecd)
                embedVar.add_field(name="Info",
                                   value="👥 Team:\n📊 Rank:\n📈 Total Score:", inline=True)
                embedVar.add_field(name="Value",
                                   value="{}\n{}° / {}\n{} / {}pts.".format(teamInfo["name"], teamInfo["rank"], len(api.teams()),
                                                       teamInfo["totalScore"], len(api.questions()) * 100), inline=True)
                embedVar.add_field(name="Punteggi problemi",
                                   value="Usa !partials per vedere i punteggi singoli dei quesiti.", inline=False)
                await channel.send(embed=embedVar)
            else:
                await channel.send(parseHTML("👥 Team: <b>{}</b>\n\n"
                                             "📊 Rank: <b>{}°</b> / {}\n"
                                             "📈 Total Score: <b>{}</b> / {}pts.\n\n"
                                             "<i>Usa </i>!partials<i> per vedere i punteggi singoli dei quesiti.</i>"
                                             "".format(teamInfo["name"], teamInfo["rank"], len(api.teams()),
                                                       teamInfo["totalScore"], len(api.questions()) * 100)))
        else:
            if dbChat.viewEmbed:
                embedVar = discord.Embed(title="👥 La tua squadra è {}.".format(dbChat.teamName),
                                         description="Posso visualizzare più informazioni quando è attiva una gara.",
                                         color=0x277ecd)
                await channel.send(embed=embedVar)
            else:
                await channel.send(parseHTML("👥 La tua squadra è <b>{}</b>.\n"
                                             "Posso visualizzare più informazioni quando è attiva una gara."
                                             "".format(dbChat.teamName)))
    else:
        await channel.send(parseHTML("Non hai impostato la tua squadra! Usa !settings per farlo."))

@bot.command(name="partials")
@async_db_session
async def partials(ctx):
    server, channel, user, message, dbChatId = parseContext(ctx)
    dbChat = DSChat.get(id=dbChatId)
    if dbChat.teamName:
        if roundStarted:
            questList = api.questions()
            try:
                teamInfo = api.teamInfo(dbChat.teamName)
            except TeamNameError:
                await channel.send(parseHTML("⚠️ La squadra che hai inserito non è presente nella classifica!\n"
                                             "Premi !settings per cambiare il nome della squadra."))
                return
            longestName = max(questList, key=len)
            questPoints = teamInfo["partialScores"]
            if dbChat.viewEmbed:
                leftColumn = ""
                rightColumn = ""
                embedVar = discord.Embed(title="👥 Team: {}".format(dbChat.teamName),
                                         color=0x277ecd)
                for quest, score in zip(questList, questPoints):
                    leftColumn += "{} {}:\n".format(helpers.getStatIcon(score), quest)
                    rightColumn += "{} pts.\n".format(score)
                leftColumn += "\n📈 Total:"
                rightColumn += "\n{} / {}pts.".format(teamInfo["totalScore"], len(questPoints) * 100)
                embedVar.add_field(name="Problemi", value=leftColumn, inline=True)
                embedVar.add_field(name="Punteggio", value=rightColumn, inline=True)
                await channel.send(embed=embedVar)
            else:
                message = "👥 Team: <b>{}</b>\n\n".format(dbChat.teamName)
                for quest, score in zip(questList, questPoints):
                    padding = " " * (len(longestName) - len(quest))
                    message += "{}<code> {}: {}</code><b>{}</b> pts.\n".format(helpers.getStatIcon(score), quest, padding, score)
                message += "\n📈 Total: <b>{}</b> / {}pts.".format(teamInfo["totalScore"], len(questPoints) * 100)
                await channel.send(parseHTML(message))
        else:
            if dbChat.viewEmbed:
                embedVar = discord.Embed(title="👥 La tua squadra è {}.".format(dbChat.teamName),
                                         description="Posso visualizzare più informazioni quando è attiva una gara.",
                                         color=0x277ecd)
                await channel.send(embed=embedVar)
            else:
                await channel.send(parseHTML("👥 La tua squadra è <b>{}</b>.\n"
                                             "Posso visualizzare più informazioni quando è attiva una gara."
                                             "".format(dbChat.teamName)))
    else:
        await channel.send(parseHTML("Non hai impostato la tua squadra! Usa !settings per farlo."))

@bot.command(name="leaderboard")
@async_db_session
async def leaderboard(ctx):
    server, channel, user, message, dbChatId = parseContext(ctx)
    dbChat = DSChat.get(id=dbChatId)
    if roundStarted:
        teams = api.teams()
        if dbChat.viewEmbed:
            embedVar = discord.Embed(title="🏆 Leaderboard", color=0x277ecd)
            leftColumn = ""
            rightColumn = ""
            for pos in range(10):
                teamInfo = api.teamInfo(teams[pos])
                leftColumn += "{} {}\n".format(helpers.getRankIcon(teamInfo["rank"]), teamInfo["name"])
                rightColumn += "{} pts.\n".format(teamInfo["totalScore"])
            embedVar.add_field(name="Team", value=leftColumn, inline=True)
            embedVar.add_field(name="Punteggio", value=rightColumn, inline=True)
            await channel.send(embed=embedVar)
        else:
            message = "🏆 <b>Leaderboard</b>\n"
            for pos in range(10):
                teamInfo = api.teamInfo(teams[pos])
                message += "\n{} <b>{}</b> ({} pts.)".format(helpers.getRankIcon(teamInfo["rank"]), teamInfo["name"],
                                                             teamInfo["totalScore"])
            await channel.send(parseHTML(message))
    else:
        await channel.send(parseHTML("Nessuna gara è attualmente in corso!"))

@bot.command(name="top")
@async_db_session
async def top(ctx):
    server, channel, user, message, dbChatId = parseContext(ctx)
    dbChat = DSChat.get(id=dbChatId)
    if roundStarted:
        teams = api.teams()
        if dbChat.viewEmbed:
            embedVar = discord.Embed(title="🏆 Top Teams", color=0x277ecd)
            leftColumn = ""
            rightColumn = ""
            for pos in range(3):
                teamInfo = api.teamInfo(teams[pos])
                leftColumn += "{} {}\n".format(helpers.getRankIcon(teamInfo["rank"]), teamInfo["name"])
                rightColumn += "{} pts.\n".format(teamInfo["totalScore"])
            if dbChat.teamName:
                try:
                    teamInfo = api.teamInfo(dbChat.teamName)
                    leftColumn += "\n{} {}".format(helpers.getRankIcon(teamInfo["rank"]), teamInfo["name"])
                    rightColumn += "\n{} pts.".format(teamInfo["totalScore"])
                except TeamNameError:
                    pass
            embedVar.add_field(name="Team", value=leftColumn, inline=True)
            embedVar.add_field(name="Punteggio", value=rightColumn, inline=True)
            await channel.send(embed=embedVar)
        else:
            message = "🏆 <b>Top Teams</b>\n"
            for pos in range(3):
                teamInfo = api.teamInfo(teams[pos])
                message += "\n{} <b>{}</b> ({} pts.)".format(helpers.getRankIcon(teamInfo["rank"]), teamInfo["name"], teamInfo["totalScore"])
            if dbChat.teamName:
                try:
                    teamInfo = api.teamInfo(dbChat.teamName)
                    message += "\n\n{} <b>{}</b> ({} pts.)".format(helpers.getRankIcon(teamInfo["rank"]), teamInfo["name"], teamInfo["totalScore"])
                except TeamNameError:
                    pass
            await channel.send(parseHTML(message))
    else:
        await channel.send(parseHTML("Nessuna gara è attualmente in corso!"))

@bot.command(name="news")
@async_db_session
async def news(ctx):
    server, channel, user, message, dbChatId = parseContext(ctx)
    dbChat = DSChat.get(id=dbChatId)
    if dbChat.viewEmbed:
        embedVar = discord.Embed(title="📲 Notifiche attive", color=0x277ecd)
        embedVar.add_field(name="Notifica", value="⏰ Inizio gara:\n"
                                                  "📊 Nuova posizione in classifica:\n"
                                                  "📈 Punteggio modificato:", inline=True)
        embedVar.add_field(name="Attivo?", value="{}\n{}\n{}".format(
                               "🔔 Attivo" if "eventStart" in dbChat.news else "🔕 Disattivo",
                               "🔔 Attivo" if "rankChanged" in dbChat.news else "🔕 Disattivo",
                               "🔔 Attivo" if "pointsChanged" in dbChat.news else "🔕 Disattivo"),
                           inline=True)
        await channel.send(embed=embedVar)
    else:
        await channel.send(parseHTML("📲 <b>Notifiche attive</b>\n\n"
                                     "⏰ Inizio gara: {}\n"
                                     "📊 Nuova posizione in classifica: {}\n"
                                     "📈 Punteggio modificato: {}".format(
            "🔔 Attivo" if "eventStart" in dbChat.news else "🔕 Disattivo",
            "🔔 Attivo" if "rankChanged" in dbChat.news else "🔕 Disattivo",
            "🔔 Attivo" if "pointsChanged" in dbChat.news else "🔕 Disattivo"
        )))

@bot.command(name="addnews")
@async_db_session
async def addnews(ctx):
    server, channel, user, message, dbChatId = parseContext(ctx)
    text = message.content.split(" ", 1)
    if len(text) > 1:
        name = text[1]
        dbChat = DSChat.get(id=dbChatId)
        if name == "start":
            if "eventStart" not in dbChat.news:
                dbChat.news.append("eventStart")
            await channel.send(parseHTML("🔔 Notifiche di inizio gara attivate!"))
        elif name == "rank":
            if "rankChanged" not in dbChat.news:
                dbChat.news.append("rankChanged")
            await channel.send(parseHTML("🔔 Notifiche per nuova posizione in classifica attivate!"))
        elif name == "points":
            if "pointsChanged" not in dbChat.news:
                dbChat.news.append("pointsChanged")
            await channel.send(parseHTML("🔔 Notifiche per nuovo punteggio attivate!"))
        else:
            await channel.send(parseHTML("Errore: scegli una notifica tra start, rank o points."))
    else:
        await channel.send(parseHTML("Errore: scegli una notifica tra start, rank o points."))

@bot.command(name="delnews")
@async_db_session
async def delnews(ctx):
    server, channel, user, message, dbChatId = parseContext(ctx)
    text = message.content.split(" ", 1)
    if len(text) > 1:
        name = text[1]
        dbChat = DSChat.get(id=dbChatId)
        if name == "start":
            if "eventStart" in dbChat.news:
                dbChat.news.remove("eventStart")
            await channel.send(parseHTML("🔕 Notifiche di inizio gara disattivate."))
        elif name == "rank":
            if "rankChanged" in dbChat.news:
                dbChat.news.remove("rankChanged")
            await channel.send(parseHTML("🔕 Notifiche per nuova posizione in classifica disattivate."))
        elif name == "points":
            if "pointsChanged" in dbChat.news:
                dbChat.news.remove("pointsChanged")
            await channel.send(parseHTML("🔕 Notifiche per nuovo punteggio disattivate."))
        else:
            await channel.send(parseHTML("Errore: scegli una notifica tra start, rank o points."))
    else:
        await channel.send(parseHTML("Errore: scegli una notifica tra start, rank o points."))

@bot.command(name="setteam")
@async_db_session
async def setteam(ctx):
    server, channel, user, message, dbChatId = parseContext(ctx)
    text = message.content.split(" ", 1)
    if len(text) > 1:
        name = text[1]
        dbChat = DSChat.get(id=dbChatId)
        dbChat.teamName = name
        await channel.send(parseHTML("✅ La tua squadra è <b>{}</b>!".format(dbChat.teamName)))
    else:
        await channel.send(parseHTML("<i>Errore: specifica il nome della squadra dopo !setteam.</i>"))

@bot.command(name="delteam")
@async_db_session
async def delteam(ctx):
    server, channel, user, message, dbChatId = parseContext(ctx)
    dbChat = DSChat.get(id=dbChatId)
    dbChat.teamName = ""
    await channel.send(parseHTML("❌ Il nome della squadra è stato rimosso."))

@bot.command(name="toggleview")
@async_db_session
async def toggleview(ctx):
    server, channel, user, message, dbChatId = parseContext(ctx)
    dbChat = DSChat.get(id=dbChatId)
    if dbChat.viewEmbed:
        dbChat.viewEmbed = False
        await channel.send(parseHTML("❌ La modalità view Embed è stata disabilitata."))
    else:
        dbChat.viewEmbed = True
        await channel.send(parseHTML("✅ La modalità view Embed è stata abilitata!"))


bot.run(js_settings["discord"]["token"])
