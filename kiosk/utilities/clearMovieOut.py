#!/usr/bin/python
"""
    Change Log:
        2010-11-25 Created by Kitch for build 1.0.001
            change slot No input to RFID input
        2009-05-14 Created by Kitch for build 0.4.6
            accept 0 as days and 0 as amount 
        2009-04-09 Created by Kitch
            clear out movies

"""

__VERSION__ = '0.4.6'

import os
import sys

USER_ROOT = "/home/mm/"
try:
    f = open("/etc/kioskhome")
    USER_ROOT = f.read().strip()
    f.close()
except:
    pass

PROXY_DIR = os.path.join(USER_ROOT, "kiosk", "mkc2", "proxy")
sys.path.append(PROXY_DIR)
import config
from conn_proxy import ConnProxy
from price_coupon_kiosk import PricePlanEngine
from tools import *

log = getLog("clear_movie_out.log", "CLEAR_MOVIE_OUT")

def error(message):
    print message

def clearOut():
    proxy = ConnProxy.getInstance()

    try:
        # get slot number
        while True:
            try:
                # Input RFID
                rfid_input = raw_input("Please enter RFID(\"a\" for abort):")
                if rfid_input.lower() == "a":
                    os.abort()
                #if not sn_input.isdigit():
                #    error("The input value is wrong.")
                #    continue
                rfid = rfid_input
                # get trs info
                sql = "SELECT id, rfid, title, out_time, price_plan, " \
                      "price_plan_text, sales_tax, cc_display " \
                      "FROM transactions WHERE state='open' " \
                      "AND rfid=?;"
                row = proxy.mkcDb.query(sql, "one", (rfid, ))
                if row is None:
                    error("The disc is not found in \"Movies Out\" List.")
                    continue
                trsId, rfid, title, outTime, pricePlan, pricePlanText, rentalTax, ccName = row
                print "The cc name: %s\nout time: %s\nprice plan:%s" % \
                      (ccName, outTime, pricePlanText.replace("\n", ""))
                break
            except Exception, ex:
                error("An error occured: %s" % str(ex))
                continue

        # get rental days
        while True:
            try:
                # input rental days
                day_input = raw_input("Please mark how many days(\"a\" for abort):")
                if day_input.lower() == "a":
                    os.abort()
                if not day_input.isdigit():
                    error("The input value is wrong.")
                    continue
                days = int(day_input)
                if days < 0:
                    error("The number of days cannot be less than.")
                    continue
                break
            except Exception, ex:
                error("An error occured: %s" % str(ex))
                continue

        while True:
            try:
                print "1. Custom rental fee"
                print "2. Auto calculate by price plan(without coupon)"
                print "3. Abort"
                opts = raw_input("Please select: ")
                if opts not in ("1", "2", "3"):
                    error("The number is out of my range!")
                    continue
                if opts == "3":
                    os.abort()

                inTime = getTimeChange(outTime, day=days)
                needInputFee = True
                if opts == "2":
                    ppe = PricePlanEngine(pricePlan, {"out_time":outTime, "in_time":inTime})
                    fee = ppe.calculate()
                    fee = fmtMoney(fee * (1 + float(rentalTax) / 100))
                    print "The rental fee is: ", fee
                    confirm = raw_input("Are you sure to charge %s(Y/n):" % fee)
                    if confirm.lower() != "n":
                        needInputFee = False

                if needInputFee:
                    # input rental fee
                    fee_input = raw_input("Please mark rental fee:")
                    try:
                        fee_input = float(fee_input)
                    except:
                        error("The input value is wrong.")
                        continue
                    if fee_input < 0:
                        error("Rental fee cannot be less than zero.")
                        continue
                    fee = fmtMoney(fee_input)
                break
            except Exception, ex:
                error("An error occured: %s" % str(ex))
                continue

        # update database
        sqlList = []
        sql = "UPDATE slots SET rfid='', state='empty' WHERE rfid='%s';" % rfid
        sqlList.append(sql)
        sql = "DELETE FROM rfids WHERE rfid='%s';" % rfid
        sqlList.append(sql)
        sql = "DELETE FROM over_capacity_rfids WHERE rfid='%s';" % rfid
        sqlList.append(sql)
        sql = "UPDATE transactions SET state='pending', in_time='%s', amount='%s' where id='%s';"
        sql = sql % (inTime, fee, trsId)
        sqlList.append(sql)
        proxy.mkcDb.updateTrs(sqlList)

        # sync to node
        params = {}
        params["rfid"] = rfid
        params["trs_id"] = trsId
        params["in_time"] = inTime
        params["amount"] = fee
        proxy.syncData("dbSyncClearMovieOut", params)

        print "Cleaning local DB ...... OK"
        print "Push the changes into sync queue ...... OK"
        print "All Done."
        print "The server side should reflect the changes in less than 15 minutes."
        log.info("clearOut: %s, %s, %s, %s" % (rfid, trsId, inTime, fee))
    except Exception, ex:
        log.error("clearOut: %s" % str(ex))
        raise



if __name__ == "__main__":
    clearOut()

