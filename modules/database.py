from pony.orm import Database, PrimaryKey, Required, Optional, StrArray

db = Database("sqlite", "../oisrankingbot.db", create_db=True)


class TGUser(db.Entity):
    chatId = PrimaryKey(int, sql_type="BIGINT", size=64)
    status = Required(str, default="normal")
    teamName = Optional(str)
    news = Required(StrArray, default=["eventStart", "rankChanged", "pointsChanged"])


class DSChat(db.Entity):
    chatId = Required(str)
    status = Required(str, default="normal")
    teamName = Optional(str)
    viewEmbed = Required(bool, default=False)
    news = Required(StrArray, default=["eventStart", "rankChanged", "pointsChanged"])


db.generate_mapping(create_tables=True)
