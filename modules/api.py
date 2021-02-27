from requests import get
from lxml import html
from requests.exceptions import ReadTimeout


class NoEventRunning(Exception):
    def __init__(self):
        self.message = "No event is currently running. The leaderboard is not active."

class TeamNameError(Exception):
    def __init__(self):
        self.message = "The team specified was not in the selected leaderboard."

class QuestionNameError(Exception):
    def __init__(self):
        self.message = "The question specified is not part of this round."


class OISRankingAPI:
    baseUrl = "https://gara.squadre.olinfo.it/ranking/"
    xpaths = {
        "titleGroup": "/html/body/table/thead/tr",
        "teamsGroup": "/html/body/table/tbody",
        "leaderboardTitle": "/html/body/h1"
    }

    sub = ""
    debug = False
    page = None
    prevPage = None

    def __init__(self, sub: str="", _debug: bool=False):
        if sub not in ["biennio", "triennio"]:
            sub = ""
        self.sub = sub
        self.debug = _debug
        self.page = None
        try:
            self.refresh()
        except NoEventRunning:
            pass

    def refresh(self):
        self.prevPage = self.page
        if not self.debug:
            try:
                resp = get(self.baseUrl + self.sub, timeout=5)
            except ReadTimeout:
                raise NoEventRunning
            if resp.status_code == 404:
                raise NoEventRunning
            self.page = html.fromstring(resp.content)
        else:
            doc = self.sub if self.sub else "all"
            self.page = html.fromstring(open(f"dev/{doc}.html").read())

    def _getTitleRow(self, oldData: bool=False):
        page = self.page if not oldData else self.prevPage
        return page.xpath(self.xpaths["titleGroup"])[0]

    def _getTeamsRow(self, oldData: bool=False):
        page = self.page if not oldData else self.prevPage
        return page.xpath(self.xpaths["teamsGroup"])[0]

    def changeSub(self, newSub: str=""):
        if newSub not in ["biennio", "triennio"]:
            newSub = ""
        self.sub = newSub

    def leaderboardTitle(self, oldData: bool=False):
        page = self.page if not oldData else self.prevPage
        return str(page.xpath(self.xpaths["leaderboardTitle"])[0].text).strip().replace("  ", " ")

    def questions(self, oldData: bool=False):
        return [str(x[0].text).strip() for x in self._getTitleRow(oldData)[5:]]

    def teams(self, oldData: bool=False):
        return [str(x[1][0].text).strip() for x in self._getTeamsRow(oldData)]

    def teamInfo(self, teamName: str, oldData: bool=False):
        if teamName not in self.teams(oldData):
            raise TeamNameError
        teamPos = self.teams(oldData).index(teamName)
        teamRaw = self._getTeamsRow(oldData)[teamPos]
        return {
            "index": int(teamPos),
            "rank": int(teamRaw[0].text),
            "name": str(teamRaw[1][0].text).strip(),
            "institute": str(teamRaw[2].text).strip(),
            "region": str(teamRaw[3].text).strip(),
            "totalScore": float(teamRaw[4].text),
            "partialScores": [float(x.text) for x in teamRaw[5:]]
        }

    def getTeamPartial(self, teamName: str, questionName: str, oldData: bool=False):
        if questionName not in self.questions(oldData):
            raise QuestionNameError
        questionPos = self.questions(oldData).index(questionName)
        return self.teamInfo(teamName, oldData)["partialScores"][questionPos]

    def validTeamName(self, teamName: str, oldData: bool=False):
        return teamName in self.teams(oldData)
