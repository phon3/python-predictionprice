# -*- coding: utf-8 -*-
import os
from apscheduler.schedulers.blocking import BlockingScheduler
from predictionprice.derivedpoloniex import ExchangeTradePoloniex
from predictionprice import PredictionPrice

myGmailAddress = "********@gmail.com"
myGmailAddressPassword = "************"
myAPIKey = "************************"
mySecret = "************************************************"

coins = ["ETH", "XMR", "XRP", "FCT", "DASH"]
backTestOptParams = [
    [20, 40, 20, 40],
    [20, 40, 20, 40],
    [20, 40, 20, 40],
    [20, 40, 20, 40],
    [20, 40, 20, 40]]

basicCoin = "BTC"
workingDirPath = os.path.dirname(os.path.abspath(__file__))


def botRoutine():

    ppList = []
    tomorrwPricePrediction = []

    # --- Prediction price and back test
    for coinIndex in range(len(coins)):
        pp = PredictionPrice(currentPair=basicCoin + "_" + coins[coinIndex], workingDirPath=workingDirPath,
                             gmailAddress=myGmailAddress, gmailAddressPassword=myGmailAddressPassword,
                             backTestOptNumFeatureMin=backTestOptParams[coinIndex][0],
                             backTestOptNumFeatureMax=backTestOptParams[coinIndex][1],
                             backTestOptNumTrainSampleMin=backTestOptParams[coinIndex][2],
                             backTestOptNumTrainSampleMax=backTestOptParams[coinIndex][3])

        pp.fit(pp.appreciationRate_, pp.quantizer(pp.appreciationRate_))
        pp.sendMail(pp.getSummary())
        ppList.append(pp)
        if pp.backTestResult_["AccuracyRateUp"].values > 0.5:
            tomorrwPricePrediction.append(pp.tomorrowPriceFlag_)
        else:
            tomorrwPricePrediction.append(False)

    # --- Fit balance
    try:
        polo = ExchangeTradePoloniex(APIKey=myAPIKey, Secret=mySecret, workingDirPath=workingDirPath,
                              gmailAddress=myGmailAddress, gmailAddressPassword=myGmailAddressPassword,
                              coins=coins, buySigns=tomorrwPricePrediction)
        polo.savePoloniexBalanceToCsv()
        polo.fitBalance()
        polo.sendMailBalance(polo.getSummary())
        polo.savePoloniexBalanceToCsv()
    except:
        pass

    # --- Write log
    for coinIndex in range(len(coins)):
        pp = ppList[coinIndex]
        writeBotLog(pp.getSummary())
    writeBotLog(polo.getSummary())

    # --- Back test optimization
    for coinIndex in range(len(coins)):
        pp = ppList[coinIndex]
        pp.backTestOptimization(pp.appreciationRate_, pp.quantizer(pp.appreciationRate_))


def writeBotLog(logStr):
    fileName = __file__.split(".py")[0] + ".log"
    f = open(fileName, "a")
    f.write(logStr)
    f.close()


if __name__ == "__main__":
    sc = BlockingScheduler(timezone="UTC")
    sc.add_job(botRoutine, "cron", hour=0, minute=1)
    sc.start()
