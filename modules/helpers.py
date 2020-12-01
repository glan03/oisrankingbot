statsIcons = {
    "low": "🔴",
    "med": "🟠",
    "high": "🟡",
    "top": "🟢",
    "finish": "✅"
}

rankIcons = {
    1:  "🥇",
    2:  "🥈",
    3:  "🥉",
    4:  "4️⃣",
    5:  "5️⃣",
    6:  "6️⃣",
    7:  "7️⃣",
    8:  "8️⃣",
    9:  "9️⃣",
    10: "🔟"
}


def getStatIcon(score: float):
    if score < 30:
        stat = "low"
    elif score < 60:
        stat = "med"
    elif score < 90:
        stat = "high"
    elif score < 100:
        stat = "top"
    else:
        stat = "finish"
    return statsIcons[stat]


def getRankIcon(rank: int):
    if rank in rankIcons:
        return rankIcons[rank]
    else:
        return "<b>{}°</b>".format(rank)
