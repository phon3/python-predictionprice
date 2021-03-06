# -*- coding: utf-8 -*-
"""
Copyright (c) 2016 Tylor Darden
Released under the MIT license
http://opensource.org/licenses/mit-license.php
"""
import sys
import os
import pytz
import time
import datetime
import smtplib
import email
import pickle
import csv
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from sklearn import tree
from sklearn.preprocessing import StandardScaler
import poloniex
import logging


class PredictionPrice(object):
    def __init__(self, currentPair="BTC_ETH", workingDirPath=".",
                 gmailAddress="", gmailAddressPassword="",
                 waitGettingTodaysChart=True, waitGettingTodaysChartTime=60,
                 numFeature=30, numTrainSample=30, standardizationFeatureFlag=True, numStudyTrial=50,
                 useBackTestOptResult=True, backTestInitialFund=1000, backTestSpread=0, backTestDays=60,
                 backTestOptNumFeatureMin=20, backTestOptNumFeatureMax=40, backTestOptNumTrainSampleMin=20, backTestOptNumTrainSampleMax=40,
                 marginTrade=False):

        self.marginTrade = marginTrade
        self.currentPair = currentPair
        self.workingDirPath = workingDirPath
        self.useBackTestOptResult=useBackTestOptResult
        if self.useBackTestOptResult and os.path.exists(self.workingDirPath + "/backTestOptResult_" + self.currentPair + ".pickle"):
            with open(self.workingDirPath + "/backTestOptResult_" + self.currentPair + ".pickle", mode='rb') as f:
                self.backTestOptResult_ = pickle.load(f)
            self.numFeature = self.backTestOptResult_["numFeatureOpt"]
            self.numTrainSample = self.backTestOptResult_["numTrainSampleOpt"]
        else:
            self.useBackTestOptResult = False
            self.numFeature = numFeature
            self.numTrainSample = numTrainSample
        self.standardizationFeatureFlag = standardizationFeatureFlag

        self.numStudyTrial = numStudyTrial
        self.gmailAddress = gmailAddress
        self.gmailAddressPassword = gmailAddressPassword

        self.waitGettingTodaysChart = waitGettingTodaysChart
        self.waitGettingTodaysChartTime = waitGettingTodaysChartTime

        self.backTestInitialFund = backTestInitialFund
        self.backTestSpread = backTestSpread
        self.backTestDays = backTestDays

        self.backTestOptNumFeatureMin = backTestOptNumFeatureMin
        self.backTestOptNumFeatureMax = backTestOptNumFeatureMax
        self.backTestOptNumTrainSampleMin = backTestOptNumTrainSampleMin
        self.backTestOptNumTrainSampleMax = backTestOptNumTrainSampleMax

        self.todayStr = str(datetime.datetime.now(pytz.timezone("UTC")))[0:10]
        self.chartData_ = self.getChartData()
        #---self.saveChartData(self.chartData_)
        #---self.chartData_ = self.loadChartData()
        self.appreciationRate_ = self.getAppreciationRate(self.chartData_.open)
        self.chartDataLatestDayStr = str(self.chartData_.date[0])[0:10]

        if self.waitGettingTodaysChart:
            for tmpIndex in range(int(self.waitGettingTodaysChartTime*60.0/20.0)):
                if not (self.todayStr == self.chartDataLatestDayStr):
                    time.sleep(20)
                else:
                    break
                self.chartData_ = self.getChartData()
                self.appreciationRate_ = self.getAppreciationRate(self.chartData_.open)
                self.chartDataLatestDayStr = str(self.chartData_.date[0])[0:10]

    def reverseDataFrame(self,dataFrame):
        """Reverse the index of chart data as last data comes first."""
        dataFrame = dataFrame[::-1]
        dataFrame.index = dataFrame.index[::-1]
        return dataFrame

    def getChartData(self):
        """Get chart data."""
        polo = poloniex.Poloniex(timeout = 10, coach = True, extend=True)
        chartData = pd.DataFrame(polo.marketChart(self.currentPair, period=polo.DAY, start=time.time() - polo.DAY * 500,end=time.time())).astype(float)
        chartData.date = pd.DataFrame([datetime.datetime.fromtimestamp(chartData.date[i]).date() for i in range(len(chartData.date))])
        return self.reverseDataFrame(chartData)

    def saveChartData(self,chartData):
        """Save chart data to a pickle file. You can load it with loadChartData() for debug."""
        with open("chartData_"+ self.currentPair + ".pickle", mode="wb") as f:
            pickle.dump(chartData, f)
        return

    def loadChartData(self):
        """You can load chart data from a pickle file. You have to save chart data with saveChartData() before calling."""
        with open("chartData_"+ self.currentPair + ".pickle", mode="rb") as f:
            chartData = pickle.load(f)
        return chartData

    def getAppreciationRate(self,price):
        """Transrate chart price to appreciation rate."""
        return np.append(-np.diff(price) / price[1:].values,0)

    def quantizer(self, y):
        """Transrate appreciation rate to -1 or 1 for preparing teacher data."""
        return np.where(np.array(y) >= 0.0, 1, -1)

    def standardizationFeature(self, train_X, test_X):
        """Standarize feature data."""
        sc = StandardScaler()
        train_X_std = sc.fit_transform(train_X)
        test_X_std = sc.transform(test_X)
        return train_X_std, test_X_std

    def preparationTrainSample(self,sampleData,classData,trainStartIndex, numFeature, numTrainSample):
        """Prepare training sample."""
        train_X = []
        train_y = []
        for i in range(numTrainSample):
            train_X.append(sampleData[trainStartIndex + i + 1:trainStartIndex + numFeature + i + 1])
            train_y.append(classData[trainStartIndex + i])
        return np.array(train_X), np.array(train_y)

    def prediction(self, sampleData, classData, trainStartIndex, numFeature, numTrainSample):
        """Return probability of price rise."""
        train_X, train_y = self.preparationTrainSample(sampleData, classData, trainStartIndex, numFeature, numTrainSample)
        X = np.array([sampleData[trainStartIndex:trainStartIndex + numFeature]])
        if self.standardizationFeatureFlag:
            train_X, X = self.standardizationFeature(train_X, X)
        y = []
        for i in range(0, self.numStudyTrial):
            clf = tree.DecisionTreeClassifier()
            clf.fit(train_X, train_y)
            y.append(clf.predict(X)[0])
        return sum(y) * 1.0 / len(y)

    def setTomorrowPriceProbability(self, sampleData, classData):
        """Set probability of price rise and buying signal to menber valiables."""
        self.tomorrowPriceProbability_ = (self.prediction(sampleData, classData, 0, self.numFeature, self.numTrainSample) + 1.0) / 2.0
        if self.tomorrowPriceProbability_>0.5:
            self.tomorrowPriceFlag_ = True
        else:
            self.tomorrowPriceFlag_ = False
        return self.tomorrowPriceProbability_

    def backTest(self, sampleData, classData, numFeature, numTrainSample, saveBackTestGraph):
        """Do back test and return the result."""
        Y = []
        YPrediction = []
        fund = [self.backTestInitialFund]
        pastDay = 0
        accuracyUp = 0
        accuracyDown = 0
        for trainStartIndex in range(self.backTestDays, 0, -1):
            yPrediction = self.quantizer(self.prediction(sampleData, classData, trainStartIndex, numFeature, numTrainSample))
            y = self.quantizer(classData[trainStartIndex - 1])
            Y.append(y.tolist())
            YPrediction.append(yPrediction.tolist())
            pastDay += 1
            if yPrediction == y:
                if yPrediction == 1:
                    accuracyUp += 1
                    fund.append(fund[pastDay - 1] * (1 + abs(self.appreciationRate_[trainStartIndex - 1]) - self.backTestSpread))
                else:
                    accuracyDown += 1
                    if self.marginTrade:
                        fund.append(fund[pastDay - 1] * (1 + abs(self.appreciationRate_[trainStartIndex - 1]) - self.backTestSpread))
                    else:
                        fund.append(fund[pastDay - 1])
            else:
                if yPrediction == 1:
                    fund.append(fund[pastDay - 1] * (1 - abs(self.appreciationRate_[trainStartIndex - 1]) - self.backTestSpread))
                else:
                    if self.marginTrade:
                        fund.append(fund[pastDay - 1] * (1 - abs(self.appreciationRate_[trainStartIndex - 1]) - self.backTestSpread))
                    else:
                        fund.append(fund[pastDay - 1])

        backTestAccuracyRateUp = float(accuracyUp) / sum(np.array(YPrediction)[np.where(np.array(YPrediction) == 1)])
        backTestAccuracyRateDown = -float(accuracyDown) / sum(np.array(YPrediction)[np.where(np.array(YPrediction) == -1)])

        trainStartIndex = 0
        backTestCurrentPrice = self.chartData_.open[trainStartIndex:trainStartIndex + self.backTestDays + 1]
        backTestCurrentPrice = backTestCurrentPrice[::-1].tolist()
        backTestDate = self.chartData_.date[trainStartIndex:trainStartIndex + self.backTestDays + 1]
        backTestDate = backTestDate[::-1].tolist()

        backTestFinalFund = fund[-1]
        backTestInitialCurrentPrice = backTestCurrentPrice[0]
        backTestFinalCurrentPrice = backTestCurrentPrice[-1]
        backTestIncreasedFundRatio = (backTestFinalFund - self.backTestInitialFund) / self.backTestInitialFund
        backTestIncreasedCurrentPriceRatio = (backTestFinalCurrentPrice - backTestInitialCurrentPrice) / backTestInitialCurrentPrice

        columnNames = ["AccuracyRateUp", "AccuracyRateDown",
                       "InitialFund", "FinalFund", "IncreasedFundRatio",
                       "InitialCurrentPrice", "FinalCurrentPrice", "IncreasedCurrentPriceRatio"]
        columnValues = [backTestAccuracyRateUp, backTestAccuracyRateDown,
                        self.backTestInitialFund, backTestFinalFund, backTestIncreasedFundRatio,
                        backTestInitialCurrentPrice, backTestFinalCurrentPrice, backTestIncreasedCurrentPriceRatio]
        backTestResult = pd.DataFrame(np.array([columnValues]), columns=columnNames)

        if saveBackTestGraph:
            fig1, ax1 = plt.subplots(figsize=(11, 6))
            p1, = ax1.plot(backTestDate, fund, "-ob")
            ax1.set_title("Back test (" + self.currentPair + ")")
            ax1.set_xlabel("Day")
            ax1.set_ylabel("Fund")
            plt.grid(fig1)
            ax2 = ax1.twinx()
            p2, = ax2.plot(backTestDate, backTestCurrentPrice, '-or')
            ax2.set_ylabel("Price[" + self.currentPair + "]")
            ax1.legend([p1, p2], ["Fund", "Price_" + self.currentPair], loc="upper left")
            plt.savefig(self.workingDirPath + "/backTest_" + self.currentPair + ".png", dpi=50)
            plt.close()

            self.backTestResult_ = backTestResult

        return backTestResult

    def backTestOptimization(self, sampleData, classData):
        """Optimize the number of features and training samples and save the results to a pickle file."""
        X = np.arange(self.backTestOptNumFeatureMin, self.backTestOptNumFeatureMax + 1, 1)
        Y = np.arange(self.backTestOptNumTrainSampleMin, self.backTestOptNumTrainSampleMax + 1, 1)
        X, Y = np.meshgrid(X, Y)
        Z = np.zeros([len(Y[:]), len(X[0])])

        for i in range(0, len(X[0])):
            for j in range(0, len(Y[:])):
                Z[j][i] = self.backTest(sampleData, classData, X[j][i], Y[j][i], False)["IncreasedFundRatio"].values[0]
                #--- print("-" * 80)
                #--- print("NumFeatur: " + str(X[j][i]))
                #--- print("NumTrainSample: " + str(Y[j][i]))
                #--- print("IncreasedFundRatio[%]: " + str(round(Z[j][i] * 100, 1)))

        maxZRow = np.where(Z == np.max(Z))[0][0]
        maxZCol = np.where(Z == np.max(Z))[1][0]

        numFeatureOpt = X[maxZRow][maxZCol]
        numTrainSampleOpt = Y[maxZRow][maxZCol]
        dateOpt = datetime.datetime.now()

        backTestOptResult = {"X": X, "Y": Y, "Z": Z, "numFeatureOpt": numFeatureOpt,
                             "numTrainSampleOpt": numTrainSampleOpt, "dateOpt": dateOpt}
        with open(self.workingDirPath + "/backTestOptResult_" + self.currentPair + ".pickle", mode='wb') as f:
            pickle.dump(backTestOptResult, f)

        print("-" * 30 + " Optimization Result " + "-" * 30)
        print("NumFeatur: " + str(numFeatureOpt))
        print("NumTrainSample: " + str(numTrainSampleOpt))
        print("IncreasedFundRatio[%]: " + str(round(Z[maxZRow][maxZCol] * 100, 1)))

        fig = plt.figure()
        ax = Axes3D(fig)
        ax.plot_surface(X, Y, Z, rstride=1, cstride=1, cmap=plt.cm.hot)
        ax.contourf(X, Y, Z, zdir="z", offset=-2, cmap=plt.cm.hot)
        ax.set_title("Back test optimization (" + self.currentPair + ")")
        ax.set_xlabel("NumFeatur")
        ax.set_ylabel("NumTrainSample")
        ax.set_zlabel("IncreasedFundRatio")
        ax.view_init(90, 90)
        plt.savefig(self.workingDirPath + "/backTestOptResult_" + self.currentPair + ".png", dpi=50)
        plt.close()

    def fit(self, sampleData, classData):
        """Call backTest() and setTomorrowPriceProbability() in one sitting."""
        self.backTest(sampleData, classData, self.numFeature, self.numTrainSample, True)
        self.setTomorrowPriceProbability(sampleData, classData)

    def getSummary(self):
        """Make summary sentence that include the result of the back test and the prediction of the price rise."""
        summaryStr=""
        summaryStr += "-----------------------------------------\n"
        summaryStr += "Chart data info.\n"
        summaryStr += "-----------------------------------------\n"
        summaryStr += "CurrentPair: " + self.currentPair + "\n"
        summaryStr += "Today: " + self.todayStr + "\n"
        summaryStr += "LatestDayInData: " + self.chartDataLatestDayStr + "\n"
        summaryStr += "LatestOpenPriceInData: " + str(self.chartData_.open[0]) + "\n"
        summaryStr += "PreviousDayInData: " + str(self.chartData_.date[1])[0:10] + "\n"
        summaryStr += "PreviousOpenPriceInData: " + str(self.chartData_.open[1]) + "\n"
        summaryStr += "-----------------------------------------\n"
        summaryStr += "Back test info.\n"
        summaryStr += "-----------------------------------------\n"
        if self.useBackTestOptResult:
            summaryStr += "ExecOptDay: " + str(self.backTestOptResult_["dateOpt"])[0:19] + "\n"
        else:
            summaryStr += "ExecOptDay: Nan\n"
        summaryStr += "NumFeature: " + str(self.numFeature) + "\n"
        summaryStr += "NumTrainSample: " + str(self.numTrainSample) + "\n"
        summaryStr += "AccuracyRateUp[%]: " + str(round(self.backTestResult_["AccuracyRateUp"].values[0]*100, 1)) + "\n"
        summaryStr += "AccuracyRateDown[%]: " + str(round(self.backTestResult_["AccuracyRateDown"].values[0]*100, 1)) + "\n"
        summaryStr += "InitialFund: " + str(self.backTestResult_["InitialFund"].values[0]) + "\n"
        summaryStr += "FinalFund: " + str(self.backTestResult_["FinalFund"].values[0]) + "\n"
        summaryStr += "IncreasedFundRatio[%]: " + str(round(self.backTestResult_["IncreasedFundRatio"].values[0]*100, 1)) + "\n"
        summaryStr += "InitialCurrentPrice: " + str(self.backTestResult_["InitialCurrentPrice"].values[0]) + "\n"
        summaryStr += "FinalCurrentPrice: " + str(self.backTestResult_["FinalCurrentPrice"].values[0]) + "\n"
        summaryStr += "IncreasedCurrentPriceRatio[%]: " + str(round(self.backTestResult_["IncreasedCurrentPriceRatio"].values[0]*100, 1)) + "\n"
        summaryStr += "-----------------------------------------\n"
        summaryStr += "Tomorrow " + self.currentPair + " price prediction\n"
        summaryStr += "-----------------------------------------\n"
        summaryStr += "TomorrowPriceRise?: " + str(self.tomorrowPriceFlag_) +"\n"
        summaryStr += "Probability[%]: " + str(round(self.tomorrowPriceProbability_*100,1)) +"\n"
        return summaryStr

    def sendMail(self, body):
        """Send a mail to inform the summary of the prediction."""
        if self.gmailAddress == "" or self.gmailAddressPassword == "":
            return "Set your gmail address and password."
        # ---Create message
        msg = email.MIMEMultipart.MIMEMultipart()
        msg["From"] = self.gmailAddress
        msg["To"] = self.gmailAddress
        msg["Date"] = email.Utils.formatdate()
        msg["Subject"] = "TomorrowPricePrediction( " + self.currentPair + " )"
        msg.attach(email.MIMEText.MIMEText(body))
        # ---AttachimentFile
        attachimentFiles = []
        if os.path.exists(self.workingDirPath + "/backTest_" + self.currentPair + ".png"):
            attachimentFiles.append(self.workingDirPath + "/backTest_" + self.currentPair + ".png")
        if os.path.exists(self.workingDirPath + "/backTestOptResult_" + self.currentPair + ".png"):
            attachimentFiles.append(self.workingDirPath + "/backTestOptResult_" + self.currentPair + ".png")
        for afn in attachimentFiles:
            img = open(afn, "rb").read()
            mimg = email.MIMEImage.MIMEImage(img, "png", filename=afn)
            msg.attach(mimg)
        # ---SendMail
        smtpobj = smtplib.SMTP("smtp.gmail.com", 587)
        smtpobj.ehlo()
        smtpobj.starttls()
        smtpobj.login(self.gmailAddress, self.gmailAddressPassword)
        smtpobj.sendmail(self.gmailAddress, self.gmailAddress, msg.as_string())
        smtpobj.close()
