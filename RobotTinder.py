import random
from PyQt5.Qt import *
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import QApplication
import requests
import warnings
import scipy.sparse
import numpy as np
import scipy.sparse.linalg
import sparse
import sys


def build_from_dense(A, alpha, l0, l1):
    n = A.shape[0]
    k_in = np.sum(A, 0)
    k_out = np.sum(A, 1)

    D1 = k_in + k_out  # to be seen as diagonal matrix, stored as 1d array
    D2 = l1 * (k_out - k_in)  # to be seen as diagonal matrix, stored as 1d array

    if alpha != 0.:
        B = np.ones(n) * (alpha * l0) + D2
        A = - (A + A.T)
        A[np.arange(n), np.arange(n)] = alpha + D1 + np.diagonal(A)
    else:
        last_row_plus_col = (A[n - 1, :] + A[:, n - 1]).reshape((1, n))
        A = A + A.T
        A += last_row_plus_col

        A[np.arange(n), np.arange(n)] = A.diagonal() + D1
        D3 = np.ones(n) * (l1 * (k_out[n - 1] - k_in[n - 1]))  # to be seen as diagonal matrix, stored as 1d array
        B = D2 + D3

    return scipy.sparse.csr_matrix(A), B


def build_from_sparse(A, alpha, l0, l1):
    n = A.shape[0]
    k_in = np.sum(A, 0).A1  # convert matrix of shape (1, n) into 1-dimensional array
    k_out = np.sum(A, 1).A1  # same with (n, 1) matrix

    D1 = k_in + k_out  # to be seen as diagonal matrix, stored as 1d array
    D2 = l1 * (k_out - k_in)  # to be seen as diagonal matrix, stored as 1d array

    if alpha != 0.:
        B = np.ones(n) * (alpha * l0) + D2
        A = - (A + A.T)
        # convert to lil matrix for more efficient computations
        A = A.tolil(copy=False)
        A.setdiag(alpha + D1 + A.diagonal())
    else:
        last_row_plus_col = sparse.COO.from_scipy_sparse(A[n - 1, :] + A[:, n - 1].T)  # create sparse 1d COO array
        A = A + A.T

        A += last_row_plus_col  # broadcast on rows
        A = -A.tocsr()  # reconvert to csr scipy matrix
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", scipy.sparse.SparseEfficiencyWarning)
            A.setdiag(A.diagonal() + D1)

        D3 = np.ones(n) * (l1 * (k_out[n - 1] - k_in[n - 1]))  # to be seen as diagonal matrix, stored as 1d array
        B = D2 + D3

    return A, B


def solve_linear_system(A, B, solver, verbose):
    if solver not in ['spsolve', 'bicgstab']:
        warnings.warn('Unknown parameter {solver} for argument solver. Setting solver = "bicgstab"'.format(solver=solver))
        solver = 'bicgstab'

    if verbose:
        print('Using scipy.sparse.linalg.{solver}(A,B)'.format(solver=solver))

    if solver == 'spsolve':
        sol = scipy.sparse.linalg.spsolve(A, B)
    elif solver == 'bicgstab':
        sol = scipy.sparse.linalg.bicgstab(A, B)[0]

    return sol.reshape((-1,))


def SpringRank(A, alpha=0., l0=1., l1=1., solver='bicgstab', verbose=False, force_dense=False):
    # check if input is sparse or can be converted to sparse.
    use_sparse = True
    if force_dense and not scipy.sparse.issparse(A):
        try:
            A = scipy.sparse.csr_matrix(A)
        except:
            warnings.warn('The input parameter A could not be converted to scipy.sparse.csr_matrix. '
                          'Using a dense representation.')
            use_sparse = False
    elif force_dense:
        use_sparse = False

    # build array to feed linear system solver
    if use_sparse:
        A, B = build_from_sparse(A, alpha, l0, l1)
    else:
        A, B = build_from_dense(A, alpha, l0, l1)

    rank = solve_linear_system(A, B, solver, verbose)

    return rank


pitScoutData = ""
matchData = ""
dataIn = ""

team1STR = ""
team2STR = ""

comparisonsData = []
ranks = []
trueRanks = []
teams = []


def getData(link):
    global pitScoutData, dataIn, matchData, teams
    r = requests.get(link).text
    config1 = r.split("UNIQUE2")
    dataIn = config1[0].split("UNIQUE1")
    # Get pit scout data
    pitScoutData = "<>".join(config1[1].split("UNIQUE1"))
    matchData = "<>".join(dataIn[7:])

    ms = []
    ref = dataIn[0].split("<>")
    for i in ref:
        ms.append([i for i in i.split("/\\") if i])
    ms = [i for i in ms if i]
    teams = list({x for i in ms for x in i})
    teams.sort(key=int)


html = r'''<!doctype html>
<html lang="en">
    <head>
        <style>
            body, html {
                margin: 5;
                color: #C0C0C0;
                font-family: Arial;
                background-color: #282828;
            }
            .teamLookupTable {
  border: 1px solid grey;
  border-collapse: collapse;
  text-align: center;
  padding: 5px 5px;
  width: 45%;
}
.teamImg {
  width: 200px;
}
.column {
  float: left;
  width: 50%;
  display: table-cell;
  overflow-x: scroll;
}

.row:after {
  content: "";
  display: table;
  clear: both;
}
.tableAA {
  font-size: 18px;
  border: 1px solid grey;
  border-collapse: collapse;
  text-align: center;
  padding: 5px 5px;
  color: white;
}
.table {
  border: 1px solid grey;
  border-collapse: collapse;
  text-align: center;
  padding: 5px 5px;
}
        </style>
  </head>
  <body>
  <h2>Robot Tinder</h2>
  <div id='content'></div>
  <div class="row">
    <div class="column" id="team1"></div>
    <div class="column" id="team2"></div>
  </div>
  <script>
  var stringSeparator1 = "/\\"
  var stringSeparator2 = "<>"
  var customConfigDataSTR = ""
  var getMatchDataSTR = ""
  var getTeamLookupConfigSTR = ""
  var pitDataSTR = ""
  var imgLinkSTR = ""
  var imgIDCounter = 0

  function setData(AcustomConfigDataSTR, AgetMatchDataSTR, AgetTeamLookupConfigSTR, AimgLinkSTR, ApitDataSTR) {
    customConfigDataSTR = AcustomConfigDataSTR
    getMatchDataSTR = AgetMatchDataSTR
    getTeamLookupConfigSTR = AgetTeamLookupConfigSTR
    imgLinkSTR = AimgLinkSTR
    pitDataSTR = ApitDataSTR
  }

  function getPitData() {
    return pitDataSTR.split(stringSeparator2)
  }

  function getImgLinks() {
    var rawData = imgLinkSTR.split(stringSeparator2)
    var imgLinks = []
    for(var i = 0; i < rawData.length; i++) {  imgLinks.push(rawData[i].split(stringSeparator1)) }
    return removeEmptyDataFrom2DArray(imgLinks)
  }
  function growImg(imgID) {
    img = document.getElementById(imgID); 
    if(img.style.width == "200px" || img.style.width == "") {
      img.style.width = "600px"; 
      img.style.height = "auto"; 
      img.style.transition = "width 0.5s ease"; 
      return;
    }
    img.style.width = "200px"; 
    img.style.height = "auto"; 
    img.style.transition = "width 0.5s ease"; 
  } 
  function createTables(team1, team2) {
    var html1 = getTeamLookupHTML(team1)
    var html2 = getTeamLookupHTML(team2)
    document.getElementById("team1").innerHTML = '<h2>' + team1 + '</h2><br><br>' + html1
    document.getElementById("team2").innerHTML = '<h2>' + team2 + '</h2><br><br>' + html2
  }
  function getImgLinkHTML(data, team) {
    var apost = "'"
    for(var i = 0; i < data.length; i++) {
      if(data[i][0] == team) {
        var imgId = team + "TeamImgID" + imgIDCounter
        imgIDCounter += 1
        return '<img src="' + data[i][1] + '" id="' + imgId + '" class="teamImg" onclick="growImg(' + apost + imgId + apost + ')">'
      }
    }
    return ""
  }


  function getCustomDataConfig() {
    var rawData = customConfigDataSTR.split(stringSeparator2)
    var matchSchedule = []
    for(var i = 0; i < rawData.length; i++) {  matchSchedule.push(rawData[i].split(stringSeparator1)) }
    return removeEmptyDataFrom2DArray(matchSchedule)
  }
  function getMatchData() {
    return getMatchDataSTR.split(stringSeparator2)
  }
  function getTeamLookupConfig() {
    var rawData = getTeamLookupConfigSTR.split(stringSeparator2)
    var teamLookupConfig = []
    for(var i = 0; i < rawData.length; i++) {  teamLookupConfig.push(rawData[i].split(stringSeparator1)) }
    return removeEmptyDataFrom2DArray(teamLookupConfig)
  }

  function getPitScoutHTMLTable(team, pitData) {
    var html = '<table class="table"><tr class="tableAA"><th class="tableAA">Drive Train</th><th class="tableAA">Wheels #:</th>'
    html += '<th tableAA="table">Motor Type:</th><th tableAA="tableAA">Motor #:</th><th class="tableAA">Comments:</th></tr><tr class="table">'
    html += '<td class="table">' + getPitDatapoint(pitData, team, "dtType") + '</td>'
    html += '<td class="table">' + getPitDatapoint(pitData, team, "wheelsNum") + '</td>'
    html += '<td class="table">' + getPitDatapoint(pitData, team, "motorType") + '</td>'
    html += '<td class="table">' + getPitDatapoint(pitData, team, "motorNum") + '</td>'
    html += '<td class="table">' + getPitDatapoint(pitData, team, "comments") + '</td></tr></table>'
    return html
  }

  function getTeamLookupHTML(team) {
    var configData = getCustomDataConfig()
    var scoutingData = getMatchData()
    var lookupConfigData = getTeamLookupConfig()

    var rowsNum = parseInt(lookupConfigData[0][0])
    var listDataPoints = []
    var compiledDataPoints = []
    for(var i = 1; i < lookupConfigData.length; i++) {
      if(lookupConfigData[i][1] == "Average") {
        compiledDataPoints.push(lookupConfigData[i][0])
      } else if(lookupConfigData[i][1] == "List All") {
        listDataPoints.push(lookupConfigData[i][0])
      }
    }


    var htmlTable = '<table class="teamLookupTable">'
    for(var i = 0; i < compiledDataPoints.length / rowsNum; i++) {
      htmlTable += '<tr class="teamLookupTable">'
      for(var j = 0; j < rowsNum; j++) {
        if(compiledDataPoints[i*rowsNum + j] != undefined) { htmlTable += '<th class="tableAA">' + compiledDataPoints[i*rowsNum + j]+ '</th>' }
      }
      htmlTable += '</tr><tr class="teamLookupTable">'
      for(var j = 0; j < rowsNum; j++) {
        if(compiledDataPoints[i*rowsNum + j] != undefined) { 
          htmlTable += '<td class="table">' + getDatapoint(team, compiledDataPoints[i*rowsNum + j], true) + '</td>' 
        }
      }
      htmlTable += '</tr>'
    }
    for(var i = 0; i < listDataPoints.length; i++) {
      htmlTable += '<tr class="teamLookupTable">'
      htmlTable += '<th class="tableAA">' + listDataPoints[i]+ '</th>'
      var data = getDatapoint(team, listDataPoints[i], false)

      for(var j = 0; j < data[0].length; j++) {
        if((j + 1) % rowsNum == 0 && j != 0) { htmlTable += '</tr><tr class="teamLookupTable">' }
        htmlTable += '<td class="table">' + data[1][j] + ": " + data[0][j] + '</td>'
      }
      htmlTable += '</tr>'
    }

    htmlTable += '</table>'
     return getImgLinkHTML(getImgLinks(), team) + '<br><br>' + getPitScoutHTMLTable(team, getPitData()) + htmlTable
     // return getImgLinkHTML(getImgLinks(), team) + '<br><br>' + getPitScoutHTMLTable(team, getPitData()) + htmlTable
  }

  function getPitDatapoint(data, team, datapoint) {
    for(var i = 0; i < data.length; i++) {
      var json = JSON.parse(data[i])
      if(json["team"] == team) {
        return json[datapoint]
      }
    }
    return 'error'
  }

  function getDatapoint(team, datapoint, isAv) {
    var scoutingData = getMatchData()
    var configData = getCustomDataConfig()
    var count = 0;
    var sum = 0;
    var text = ""
    var isText = false
    var outList = []
    var matchesList = []
    for(var j = 0; j < scoutingData.length; j++) {
      var json = JSON.parse(scoutingData[j])
      var matchNum = json.match
      if(json.team == team) {
        for(var k = 0; k < configData.length; k++) {
          if(configData[k][0] == datapoint) {
            for(var l = 2; l < configData[k].length; l++) {
              if(configData[k][1] == "Numeric") {
                sum += parseInt(json[configData[k][l]])
                isText = false
              } else {
                text += json[configData[k][l]]
                isText = true
              }
            }
          }    
        }
        if(isAv) {
          count++;
        } else {
          if(!isText) {
            outList.push(sum)
            matchesList.push(matchNum)
            sum = 0
          } else {
            outList.push(text)
            matchesList.push(matchNum)
            text = ""
          }

        }
      }
    }
    if(isAv) {
      return sum / count
    }
    return [outList, matchesList]
  }
    function removeEmptyDataFrom2DArray(array) {
    var array = array.filter(function (el) { return el != null; });
    for(var i = 0; i < array.length; i++) {
      array[i] = array[i].filter(function (el) { return el != null; });
      array[i] = array[i].filter(function (el) { return el != ""; });
    }
    array = array.filter(function (el) { return el != []; });
    return array
  }
  </script>
  </body>
'''

app = QApplication(sys.argv)
win = QWidget()
layout = QGridLayout()
rankDisplayScroll = QScrollArea()
rankDisplayScroll.setFixedWidth(int(app.primaryScreen().size().width() / 9))
rankDisplayLayout = QGridLayout()

top = QWidget()
topLayout = QGridLayout()
left = QWidget()
leftLayout = QGridLayout()
row1 = QWidget()
row1Layout = QGridLayout()
row2 = QWidget()
row2Layout = QGridLayout()

web = QWebEngineView()
linkEntry = QLineEdit()
# linkEntry.setText("https://script.google.com/macros/s/AKfycbzbVJ03rdYPL7VORjsFZgu6AU4UnLAGrPAgFeCzBJoAOqnA3C4rf1JX/exec")
submit = QPushButton("Enter Link", win)
rankDisplayWidget = QTextEdit()
saveFileButton = QPushButton("Save")
rankDisplayScroll.setWidgetResizable(True)
rankDisplayLayout.addWidget(rankDisplayWidget, 1, 0)
rankDisplayLayout.addWidget(saveFileButton, 0, 0)
rankDisplayScroll.setLayout(rankDisplayLayout)

row1Layout.addWidget(linkEntry, 0, 0)
row1Layout.addWidget(submit, 0, 1)
row1Layout.setSpacing(0)
row1Layout.setAlignment(Qt.AlignTop)
row1.setLayout(row1Layout)

team1 = QPushButton("Team 1", win)
team2 = QPushButton("Team 2", win)
row2Layout.addWidget(team1, 0, 0)
row2Layout.addWidget(team2, 0, 1)
row2Layout.setAlignment(Qt.AlignTop)
row2.setLayout(row2Layout)

topLayout.addWidget(row1, 0, 0)
topLayout.addWidget(row2, 1, 0)
topLayout.setAlignment(Qt.AlignTop)
top.setLayout(topLayout)


def submitLink():
    global linkEntry
    if linkEntry.text() == "":
        return
    getData(linkEntry.text() + "?data={}")
    linkEntry.clear()
    web.page().runJavaScript(
        "setData(String.raw`{0}`, String.raw`{1}`, String.raw`{2}`, String.raw`{3}`, String.raw`{4}`)".format(dataIn[1], matchData, dataIn[4], dataIn[6], pitScoutData))
    createPage()


def createPage():
    global web, team1, team2
    getNextTeams()
    web.page().runJavaScript("createTables('{0}', '{1}')".format(team1STR, team2STR))
    team1.setText(team1STR)
    team2.setText(team2STR)


def getTeams(dataInIn):
    out = []
    for i in dataInIn:
        for j in i:
            if not int(j) in out:
                out.append(int(j))
    out.sort()
    return out


def Diff(li1, li2):
    return list(list(set(li1) - set(li2)) + list(set(li2) - set(li1)))


def saveFile():
    try:
        fileName = QFileDialog.getSaveFileName()
        if fileName[0] == "":
            return
        file = open(fileName[0], 'w+')
        for i in comparisonsData:
            file.write(str(i[0]) + ">" + str(i[1]) + "\n")
        file.close()
    except Exception as e:
        print(e)


def displayRank():
    text = ""
    revRanks = list(trueRanks)
    for i in range(len(revRanks)):
        text = text + str(i) + ")\t"
        for j in revRanks[i]:
            text = text + str(j) + "\t"
        text = text[:-1]
        text = text + "\n"
    rankDisplayWidget.setText(text)


def correctComparisonsData(incList):
    new_list = [list(element) for element in list(set([frozenset(element) for element in incList]))]
    for i in new_list:
        if len(i) < 2:
            new_list.remove(i)
    return new_list


def unorderedInList(refList, unordered):
    for i in refList:
        if set(i) == set(unordered):
            return True
    return False


def getNextTeams():
    global team1STR, team2STR, comparisonsData
    # comparisonsData = correctComparisonsData(comparisonsData)
    if len(comparisonsData) > 0:
        calculateRanks()
    teamToChooseFrom = list(map(str, Diff(list(map(int, teams)), getTeams(comparisonsData))))
    if len(teamToChooseFrom) <= 1:
        areSameRankTeams = False
        for i in ranks:
            if len(i) > 1:
                areSameRankTeams = True
                break
        if not areSameRankTeams:
            try:
                flatComparisonsData = [j for sub in comparisonsData for j in sub]
                random.shuffle(flatComparisonsData)
                print("Randomized Flat Data: ", end="")
                print(flatComparisonsData)
                minTeam1 = flatComparisonsData[0]
                minTeam2 = flatComparisonsData[1]
                if flatComparisonsData.count(flatComparisonsData[0]) < flatComparisonsData.count(flatComparisonsData[1]):
                    minTeam1 = flatComparisonsData[0]
                    minTeam2 = flatComparisonsData[1]
                for i in flatComparisonsData[2:]:
                    if flatComparisonsData.count(i) < flatComparisonsData.count(minTeam2):
                        minTeam2 = i
                    if flatComparisonsData.count(i) < flatComparisonsData.count(minTeam1):
                        minTeam2 = minTeam1
                        minTeam1 = i
                if minTeam2 == minTeam1:
                    while minTeam2 == minTeam1:
                        minTeam2 = random.choice(flatComparisonsData)

                team1STR = str(minTeam1)
                team2STR = str(minTeam2)
            except Exception as e:
                print(e)
        else:
            try:
                print("Ranks: ", end="")
                print(ranks)
                team1STR = str(ranks[0][0])
                if len(ranks[0]) == 1:
                    team2STR = str(ranks[1][0])
                else:
                    team2STR = str(ranks[0][1])
            except Exception as e:
                print(e)
        if len(teamToChooseFrom) == 1:
            team2STR = teamToChooseFrom[0]


    else:
        print("Teams that have not been chosen: ", end="")
        print(teamToChooseFrom)
        team1STR = random.choice(teamToChooseFrom)
        while True:
            ranTeam = random.choice(teamToChooseFrom)
            if not ranTeam == team1STR:
                team2STR = ranTeam
                break

    while unorderedInList(comparisonsData, [int(team1STR), int(team2STR)]):
        print("Error: Chose existing pair of teams")
        team1STR = str(random.choice(teams))
        team2STR = str(random.choice(teams))
        while team1STR == team2STR:
            team2STR = str(random.choice(teams))


def calculateRanks():
    global ranks, trueRanks
    localTeams = getTeams(comparisonsData)
    dataForSpring = np.zeros((len(localTeams), len(localTeams)))

    for i in comparisonsData:
        betterTeamIndex = localTeams.index(i[0])
        worseTeamIndex = localTeams.index(i[1])
        dataForSpring[betterTeamIndex][worseTeamIndex] = 1

    rank = SpringRank(scipy.sparse.csr_matrix(dataForSpring)).tolist()

    rankTeams = []
    for i in range(len(rank)):
        rankTeams.append([rank[i], localTeams[i]])
    rankTeams = sorted(rankTeams, key=lambda row: row[0])
    try:
        rankTeams.reverse()
        last = 0
        i = 0
        ranks = []
        for ii in rankTeams:
            if i != 0 and last == ii[0]:
                ranks[i - 1].append(ii[1])
            else:
                ranks.append([ii[1]])
                i = i + 1

            last = ii[0]
        trueRanks = list(ranks)
        ranks = sorted(ranks, key=len)
        ranks.reverse()
        displayRank()
    except Exception as e:
        print(e)


def submitTeam1():
    submitTeam(team1STR, team2STR)


def submitTeam2():
    submitTeam(team2STR, team1STR)


def submitTeam(betterTeam, worseTeam):
    if team1STR == "" or team2STR == "":
        return
    comparisonsData.append([int(betterTeam), int(worseTeam)])
    createPage()


openFile = QFileDialog.getOpenFileName()
if openFile[0] != "":
    openedFile = open(openFile[0], 'r')
    Lines = openedFile.readlines()
    for i in Lines:
        comparisonsData.append(list(map(int, i.replace("\n", "").split(">"))))

print(comparisonsData)

web.setHtml(html)
submit.clicked.connect(submitLink)
team1.clicked.connect(submitTeam1)
team2.clicked.connect(submitTeam2)
saveFileButton.clicked.connect(saveFile)

web.setFixedHeight(int(app.primaryScreen().size().height() * .75))
leftLayout.addWidget(top, 0, 0)
leftLayout.addWidget(web, 2, 0)
left.setLayout(leftLayout)

layout.addWidget(left, 0, 0)
layout.addWidget(rankDisplayScroll, 0, 1)
layout.setAlignment(Qt.AlignTop)
win.setLayout(layout)
win.setWindowTitle("Robot Tinder")
win.show()
sys.exit(app.exec_())

