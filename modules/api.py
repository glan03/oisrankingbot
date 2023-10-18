from requests import get


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
    baseUrl = "https://judge.science.unitn.it/ranking"
    data = {}
    oldData = {}

    def __init__(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        self.oldData = self.data
        try:
            self.data = {
                "teams": get(f"{self.baseUrl}/teams", timeout=5).json(),
                "users": get(f"{self.baseUrl}/users", timeout=5).json(),
                "tasks": get(f"{self.baseUrl}/tasks", timeout=5).json(),
                "scores": get(f"{self.baseUrl}/scores", timeout=5).json()
            }
        except Exception:
            raise NoEventRunning

    def questions(self, oldData: bool=False) -> list[str]:
        data = self.data if not oldData else self.oldData
        return sorted([x for x in data['tasks']], key=lambda x: data['tasks'][x]['order'])

    def teams(self, oldData: bool=False) -> list[str]:
        data = self.data if not oldData else self.oldData
        scores = data['scores']
        return sorted([x for x in data['users']], key=lambda x: sum(scores.get(x, {}).values()), reverse=True)

    def teamInfo(self, teamName: str, oldData: bool=False) -> dict:
        if teamName not in self.teams(oldData):
            raise TeamNameError

        data = self.data if not oldData else self.oldData
        tasks = self.questions(oldData)
        partials = data['scores'][teamName]
        partials = [partials.get(task, 0) for task in tasks]
        total = sum(partials)
        rank = self.teams(oldData).index(teamName) + 1

        return {
            "rank": rank,
            "name": teamName,
            "partialScores": partials,
            "totalScore": total
        }

    def getTeamPartial(self, teamName: str, questionName: str, oldData: bool=False) -> float:
        if questionName not in self.questions(oldData):
            raise QuestionNameError

        questionPos = self.questions(oldData).index(questionName)
        return self.teamInfo(teamName, oldData)["partialScores"][questionPos]
