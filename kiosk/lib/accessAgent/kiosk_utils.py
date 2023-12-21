#!/usr/bin/python
""" Kiosk utilities.
## File Name: kiosk_utils.py
##
##  Change Log:
##      2011-05-20 Modified by Tim
##          add apis lock_disc_by_rfid, release_disc_lock_by_rfid, 
##          reserve_disc_by_rfid for reserve API
##      2010-03-29 Modified by Tim
##          1. Change the function _getPickupCode() for #2057.
##          2. Add ms_disc_type for reserveV5().
##
"""

import base64
import time
import os
import sys
import random
from mda import Db
from datetime import datetime, timedelta
from agent_config import *

class LinuxCmd(object):
    """ Execute Linux Command.
    e.g. lc = LinuxCmd()
         lc.execute("ls") # Return the result of ls.
         lc.execute("pkill python", True)  # Return '0' or '1'.
    """

    def __init__(self):
        pass

    def execute(self, cmd, noResult=False):
        """ Execute a linux command line.
        @Params: cmd(String): Command line
                 noResult(Boolean): True: Return '0'(Success) or '1'(Failure)
                                    False: Return the result of cmd.
        @Return: '0', '1', "success" or "".
        """
        w = None
        r = None
        result = ""
        try:
            if noResult:
                result = os.system(cmd)
                result = str(result)
            else:
                w, r = os.popen2(cmd)
                result = r.read()
        except Exception, ex:
            result = "Error when execute cmd(%s): %s" % (cmd, str(ex))

        # Close the object handler.
        if hasattr(w, "close"):
            w.close()
        if hasattr(r, "close"):
            r.close()
        return result

class TimeUtils(object):
    @staticmethod
    def time_format():
        return '%Y-%m-%d %H:%M:%S'

    @staticmethod
    def time_string_to_datetime(time_str):
        try:
            return datetime.strptime(time_str, TimeUtils.time_format())
        except Exception, ex:
            return None

    @staticmethod
    def get_current_time():
        return datetime.now().strftime(TimeUtils.time_format())

    @staticmethod
    def get_expired_lock_time():
        seconds_delta = 60*10
        return datetime.now() - timedelta(seconds=seconds_delta)


class RFIDObject(object):
    def __init__(self, rfid=None):
        self.rfid = rfid
        self.state = ''
        self.upc = ''
        self.category_id = ''
        self.price_plan_dynamic = 0
        self.lock_time = None
        self.lock_by = None
        self.price_plan_id = None
        self.sales_price = None

    @property
    def is_in_available_status(self):
        return self.state in ('in', 'unload')

    @property
    def is_in_lock_status(self):
        return self.state in ('in_lock', 'unload_lock')

    @property
    def can_lock(self):
        if self.is_in_lock_status:
            return (not self.lock_time
                    or self.lock_time < TimeUtils.get_expired_lock_time())
        return self.is_in_available_status

    @property
    def is_dynamic_price_plan(self):
        return str(self.price_plan_dynamic) == "1"

    def is_valid_lock_owner(self, owner):
        return (self.is_in_lock_status 
                and str(self.lock_by) == str(owner))

    @property
    def can_release(self):
        return self.is_in_lock_status

    def get_lock_state(self):
        return self.get_release_state() + '_lock'

    def get_release_state(self):
        return self.state.replace('_lock', '')


class UPCObject(object):
    def __init__(self, upc=None):
        self.upc = upc
        self.genre = ''
        self.dvd_version = ''
        self.dvd_release_date = ''
        self.title = ''

    @property
    def is_game(self):
        return self.genre in ("games", "game")

    @property
    def is_blue_ray(self):
        dv1 = self.dvd_version.lower().find("blu")
        dv2 = self.dvd_version.lower().find("ray")
        return (dv1>=0 and dv2>=0 and dv2-dv1 == 4)

    def get_dvd_version(self):
        if self.is_game:
            return "Games"
        elif self.is_blue_ray:
            return "Blu-ray"
        return "DVD"



class KioskUtils(object):
    def __init__(self, kioskId="", log=None):
        self.kioskId = kioskId
        self.log = log

    def __del__(self):
        pass

    def callback(self, *p, **pp):
        #print "GOOD*****GOT Callback", str1
        return "Reply: I'm kiosk %s." % self.kioskId

    def _getDbPath(self, dbName):
        dbPaths = {"mkc":MKC_DB_PATH,
                   "upc":UPC_DB_PATH,
                   "newupc":NEW_UPC_DB_PATH,
                   "media":MEDIA_DB_PATH,
                   "sync":SYNC_DB_PATH}
        return dbPaths[dbName.lower()]

    def query(self, dbName, sql, fetch='all', params=()):
        db = Db(self._getDbPath(dbName))
        result = db.query(sql, fetch, params)
        del db
        return result

    def update(self, dbName, sql, params=()):
        db = Db(self._getDbPath(dbName))
        newId = db.update(sql, params)
        del db
        return newId

    def updateMany(self, dbName, sql, params=[]):
        db = Db(self._getDbPath(dbName))
        db.updateMany(sql, params)
        del db
        return

    def updateTrs(self, dbName, sqlList=[]):
        db = Db(self._getDbPath(dbName))
        db.updateTrs(sqlList)
        del db
        return

    def executeScript(self, dbName, sql):
        db = Db(self._getDbPath(dbName))
        db.executeScript(sql)
        del db
        return

    def isOnline(self):
        print "==========================isOnline:return"
        return "1"

    def _getPickupCode(self, ccId=0):
        """ The pickup code is formed by 6 digits.
        """
        code = ""
        db = Db(self._getDbPath("mkc"))
        # get the reserved pickup code of the customer
        sql = "SELECT pickup_code FROM reservations WHERE cc_id=? " \
              "AND state='reserved';"
        row = db.query(sql, "one", (ccId, ))
        if row and row[0]:
            code, = row
        if not code: # check the pickup code
            sql = "SELECT id FROM reservations WHERE pickup_code=?;"
            while not code:
                code = str(random.randrange(100000, 999999))
                row = db.query(sql, "one", (code, ))
                if row and row[0]:
                    code = ""
        else:
            pass
        del db
        return code

    def reserve(self, rfid, upclist, acctId, amount, gene, reserveMethod,
                cardNum, nameOnCard, expdate, trsCode, trsMsg, oid, memberId,
                preauthMethod, ccId=0):
        status = 0
        msg = ""
        pricePlan = ""
        upgId = 0
        reserveId = 0
        reserveTime = ""
        upc = ""
        db = None
        try:
            # Check the rental lock.
            rentalLock = True
            sql = "SELECT value FROM config WHERE variable='rental_lock';"
            db = Db(self._getDbPath("mkc"))
            row = db.query(sql, "one")
            if row and row[0] == "no":
                rentalLock = False

            # Check if the dvd release date of the upc is OK.
            db = Db(self._getDbPath("upc"))
            upcstr = "(%s)" % ",".join("'%s'"%u for u in upclist)
            sql = "SELECT upc FROM upc WHERE upc IN %s " % upcstr
            if rentalLock:
                dateNow = time.strftime("%Y-%m-%d 23:59:59")
                sql += "AND dvd_release_date<='%s' "%dateNow
            sql += ";"
            rows = db.query(sql)
            if rows:
                upcstr = "(%s)" % ",".join("'%s'"%u for u, in rows)

                db = Db(self._getDbPath("mkc"))
                # Get rfid by upc.
                sql = "SELECT r.rfid, p.data_text, r.upc FROM rfids as r," \
                      "price_plans as p,slots as s WHERE r.rfid=s.rfid " \
                      "AND r.price_plan_id=p.id AND r.state IN " \
                      "('in', 'unload') AND upc IN %s " \
                      "ORDER BY s.id DESC LIMIT 1;" % upcstr
                row = db.query(sql, "one")
                if row:
                    rfid, pricePlan, upc = row

                    display = "%s (%s)" % (nameOnCard, cardNum[-4:])

                    if ccId=="":
                        # Add to cc table.
                        cardNumEn = base64.b64encode(cardNum)
                        sql = "select id from cc where number=?;"
                        row = db.query(sql, "one", (cardNumEn, ))
                        if row:
                            ccId = row[0]
                        else:
                            sql = "insert into cc(number, name, expdate, track1," \
                                  " track2, display, member_id) values(?,?,?,?,?,?,?);"
                            p = (cardNumEn, nameOnCard, expdate, "", "", display, memberId)
                            ccId = db.update(sql, p)
                    else:
                        # Global cc.
                        sql = "SELECT id FROM cc WHERE id=?;"
                        row = db.query(sql, "one", (ccId, ))
                        if row:
                            # Update info.
                            sql = "UPDATE cc SET id=:cc_id "
                            if nameOnCard:
                                sql += ",name=:name "
                            if display:
                                sql += ",display=:display "
                            sql += "WHERE id=:cc_id;"
                            db.update(sql, {"cc_id":ccId, "name":nameOnCard, "display":display})
                        else:
                            # Insert info.
                            sql = "INSERT INTO cc(id, name, display) VALUES(?,?,?);"
                            db.update(sql, (ccId, nameOnCard, display))
                    # Add to preauthq.
                    reserveTime = time.strftime("%Y-%m-%d %H:%M:%S")
                    preauthqId = ""
                    # Add to upg.
                    sql = "insert into upg(acct_id, pq_id, type, oid, amount," \
                          " cc_id, result_code, result_msg, time, preauth_method," \
                          " notes) values(?,?,?,?,?,?,?,?,?,?,?);"
                    p = (acctId, preauthqId, "PREAUTH", oid, amount, ccId, \
                         trsCode, trsMsg, reserveTime, preauthMethod, self.kioskId)
                    upgId = db.update(sql, p)

                    sqls = []
                    # Update the rfids and insert into reservations.
                    sql = "update rfids set state='reserved' where rfid='%s';"%rfid
                    sqls.append(sql)
                    # Add to reservations.
                    sql = "insert into reservations(rfid, cc_id, reserve_time," \
                          " reserve_method, gene, upg_id) values('%s', '%s', " \
                          "'%s', '%s', '%s', '%s');"%(rfid, ccId, reserveTime, \
                                                      reserveMethod, gene, upgId)
                    sqls.append(sql)
                    db.updateTrs(sqls)
                    # Get reserve id.
                    sql = "SELECT id FROM reservations WHERE rfid=? AND cc_id=? AND " \
                          "reserve_time=? AND upg_id=? AND state='reserved';"
                    row = db.query(sql, "one", (rfid, ccId, reserveTime, upgId))
                    reserveId, = row
                    status = 1
                else:
                    status = 2
            else:
                status = 3
        except Exception, ex:
            if upgId!=0:
                try:
                    sql = "DELETE FROM upg WHERE id=?;"
                    db = Db(self._getDbPath("mkc"))
                    db.update(sql, (upgId, ))
                except Exception, ex:
                    print ex
            status = 0
            msg = "Error when reserve '%s': %s" % (rfid, str(ex))
            self.log.error(msg)
        del db

        return status, msg, ccId, upgId, reserveTime, pricePlan, rfid, upc, reserveId

    def reserveV2(self, params):
        """
        @Params: params(dict): {"acct_id":xxx,
                                "amount":xxx,
                                "cc_id":xxx,
                                "card_num":xxx,
                                "name_on_card":xxx,
                                "exp_date":xxx,
                                "card_display":xxx,
                                "oid":xxx,
                                "trs_code":xxx,
                                "trs_msg":xxx,
                                "member_id":xxx,
                                "reserve_method":xxx,
                                "preauth_method":xxx,
                                "shopping_cart":[{"upc_list":[],
                                                  "gene":xxx,
                                                  "movie_id":xxx,
                                                  "coupon_code":xxx,
                                                  "coupon_plan":xxx,
                                                  "coupon_text":xxx,}],}
        @Return: result(dict):
        """
        result = {}
        status = 0
        msg = ""
        pricePlan = ""
        reserveId = 0
        db = None
        try:
            upgId = 0
            result["status"] = 0
            reserveTime = time.strftime("%Y-%m-%d %H:%M:%S")
            result["reserve_time"] = reserveTime
            # Check the rental lock.
            rentalLock = True
            sql = "SELECT value FROM config WHERE variable='rental_lock';"
            db = Db(self._getDbPath("mkc"))
            row = db.query(sql, "one")
            if row and row[0] == "no":
                rentalLock = False

            # Add the cc into cc table.
            # Global cc.
            sql = "SELECT id FROM cc WHERE id=?;"
            row = db.query(sql, "one", (params["cc_id"], ))
            if row:
                # Update info.
                sql = "UPDATE cc SET id=:cc_id "
                if params["name_on_card"]:
                    sql += ",name=:name "
                if params["card_display"]:
                    sql += ",display=:display "
                sql += "WHERE id=:cc_id;"
                db.update(sql, {"cc_id":params["cc_id"],
                                "name":params["name_on_card"],
                                "display":params["card_display"]})
            else:
                # Insert info.
                sql = "INSERT INTO cc(id, name, display) VALUES(?,?,?);"
                db.update(sql, (params["cc_id"],
                                params["name_on_card"],
                                params["card_display"],))

            # Add upg into upg table.
            preauthqId = ""
            # Add to upg.
            sql = "insert into upg(acct_id, pq_id, type, oid, " \
                  "amount, cc_id, result_code, result_msg, time, " \
                  "preauth_method, notes) " \
                  "values(?,?,?,?,?,?,?,?,?,?,?);"
            p = (params["acct_id"], preauthqId, "PREAUTH", \
                 params["oid"], params["amount"], params["cc_id"], \
                 params["trs_code"], params["trs_msg"], \
                 reserveTime, params["preauth_method"], self.kioskId)
            upgId = db.update(sql, p)
            result["upg_id"] = upgId

            # Check if the dvd release date of the upc is OK.
            result["shopping_cart"] = []
            for itm in params["shopping_cart"]:
                tmp = {}
                tmp.update(itm)
                tmp["status"] = 0
                tmp["msg"] = ""
                rfid = ""
                try:
                    db = Db(self._getDbPath("upc"))
                    upcstr = "(%s)" % ",".join("'%s'"%u for u in itm["upc_list"])
                    sql = "SELECT upc FROM upc WHERE upc IN %s " % upcstr
                    if rentalLock:
                        dateNow = time.strftime("%Y-%m-%d 23:59:59")
                        sql += "AND dvd_release_date<='%s' "%dateNow
                    sql += ";"
                    rows = db.query(sql)

                    if rows:
                        upcstr = "(%s)" % ",".join("'%s'"%u for u, in rows)

                        db = Db(self._getDbPath("mkc"))
                        # Get rfid by upc.
                        sql = "SELECT r.rfid, p.data_text, r.upc, r.title, " \
                              "r.genre, p.data, r.price_plan_dynamic, s.id " \
                              "FROM rfids as r, price_plans as p, " \
                              "slots as s WHERE r.rfid=s.rfid AND " \
                              "r.price_plan_id=p.id AND r.state IN ('in', " \
                              "'unload') AND upc IN %s ORDER BY s.id DESC " \
                              "LIMIT 1;" % upcstr
                        row = db.query(sql, "one")
                        if row:
                            rfid, pricePlanText, upc, title, genre, pricePlan, \
                            dynamic, slotId = row
                            # Get dynamic price plan.
                            if str(dynamic) == "1":
                                weekday = time.strftime("%A")
                                sql = "SELECT price_plan, price_plan_text " \
                                      "FROM price_plans_week WHERE title LIKE ?;"
                                row = db.query(sql, "one", (weekday, ))
                                dypricePlan, dypricePlanText = "", ""
                                if row:
                                    dypricePlan, dypricePlanText = row
                                if dypricePlan:
                                    pricePlan = dypricePlan
                                if dypricePlanText:
                                    pricePlanText = dypricePlanText

                            trs = []
                            # Update the rfids and insert into reservations.
                            sql = "update rfids set state='reserved' where " \
                                  "rfid=?;"
                            trs.append({"sql":sql, "params":(rfid, )})
                            # Add to reservations.
                            sql = "insert into reservations(rfid, cc_id, " \
                                  "reserve_time, reserve_method, gene, upg_id," \
                                  "title, genre, upc, price_plan, " \
                                  "price_plan_text, coupon_code, coupon_plan," \
                                  "coupon_text, slot_id) values(?,?,?,?,?,?,?," \
                                  "?,?,?,?,?,?,?,?);"
                            p = (rfid, params["cc_id"], reserveTime, \
                                params["reserve_method"], itm["gene"], upgId,\
                                title, genre, upc, pricePlan, pricePlanText, \
                                itm["coupon_code"], itm["coupon_plan"], \
                                itm["coupon_text"], slotId)
                            trs.append({"sql":sql, "params": p})
                            db.updateTrs2(trs)
                            # Get reserve id.
                            sql = "SELECT id FROM reservations WHERE rfid=? " \
                                  "AND cc_id=? AND reserve_time=? AND upg_id=? " \
                                  "AND state='reserved';"
                            row = db.query(sql, "one", (rfid, params["cc_id"], \
                                                    reserveTime, upgId))
                            reserveId, = row
                            tmp["status"] = 1
                            tmp["rfid"] = rfid
                            tmp["upc"] = upc
                            tmp["title"] = title
                            tmp["genre"] = genre
                            tmp["reserve_id"] = reserveId
                            tmp["price_plan_text"] = pricePlanText
                            tmp["price_plan"] = pricePlan
                            tmp["slot_id"] = slotId
                            tmp["coupon_code"] = itm["coupon_code"]
                            tmp["coupon_plan"] = itm["coupon_plan"]
                            tmp["coupon_text"] = itm["coupon_text"]
                        else:
                            # No disc can be reserved.
                            tmp["status"] = 2
                    else:
                        # No upc can be reserved.
                        tmp["status"] = 3
                except Exception, ex:
                    tmp["status"] = 0
                    tmp["msg"] = "Error when reserve the disc: %s" % ex
                result["shopping_cart"].append(tmp)
            result["status"] = 1
            result["msg"] = "Reserve successfully."
        except Exception, ex:
            self.log.error("Error when reserve %s: %s"%(params, ex))
            if upgId!=0:
                try:
                    sql = "DELETE FROM upg WHERE id=?;"
                    db = Db(self._getDbPath("mkc"))
                    db.update(sql, (upgId, ))
                except Exception, ex:
                    print ex
            result["status"] = 0
            result["msg"] = "Error when reserve the shopping cart: %s" % ex
        del db

        return result

    def reserveV3(self, params):
        """
        @Params: params(dict): {"acct_id":xxx,
                                "amount":xxx,
                                "cc_id":xxx,
                                "card_num":xxx,
                                "name_on_card":xxx,
                                "exp_date":xxx,
                                "card_display":xxx,
                                "oid":xxx,
                                "trs_code":xxx,
                                "trs_msg":xxx,
                                "member_id":xxx,
                                "reserve_method":xxx,
                                "preauth_method":xxx,
                                "shopping_cart":[{"upc_list":[],
                                                  "gene":xxx,
                                                  "movie_id":xxx,
                                                  "coupon_code":xxx,
                                                  "coupon_plan":xxx,
                                                  "coupon_text":xxx,
                                                  "pickup_code":xxx,}],}
        @Return: result(dict):
        """
        result = {}
        status = 0
        msg = ""
        pricePlan = ""
        reserveId = 0
        db = None
        try:
            upgId = 0
            result["status"] = 0
            reserveTime = time.strftime("%Y-%m-%d %H:%M:%S")
            result["reserve_time"] = reserveTime
            # Check the rental lock.
            rentalLock = True
            sql = "SELECT value FROM config WHERE variable='rental_lock';"
            db = Db(self._getDbPath("mkc"))
            row = db.query(sql, "one")
            if row and row[0] == "no":
                rentalLock = False

            # Add the cc into cc table.
            # Global cc.
            sql = "SELECT id FROM cc WHERE id=?;"
            row = db.query(sql, "one", (params["cc_id"], ))
            if row:
                # Update info.
                sql = "UPDATE cc SET id=:cc_id "
                if params["name_on_card"]:
                    sql += ",name=:name "
                if params["card_display"]:
                    sql += ",display=:display "
                sql += "WHERE id=:cc_id;"
                db.update(sql, {"cc_id":params["cc_id"],
                                "name":params["name_on_card"],
                                "display":params["card_display"]})
            else:
                # Insert info.
                sql = "INSERT INTO cc(id, name, display) VALUES(?,?,?);"
                db.update(sql, (params["cc_id"],
                                params["name_on_card"],
                                params["card_display"],))

            # Add upg into upg table.
            preauthqId = ""
            # Add to upg.
            sql = "insert into upg(acct_id, pq_id, type, oid, " \
                  "amount, cc_id, result_code, result_msg, time, " \
                  "preauth_method, notes) " \
                  "values(?,?,?,?,?,?,?,?,?,?,?);"
            p = (params["acct_id"], preauthqId, "PREAUTH", \
                 params["oid"], params["amount"], params["cc_id"], \
                 params["trs_code"], params["trs_msg"], \
                 reserveTime, params["preauth_method"], self.kioskId)
            upgId = db.update(sql, p)
            result["upg_id"] = upgId

            # Check if the dvd release date of the upc is OK.
            result["shopping_cart"] = []
            for itm in params["shopping_cart"]:
                pickupCode = self._getPickupCode(params["cc_id"])
                tmp = {}
                tmp.update(itm)
                tmp["status"] = 0
                tmp["msg"] = ""
                tmp["pickup_code"] = ""
                rfid = ""
                try:
                    db = Db(self._getDbPath("upc"))
                    upcstr = "(%s)" % ",".join("'%s'"%u for u in itm["upc_list"])
                    sql = "SELECT upc FROM upc WHERE upc IN %s " % upcstr
                    if rentalLock:
                        dateNow = time.strftime("%Y-%m-%d 23:59:59")
                        sql += "AND dvd_release_date<='%s' "%dateNow
                    sql += ";"
                    rows = db.query(sql)
                    if rows:
                        upcstr = "(%s)" % ",".join("'%s'"%u for u, in rows)

                        db = Db(self._getDbPath("mkc"))
                        # Get rfid by upc.
                        sql = "SELECT r.rfid, p.data_text, r.upc, r.title, " \
                              "r.genre, p.data, r.price_plan_dynamic, s.id, " \
                              "r.category_id " \
                              "FROM rfids as r, price_plans as p, " \
                              "slots as s WHERE r.rfid=s.rfid AND " \
                              "r.price_plan_id=p.id AND r.state IN ('in', " \
                              "'unload') AND upc IN %s ORDER BY s.id DESC " \
                              "LIMIT 1;" % upcstr
                        row = db.query(sql, "one")
                        if row:
                            rfid, pricePlanText, upc, title, genre, pricePlan, \
                            dynamic, slotId, categoryId = row
                            # Get dynamic price plan.
                            if str(dynamic) == "1":
                                weekday = time.strftime("%A")
                                sql = "SELECT price_plan, price_plan_text " \
                                      "FROM price_plans_week WHERE title LIKE ?;"
                                row = db.query(sql, "one", (weekday, ))
                                dypricePlan, dypricePlanText = "", ""
                                if row:
                                    dypricePlan, dypricePlanText = row
                                if dypricePlan:
                                    pricePlan = dypricePlan
                                if dypricePlanText:
                                    pricePlanText = dypricePlanText

                            # Check category price plan for the disc.
                            if str(categoryId) != "":
                                sql = "SELECT price_plan_id FROM category " \
                                      "WHERE id=?;"
                                row = db.query(sql, "one", (categoryId, ))
                                if row and str(row[0]) != "":
                                    cppid = row[0] # category price plan id
                                    sql = "SELECT data, data_text " \
                                          "FROM price_plans " \
                                          "WHERE id=?;"
                                    row = db.query(sql, "one", (cppid, ))
                                    if row and row[0] and row[1]:
                                        pricePlan, pricePlanText = row

                            trs = []
                            # Update the rfids and insert into reservations.
                            sql = "update rfids set state='reserved' where " \
                                  "rfid=?;"
                            trs.append({"sql":sql, "params":(rfid, )})
                            # Add to reservations.
                            sql = "insert into reservations(rfid, cc_id, " \
                                  "reserve_time, reserve_method, gene, upg_id," \
                                  "title, genre, upc, price_plan, " \
                                  "price_plan_text, coupon_code, coupon_plan," \
                                  "coupon_text, slot_id, pickup_code) " \
                                  "values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);"
                            p = (rfid, params["cc_id"], reserveTime, \
                                params["reserve_method"], itm["gene"], upgId,\
                                title, genre, upc, pricePlan, pricePlanText, \
                                itm["coupon_code"], itm["coupon_plan"], \
                                itm["coupon_text"], slotId, pickupCode)
                            trs.append({"sql":sql, "params": p})
                            db.updateTrs2(trs)
                            # Get reserve id.
                            sql = "SELECT id FROM reservations WHERE rfid=? " \
                                  "AND cc_id=? AND reserve_time=? AND upg_id=? " \
                                  "AND state='reserved';"
                            row = db.query(sql, "one", (rfid, params["cc_id"], \
                                                    reserveTime, upgId))
                            reserveId, = row
                            tmp["status"] = 1
                            tmp["rfid"] = rfid
                            tmp["upc"] = upc
                            tmp["title"] = title
                            tmp["genre"] = genre
                            tmp["reserve_id"] = reserveId
                            tmp["price_plan_text"] = pricePlanText
                            tmp["price_plan"] = pricePlan
                            tmp["slot_id"] = slotId
                            tmp["coupon_code"] = itm["coupon_code"]
                            tmp["coupon_plan"] = itm["coupon_plan"]
                            tmp["coupon_text"] = itm["coupon_text"]
                            tmp["pickup_code"] = pickupCode
                        else:
                            # No disc can be reserved.
                            tmp["status"] = 2
                    else:
                        # No upc can be reserved.
                        tmp["status"] = 3
                except Exception, ex:
                    tmp["status"] = 0
                    tmp["msg"] = "Error when reserve the disc: %s" % ex
                result["shopping_cart"].append(tmp)
            result["status"] = 1
            result["msg"] = "Reserve successfully."
        except Exception, ex:
            self.log.error("Error when reserve %s: %s"%(params, ex))
            if upgId!=0:
                try:
                    sql = "DELETE FROM upg WHERE id=?;"
                    db = Db(self._getDbPath("mkc"))
                    db.update(sql, (upgId, ))
                except Exception, ex:
                    print ex
            result["status"] = 0
            result["msg"] = "Error when reserve the shopping cart: %s" % ex
        del db

        return result

    def reserveV4(self, params):
        """
        @Params: params(dict): {"acct_id":xxx,
                                "amount":xxx,
                                "cc_id":xxx,
                                "card_num":xxx,
                                "name_on_card":xxx,
                                "exp_date":xxx,
                                "card_display":xxx,
                                "oid":xxx,
                                "trs_code":xxx,
                                "trs_msg":xxx,
                                "member_id":xxx,
                                "reserve_method":xxx,
                                "preauth_method":xxx,
                                "pickup_code":xxx,
                                "shopping_cart":[{"upc_list":[],
                                                  "gene":xxx,
                                                  "movie_id":xxx,
                                                  "coupon_code":xxx,
                                                  "coupon_plan":xxx,
                                                  "coupon_text":xxx,
                                                  "ms_id":xxx,
                                                  "ms_expr_time":xxx,
                                                  "ms_keep_days":xxx,}],}
        @Return: result(dict):
        """
        result = {}
        status = 0
        msg = ""
        pricePlan = ""
        reserveId = 0
        db = None
        try:
            upgId = 0
            result["status"] = 0
            reserveTime = time.strftime("%Y-%m-%d %H:%M:%S")
            result["reserve_time"] = reserveTime
            # Check the rental lock.
            rentalLock = True
            sql = "SELECT value FROM config WHERE variable='rental_lock';"
            db = Db(self._getDbPath("mkc"))
            row = db.query(sql, "one")
            if row and row[0] == "no":
                rentalLock = False

            # Add the cc into cc table.
            # Global cc.
            sql = "SELECT id FROM cc WHERE id=?;"
            row = db.query(sql, "one", (params["cc_id"], ))
            if row:
                # Update info.
                sql = "UPDATE cc SET id=:cc_id "
                if params["name_on_card"]:
                    sql += ",name=:name "
                if params["card_display"]:
                    sql += ",display=:display "
                sql += "WHERE id=:cc_id;"
                db.update(sql, {"cc_id":params["cc_id"],
                                "name":params["name_on_card"],
                                "display":params["card_display"]})
            else:
                # Insert info.
                sql = "INSERT INTO cc(id, name, display) VALUES(?,?,?);"
                db.update(sql, (params["cc_id"],
                                params["name_on_card"],
                                params["card_display"],))

            # Add upg into upg table.
            preauthqId = ""
            # Add to upg.
            upgId = 0
            if params["oid"]:
                sql = "insert into upg(acct_id, pq_id, type, oid, " \
                      "amount, cc_id, result_code, result_msg, time, " \
                      "preauth_method, notes) " \
                      "values(?,?,?,?,?,?,?,?,?,?,?);"
                p = (params["acct_id"], preauthqId, "PREAUTH", \
                     params["oid"], params["amount"], params["cc_id"], \
                     params["trs_code"], params["trs_msg"], \
                     reserveTime, params["preauth_method"], self.kioskId)
                upgId = db.update(sql, p)
            result["upg_id"] = upgId

            # Check if the dvd release date of the upc is OK.
            result["shopping_cart"] = []
            for itm in params["shopping_cart"]:
                pickupCode = self._getPickupCode(params["cc_id"])
                tmp = {}
                tmp.update(itm)
                tmp["status"] = 0
                tmp["msg"] = ""
                tmp["pickup_code"] = ""
                rfid = ""
                try:
                    db = Db(self._getDbPath("upc"))
                    upcstr = "(%s)" % ",".join("'%s'"%u for u in itm["upc_list"])
                    sql = "SELECT upc FROM upc WHERE upc IN %s " % upcstr
                    if rentalLock:
                        dateNow = time.strftime("%Y-%m-%d 23:59:59")
                        sql += "AND dvd_release_date<='%s' "%dateNow
                    sql += ";"
                    rows = db.query(sql)
                    if rows:
                        upcstr = "(%s)" % ",".join("'%s'"%u for u, in rows)

                        db = Db(self._getDbPath("mkc"))
                        # Get rfid by upc.
                        sql = "SELECT r.rfid, p.data_text, r.upc, r.title, " \
                              "r.genre, p.data, r.price_plan_dynamic, s.id, " \
                              "r.category_id " \
                              "FROM rfids as r, price_plans as p, " \
                              "slots as s WHERE r.rfid=s.rfid AND " \
                              "r.price_plan_id=p.id AND r.state IN ('in', " \
                              "'unload') AND upc IN %s ORDER BY s.id DESC " \
                              "LIMIT 1;" % upcstr
                        row = db.query(sql, "one")
                        if row:
                            rfid, pricePlanText, upc, title, genre, pricePlan, \
                            dynamic, slotId, categoryId = row
                            # Get dynamic price plan.
                            if str(dynamic) == "1":
                                weekday = time.strftime("%A")
                                sql = "SELECT price_plan, price_plan_text " \
                                      "FROM price_plans_week WHERE title LIKE ?;"
                                row = db.query(sql, "one", (weekday, ))
                                dypricePlan, dypricePlanText = "", ""
                                if row:
                                    dypricePlan, dypricePlanText = row
                                if dypricePlan:
                                    pricePlan = dypricePlan
                                if dypricePlanText:
                                    pricePlanText = dypricePlanText

                            # Check category price plan for the disc.
                            if str(categoryId) != "":
                                sql = "SELECT price_plan_id FROM category " \
                                      "WHERE id=?;"
                                row = db.query(sql, "one", (categoryId, ))
                                if row and str(row[0]) != "":
                                    cppid = row[0] # category price plan id
                                    sql = "SELECT data, data_text " \
                                          "FROM price_plans " \
                                          "WHERE id=?;"
                                    row = db.query(sql, "one", (cppid, ))
                                    if row and row[0] and row[1]:
                                        pricePlan, pricePlanText = row

                            trs = []
                            # Update the rfids and insert into reservations.
                            sql = "update rfids set state='reserved' where " \
                                  "rfid=?;"
                            trs.append({"sql":sql, "params":(rfid, )})
                            # Add to reservations.
                            sql = "insert into reservations(rfid, cc_id, " \
                                  "reserve_time, reserve_method, gene, upg_id," \
                                  "title, genre, upc, price_plan, " \
                                  "price_plan_text, coupon_code, coupon_plan," \
                                  "coupon_text, slot_id, pickup_code, ms_id, " \
                                  "ms_keep_days) " \
                                  "values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);"
                            p = (rfid, params["cc_id"], reserveTime, \
                                params["reserve_method"], itm["gene"], upgId,\
                                title, genre, upc, pricePlan, pricePlanText, \
                                itm["coupon_code"], itm["coupon_plan"], \
                                itm["coupon_text"], slotId, pickupCode, \
                                itm["ms_id"], itm["ms_keep_days"])
                            trs.append({"sql":sql, "params": p})
                            db.updateTrs2(trs)
                            # Get reserve id.
                            sql = "SELECT id FROM reservations WHERE rfid=? " \
                                  "AND cc_id=? AND reserve_time=? AND upg_id=? " \
                                  "AND state='reserved';"
                            row = db.query(sql, "one", (rfid, params["cc_id"], \
                                                    reserveTime, upgId))
                            reserveId, = row
                            tmp["status"] = 1
                            tmp["rfid"] = rfid
                            tmp["upc"] = upc
                            tmp["title"] = title
                            tmp["genre"] = genre
                            tmp["reserve_id"] = reserveId
                            tmp["price_plan_text"] = pricePlanText
                            tmp["price_plan"] = pricePlan
                            tmp["slot_id"] = slotId
                            tmp["coupon_code"] = itm["coupon_code"]
                            tmp["coupon_plan"] = itm["coupon_plan"]
                            tmp["coupon_text"] = itm["coupon_text"]
                            tmp["pickup_code"] = pickupCode
                            tmp["ms_id"] = itm["ms_id"]
                            tmp["ms_expr_time"] = itm["ms_expr_time"]
                            tmp["ms_keep_days"] = itm["ms_keep_days"]
                        else:
                            # No disc can be reserved.
                            tmp["status"] = 2
                    else:
                        # No upc can be reserved.
                        tmp["status"] = 3
                except Exception, ex:
                    tmp["status"] = 0
                    tmp["msg"] = "Error when reserve the disc: %s" % ex
                result["shopping_cart"].append(tmp)
            result["status"] = 1
            result["msg"] = "Reserve successfully."
        except Exception, ex:
            self.log.error("Error when reserveV4 %s: %s"%(params, ex))
            if upgId!=0:
                try:
                    sql = "DELETE FROM upg WHERE id=?;"
                    db = Db(self._getDbPath("mkc"))
                    db.update(sql, (upgId, ))
                except Exception, ex:
                    print ex
            result["status"] = 0
            result["msg"] = "Error when reserve the shopping cart: %s" % ex
        del db

        return result

    def reserveV5(self, params):
        """
        @Params: params(dict): {"acct_id":xxx,
                                "amount":xxx,
                                "cc_id":xxx,
                                "card_num":xxx,
                                "name_on_card":xxx,
                                "exp_date":xxx,
                                "card_display":xxx,
                                "oid":xxx,
                                "trs_code":xxx,
                                "trs_msg":xxx,
                                "member_id":xxx,
                                "reserve_method":xxx,
                                "preauth_method":xxx,
                                "pickup_code":xxx,
                                "shopping_cart":[{"upc_list":[],
                                                  "gene":xxx,
                                                  "movie_id":xxx,
                                                  "coupon_code":xxx,
                                                  "coupon_plan":xxx,
                                                  "coupon_text":xxx,
                                                  "ms_id":xxx,
                                                  "ms_expr_time":xxx,
                                                  "ms_keep_days":xxx,
                                                  "ms_disc_type":xxx,}],}
        @Return: result(dict):
        """
        result = {}
        status = 0
        msg = ""
        pricePlan = ""
        reserveId = 0
        db = None
        try:
            upgId = 0
            result["status"] = 0
            reserveTime = time.strftime("%Y-%m-%d %H:%M:%S")
            result["reserve_time"] = reserveTime
            # Check the rental lock.
            rentalLock = True
            sql = "SELECT value FROM config WHERE variable='rental_lock';"
            db = Db(self._getDbPath("mkc"))
            row = db.query(sql, "one")
            if row and row[0] == "no":
                rentalLock = False

            # Add the cc into cc table.
            # Global cc.
            sql = "SELECT id FROM cc WHERE id=?;"
            row = db.query(sql, "one", (params["cc_id"], ))
            if row:
                # Update info.
                sql = "UPDATE cc SET id=:cc_id "
                if params["name_on_card"]:
                    sql += ",name=:name "
                if params["card_display"]:
                    sql += ",display=:display "
                sql += "WHERE id=:cc_id;"
                db.update(sql, {"cc_id":params["cc_id"],
                                "name":params["name_on_card"],
                                "display":params["card_display"]})
            else:
                # Insert info.
                sql = "INSERT INTO cc(id, name, display) VALUES(?,?,?);"
                db.update(sql, (params["cc_id"],
                                params["name_on_card"],
                                params["card_display"],))

            # Add upg into upg table.
            preauthqId = ""
            # Add to upg.
            upgId = 0
            if params["oid"]:
                sql = "insert into upg(acct_id, pq_id, type, oid, " \
                      "amount, cc_id, result_code, result_msg, time, " \
                      "preauth_method, notes) " \
                      "values(?,?,?,?,?,?,?,?,?,?,?);"
                p = (params["acct_id"], preauthqId, "PREAUTH", \
                     params["oid"], params["amount"], params["cc_id"], \
                     params["trs_code"], params["trs_msg"], \
                     reserveTime, params["preauth_method"], self.kioskId)
                upgId = db.update(sql, p)
            result["upg_id"] = upgId

            # Check if the dvd release date of the upc is OK.
            result["shopping_cart"] = []
            for itm in params["shopping_cart"]:
                pickupCode = self._getPickupCode(params["cc_id"])
                tmp = {}
                tmp.update(itm)
                tmp["status"] = 0
                tmp["msg"] = ""
                tmp["pickup_code"] = ""
                rfid = ""
                try:
                    db = Db(self._getDbPath("upc"))
                    upcstr = "(%s)" % ",".join("'%s'"%u for u in itm["upc_list"])
                    sql = "SELECT upc, genre, dvd_version " \
                          "FROM upc WHERE upc IN %s " % upcstr
                    if rentalLock:
                        dateNow = time.strftime("%Y-%m-%d 23:59:59")
                        sql += "AND dvd_release_date<='%s' "%dateNow
                    sql += ";"
                    rows = db.query(sql)
                    if rows:
                        upcstr = "(%s)" % ",".join("'%s'"%u[0] for u in rows)

                        db = Db(self._getDbPath("mkc"))
                        # Get rfid by upc.
                        sql = "SELECT r.rfid, p.data_text, r.upc, r.title, " \
                              "r.genre, p.data, r.price_plan_dynamic, s.id, " \
                              "r.category_id " \
                              "FROM rfids as r, price_plans as p, " \
                              "slots as s WHERE r.rfid=s.rfid AND " \
                              "r.price_plan_id=p.id AND r.state IN ('in', " \
                              "'unload') AND upc IN %s ORDER BY s.id DESC " \
                              "LIMIT 1;" % upcstr
                        row = db.query(sql, "one")
                        if row:
                            rfid, pricePlanText, upc, title, genre, pricePlan, \
                            dynamic, slotId, categoryId = row
                            # Get dynamic price plan.
                            isGame, isBR = False, False
                            dvdversion = "DVD"
                            for u in rows:
                                if str(u[0]) == upc:
                                    isGame = str(u[1]).lower() in ("games", "game")
                                    if isGame:
                                        dvdversion = "Games"
                                        break
                                    dv = str(u[2]).lower()
                                    dv1 = dv.find("blu")
                                    dv2 = dv.find("ray")
                                    if  dv1>=0 and dv2>=0 and dv2-dv1 == 4:
                                        isBR = True
                                        dvdversion = "Blu-ray"
                                    break
                            # check ms for apply disc type
                            if itm["ms_expr_time"] and itm["ms_disc_type"].upper().find(dvdversion.upper()) < 0:
                                # can not use MS
                                itm["ms_id"] = ""
                                itm["ms_expr_time"] = ""
                                itm["ms_keep_days"] = ""
                            if str(dynamic) == "1":
                                weekday = time.strftime("%A")
                                sql = "SELECT price_plan, price_plan_text, " \
                                      "price_plan_br, price_plan_text_br, " \
                                      "price_plan_game, price_plan_text_game " \
                                      "FROM price_plans_week WHERE title LIKE ?;"
                                row = db.query(sql, "one", (weekday, ))
                                dyPP, dyPPT, dyPPBR, dyPPTBR, dyPPG, \
                                dyPPTG = "", "", "", "", "", ""
                                if row:
                                    dyPP, dyPPT, dyPPBR, dyPPTBR, dyPPG, \
                                    dyPPTG = row
                                if isGame:
                                    if dyPPG and dyPPTG:
                                        pricePlan = dyPPG
                                        pricePlanText = dyPPTG
                                elif isBR:
                                    if dyPPBR and dyPPTBR:
                                        pricePlan = dyPPBR
                                        pricePlanText = dyPPTBR
                                else:
                                    if dyPP and dyPPT:
                                        pricePlan = dyPP
                                        pricePlanText = dyPPT

                            # Check category price plan for the disc.
                            if str(categoryId) != "":
                                sql = "SELECT price_plan_id FROM category " \
                                      "WHERE id=?;"
                                row = db.query(sql, "one", (categoryId, ))
                                if row and str(row[0]) != "":
                                    cppid = row[0] # category price plan id
                                    sql = "SELECT data, data_text " \
                                          "FROM price_plans " \
                                          "WHERE id=?;"
                                    row = db.query(sql, "one", (cppid, ))
                                    if row and row[0] and row[1]:
                                        pricePlan, pricePlanText = row

                            trs = []
                            # Update the rfids and insert into reservations.
                            sql = "update rfids set state='reserved' where " \
                                  "rfid=?;"
                            trs.append({"sql":sql, "params":(rfid, )})
                            # Add to reservations.
                            sql = "insert into reservations(rfid, cc_id, " \
                                  "reserve_time, reserve_method, gene, upg_id," \
                                  "title, genre, upc, price_plan, " \
                                  "price_plan_text, coupon_code, coupon_plan," \
                                  "coupon_text, slot_id, pickup_code, ms_id, " \
                                  "ms_keep_days) " \
                                  "values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);"
                            p = (rfid, params["cc_id"], reserveTime, \
                                params["reserve_method"], itm["gene"], upgId,\
                                title, genre, upc, pricePlan, pricePlanText, \
                                itm["coupon_code"], itm["coupon_plan"], \
                                itm["coupon_text"], slotId, pickupCode, \
                                itm["ms_id"], itm["ms_keep_days"])
                            trs.append({"sql":sql, "params": p})
                            db.updateTrs2(trs)
                            # Get reserve id.
                            sql = "SELECT id FROM reservations WHERE rfid=? " \
                                  "AND cc_id=? AND reserve_time=? AND upg_id=? " \
                                  "AND state='reserved';"
                            row = db.query(sql, "one", (rfid, params["cc_id"], \
                                                    reserveTime, upgId))
                            reserveId, = row
                            tmp["status"] = 1
                            tmp["rfid"] = rfid
                            tmp["upc"] = upc
                            tmp["title"] = title
                            tmp["genre"] = genre
                            tmp["reserve_id"] = reserveId
                            tmp["price_plan_text"] = pricePlanText
                            tmp["price_plan"] = pricePlan
                            tmp["slot_id"] = slotId
                            tmp["coupon_code"] = itm["coupon_code"]
                            tmp["coupon_plan"] = itm["coupon_plan"]
                            tmp["coupon_text"] = itm["coupon_text"]
                            tmp["pickup_code"] = pickupCode
                            tmp["ms_id"] = itm["ms_id"]
                            tmp["ms_expr_time"] = itm["ms_expr_time"]
                            tmp["ms_keep_days"] = itm["ms_keep_days"]
                        else:
                            # No disc can be reserved.
                            tmp["status"] = 2
                    else:
                        # No upc can be reserved.
                        tmp["status"] = 3
                except Exception, ex:
                    tmp["status"] = 0
                    tmp["msg"] = "Error when reserve the disc: %s" % ex
                result["shopping_cart"].append(tmp)
            result["status"] = 1
            result["msg"] = "Reserve successfully."
        except Exception, ex:
            self.log.error("Error when reserveV4 %s: %s"%(params, ex))
            if upgId!=0:
                try:
                    sql = "DELETE FROM upg WHERE id=?;"
                    db = Db(self._getDbPath("mkc"))
                    db.update(sql, (upgId, ))
                except Exception, ex:
                    print ex
            result["status"] = 0
            result["msg"] = "Error when reserve the shopping cart: %s" % ex
        del db

        return result
        
    # This version is for supporting the online lock/release disc
    def reserveV6(self, params):
        """
        @Params: params(dict): {"acct_id":xxx,
                                "amount":xxx,
                                "cc_id":xxx,
                                "card_num":xxx,
                                "name_on_card":xxx,
                                "exp_date":xxx,
                                "card_display":xxx,
                                "oid":xxx,
                                "trs_code":xxx,
                                "trs_msg":xxx,
                                "member_id":xxx,
                                "reserve_method":xxx,
                                "preauth_method":xxx,
                                "pickup_code":xxx,
                                "shopping_cart":[{"upcs":xxx,
                                                  "gene":xxx,
                                                  "movie_id":xxx,
                                                  "coupon_code":xxx,
                                                  "coupon_plan":xxx,
                                                  "coupon_text":xxx,
                                                  "ms_id":xxx,
                                                  "ms_expr_time":xxx,
                                                  "ms_keep_days":xxx,
                                                  "ms_disc_type":xxx,}],}
        @Return: result(dict):
        """
        result = {}
        try:
            mkc_DB = self._get_mkcDB()
            upc_DB = self._get_upcDB()
            rental_lock = self._get_rental_lock(mkc_DB)

            result["status"] = 0
            current_time = TimeUtils.get_current_time()
            result["reserve_time"] = current_time
            self._update_cc_information(mkc_DB, params['cc_id'], params['name_on_card'], params['card_display'])
            result["upg_id"] = self._update_upg(mkc_DB, params['oid'], 
                                                params['acct_id'], "", 
                                                params['amount'], params['cc_id'], 
                                                params['trs_code'], params['trs_msg'], 
                                                current_time, params['preauth_method'])

            # Check if the dvd release date of the upc is OK.
            result["shopping_cart"] = []
            pickupCode = self._getPickupCode(params["cc_id"])
            member_id = params['member_id']
            cart_list = params['cart_dict']['cart']
            for shopping_item in params["shopping_cart"]:
                tmp_dict = {"status" : 0, "msg" : "", "pickup_code" : ""}
                tmp_dict.update(shopping_item)
                rfid = None
                if cart_list:
                    rfid = cart_list[0]['rfid']
                try:
                    rfid_obj = self._get_rfid_object(mkc_DB, rfid)
                    can_reserve = False
                    if rfid_obj.can_lock or rfid_obj.is_valid_lock_owner(member_id):
                        self.log.info('can_lock')
                        upc_obj = self._get_upc_object(upc_DB, rfid_obj.upc)
                        if rental_lock:
                            can_reserve = upc_obj.dvd_release_date <= time.strftime("%Y-%m-%d 23:59:59")
                        else:
                            can_reserve = True
                    if can_reserve:
                        self.log.info('can_reserve')
                        pricePlan, pricePlanText = self._get_price_plan(mkc_DB, rfid_obj, upc_obj)
                        dvd_version = upc_obj.get_dvd_version()
                        if shopping_item["ms_expr_time"] and shopping_item["ms_disc_type"].upper().find(dvd_version.upper()) < 0:
                            # can not use MS
                            shopping_item["ms_id"] = ""
                            shopping_item["ms_expr_time"] = ""
                            shopping_item["ms_keep_days"] = ""

                        trs = []
                        slot_id = self._get_slotID_by_rfid(mkc_DB, rfid)
                        # Update the rfids and insert into reservations.
                        sql = "UPDATE rfids SET state='reserved', lock_by='', lock_time =''  WHERE rfid=?;"
                        trs.append({"sql":sql, "params":(rfid, )})
                        # Add to reservations.
                        sql = '''
                                INSERT INTO reservations(rfid, cc_id, 
                                    reserve_time, reserve_method, gene, 
                                    upg_id, title, genre, upc, price_plan,
                                    price_plan_text, coupon_code, coupon_plan,
                                    coupon_text, slot_id, pickup_code, ms_id,
                                    ms_keep_days) 
                                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);
                              '''
                        params_tuple = (rfid, params["cc_id"], 
                                        current_time, params["reserve_method"], shopping_item["gene"], 
                                        result['upg_id'], upc_obj.title, upc_obj.genre, upc_obj.upc, pricePlan, 
                                        pricePlanText, shopping_item["coupon_code"], shopping_item["coupon_plan"], 
                                        shopping_item["coupon_text"], slot_id, pickupCode, 
                                        shopping_item["ms_id"], shopping_item["ms_keep_days"])
                        trs.append({"sql":sql, "params": params_tuple})
                        self.log.info('start the transaction recording...')
                        mkc_DB.updateTrs2(trs)
                        reserveID = self. _get_reservedID(mkc_DB, rfid, params['cc_id'], current_time, result['upg_id'])
                        tmp_dict["status"] = 1
                        tmp_dict["rfid"] = rfid
                        tmp_dict["upc"] = rfid_obj.upc
                        tmp_dict["title"] = upc_obj.title
                        tmp_dict["genre"] = upc_obj.genre
                        tmp_dict["reserve_id"] = reserveID
                        tmp_dict["price_plan_text"] = pricePlanText
                        tmp_dict["price_plan"] = pricePlan
                        tmp_dict["slot_id"] = slot_id
                        tmp_dict["coupon_code"] = shopping_item["coupon_code"]
                        tmp_dict["coupon_plan"] = shopping_item["coupon_plan"]
                        tmp_dict["coupon_text"] = shopping_item["coupon_text"]
                        tmp_dict["pickup_code"] = pickupCode
                        tmp_dict["ms_id"] = shopping_item["ms_id"]
                        tmp_dict["ms_expr_time"] = shopping_item["ms_expr_time"]
                        tmp_dict["ms_keep_days"] = shopping_item["ms_keep_days"]
                    else:
                        tmp_dict["status"] = 3 # No disc can be reserved.
                except Exception, ex:
                    self.log.error("Error when reserveV6 %s: %s"%(params, str(ex)))
                    tmp_dict["status"] = 0
                    tmp_dict["msg"] = "Error when reserve the disc: %s" % ex
                result["shopping_cart"].append(tmp_dict)
            result["status"] = 1
            result["msg"] = "Reserve successfully."
        except Exception, ex:
            self.log.error("Error when reserveV6 %s: %s"%(params, str(ex)))
            if result['upg_id']:
                try:
                    sql = "DELETE FROM upg WHERE id=?;"
                    mkc_DB.update(sql, (result['upg_id'], ))
                except Exception, ex_db:
                    print ex_db
            result["status"] = 0
            result["msg"] = "Error when reserve the shopping cart: %s" % str(ex)
        return result



    def _getDiscType(self, upc):
        """
        @Params: upc(str)
        @Return: discType(str)
        """
        discType = "DVD"
        sql = "SELECT genre, dvd_version FROM upc WHERE upc=?;"
        db = Db(self._getDbPath("upc"))
        row = db.query(sql, "one", (upc, ))
        del db
        if row:
            genre, dvd_version = row
            if str(genre).upper() == "GAMES":
                discType = "Games"
            elif str(dvd_version).upper().find("BLU-RAY") >= 0:
                discType = "Blu-ray"
        return discType

    def _execCmd(self, cmd, noResult=False):
        lc = LinuxCmd()
        return lc.execute(cmd, noResult)

    def getKioskScreenShot(self):
        fileName = time.strftime("%Y-%m-%d_%H%M%S") + ".jpg"
        filePath = os.path.join(USER_ROOT, "kiosk/tmp/", fileName)
        #cmd = "su - mm -c 'DISPLAY=:0.0 /usr/bin/scrot /tmp/%s'" % fileName
        lc = LinuxCmd()
        cmd = "DISPLAY=:0.0 /usr/bin/scrot %s" % filePath
        result = lc.execute(cmd, True)

        content = ""
        if str(result) == "0":
            f = open(filePath)
            content = f.read()
            f.close()
            content = base64.b64encode(content)
        del lc
        return content

    def upgradeSoftware(self, softwareVersion):
        f = open("/tmp/upgrade_version", "w")
        f.write(str(softwareVersion))
        f.close()
        return 1

    ############################################################
    # begin for online lock/release disc
    ############################################################
    
    def lock_disc_by_rfid(self, params):
        """ Lock disc by rfid for reserve.
        @param params(dict): {"rfid": xxx, "user_id": xxx}
        @return: result(dict): {"rfid": xxx, "status": xxx, "msg": xxx,
                                "preauth_amount": xxx, "sale_amount": xxx}
        @rtype: status  0: success
                        1: internal error
                        2: params is invalid
                        3: locked by others
                        4: the rfid does not exist
                        5: the rfid is invalid
        """
        result = {"rfid": params.get("rfid", ""), "status": 1, "msg": "",
                  "preauth_amount": 0, "sale_amount": 0}
        try:
            # check the params
            if params.get("rfid") and params.get("user_id"):
                # get the rfid information
                db = Db(self._getDbPath("mkc"))
                rfid_obj = self._get_rfid_object(db, params["rfid"])
                if not rfid_obj.upc:  # the rfid does not exist
                    result["status"] = 4
                elif rfid_obj.can_lock or rfid_obj.is_valid_lock_owner(params["user_id"]):
                    # check if the rfid could be locked
                    self._lock_rfid(db, params["rfid"], params["user_id"], rfid_obj.get_lock_state())
                    result["status"] = 0
                    result["preauth_amount"] = rfid_obj.sales_price
                    result["sale_amount"] = rfid_obj.sales_price
                elif rfid_obj.is_valid_lock_owner and str(rfid_obj.lock_by) != (params["user_id"]):
                    # the rfid is locked by others
                    result["status"] = 3
                else:  # the rfid is bad
                    result["status"] = 5
            else:
                result["status"] = 2
        except Exception, ex:
            result["status"] = 1
            result["msg"] = str(ex)
        return result
        
    def release_disc_lock_by_rfid(self, params):
        """ Release lock of the rfid for reserve.
        @param: params(dict): {"rfid": xxx, "user_id": xxx}
        @return: result(dict): {"rfid": xxx, "status": xxx, "msg": xxx}
        @rtype: status  0: success
                        1: internal error
                        2: params is invalid
                        3: can not release, locked by others
        """
        result = {"rfid": params.get("rfid", ""), "status": 1, "msg": ""}
        try:
            # check the params
            if params.get("rfid") and params.get("user_id"):
                # 
                db = Db(self._getDbPath("mkc"))
                rfid_obj = self._get_rfid_object(db, params["rfid"])
                if rfid_obj.can_release:
                    if rfid_obj.is_valid_lock_owner(params["user_id"]):
                        self._release_rfid(db, params["rfid"], rfid_obj.get_release_state())
                        result["status"] = 0
                    else:
                        result["status"] = 3
                else:
                    result["status"] = 0
            else:
                result["status"] = 2
        except Exception, ex:
            result["status"] = 1
            result["msg"] = str(ex)
        return result
        
    def reserve_disc_by_rfid(self, params):
        """ Reserve the disc by rfid, it will not check rental lock and rating lock.
        @param params(dict): {"rfid": xxx, "user_id": xxx, "cc_id": xxx,
                              "cc_name": xxx, "cc_display": xxx, "amount": xxx,
                              "oid": xxx, "upg_code": xxx, "upg_msg": xxx,
                              "upg_type": xxx, "gene": xxx, "acct_id": xxx,
                              "user_id": xxx, "coupon_code": xxx, "coupon_plan": xxx,
                              "coupon_text": xxx, "ms_id": xxx, "ms_keep_days": xxx,
                              "reserve_method": xxx,}
        @return: result(dict): {"upg_id": xxx, "status": xxx, "pickup_code": xxx,
                                "msg": xxx, "reserve_time": xxx, "rfid: xxx,
                                "price_plan": xxx, "price_plan_text": xxx,
                                "reserve_id": xxx, "slot_id": xxx, "upc": xxx,
                                "title": xxx, "genre": xxx, }
        @rtype: status  0: success
                        1: internal error
                        2: the rfid can not be reserved
        """
        result = {"status": 1, "upg_id": 0, "pickup_code": "", 
                  "msg": "", "rfid": params.get("rfid", ""),
                  "reserve_id": 0}
        try:
            mkc_db = self._get_mkcDB()
            upc_db = self._get_upcDB()

            current_time = TimeUtils.get_current_time()

            rfid_obj = self._get_rfid_object(mkc_db, params["rfid"])
            upc_obj = self._get_upc_object(upc_db, rfid_obj.upc)
            # chek if the rfid could be reserved
            if rfid_obj.can_lock or rfid_obj.is_valid_lock_owner(params["user_id"]):
                # form the pickup code
                pickup_code = self._getPickupCode(params["cc_id"])
                self._update_cc_information(mkc_db, params["cc_id"], params["cc_name"],
                                            params["cc_display"])
                result["upg_id"] = self._update_upg(mkc_db, params["oid"],
                                                    params["acct_id"], "", 
                                                    params["amount"], params["cc_id"], 
                                                    params["upg_code"], params["upg_msg"], 
                                                    current_time, params.get("preauth_method", "full"),
                                                    params["upg_type"])
                price_plan, price_plan_text = self._get_price_plan(mkc_db, rfid_obj, upc_obj)

                trs = []
                slot_id = self._get_slotID_by_rfid(mkc_db, params["rfid"])
                # Update the rfids and insert into reservations.
                sql = "UPDATE rfids SET state='reserved', lock_by='', lock_time ='' WHERE rfid=?;"
                trs.append({"sql":sql, "params":(params["rfid"], )})
                # Add to reservations.
                sql = '''
                        INSERT INTO reservations(rfid, cc_id, 
                            reserve_time, reserve_method, gene, 
                            upg_id, title, genre, upc, price_plan,
                            price_plan_text, coupon_code, coupon_plan,
                            coupon_text, slot_id, pickup_code, ms_id,
                            ms_keep_days) 
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);
                      '''
                params_tuple = (params["rfid"], params["cc_id"], 
                                current_time, params.get("reserve_method", "web"), 
                                params["gene"], result["upg_id"], upc_obj.title, 
                                upc_obj.genre, upc_obj.upc, price_plan, price_plan_text,
                                params.get("coupon_code", ""), params.get("coupon_plan", ""),
                                params.get("coupon_text", ""), slot_id, pickup_code,
                                params.get("ms_id", ""), params.get("ms_keep_days", ""))
                trs.append({"sql":sql, "params": params_tuple})
                self.log.info('start the transaction recording...')
                mkc_db.updateTrs2(trs)
                reserve_id = self. _get_reservedID(mkc_db, params["rfid"], params["cc_id"], 
                                                  current_time, result['upg_id'])
                result["reserve_time"] = current_time
                result["pickup_code"] = pickup_code
                result["price_plan"] = price_plan
                result["price_plan_text"] = price_plan_text
                result["reserve_id"] = reserve_id
                result["slot_id"] = slot_id
                result["upc"] = rfid_obj.upc
                result["title"] = upc_obj.title
                result["genre"] = upc_obj.genre
                result["status"] = 0
                result["msg"] = "Reserve successfully."
            else:
                result["status"] = 2
        except Exception, ex:
            self.log.error("Error when reserve_disc_by_rfid %s: %s" % (params, ex))
            if result.get("upg_id", ""):
                try:
                    sql = "DELETE FROM upg WHERE id=?;"
                    mkc_db.update(sql, (result['upg_id'], ))
                except Exception, ex_db:
                    print ex_db
            result["status"] = 1
            result["msg"] = "Error when reserve the shopping cart: %s" % str(ex)
        return result

    def lockdisc(self, params):
        self.log.info(str(params))
        result = self._lock_disc_impl(params.get('upc', None),
                                    params.get('lock_by', None),
                                    params.get('sales_price', None))
        self.log.info(result)
        return result


    def releasedisclock(self, params):
        self.log.info(str(params))
        return self._release_disc_lock_impl(params.get('rfid', None),
                                            params.get('lock_by', None))


    def _get_rental_lock(self, mkc_DB):
        sql = "SELECT value FROM config WHERE variable='rental_lock';"
        result = mkc_DB.query(sql, "one")
        return (not result or result[0] != "no")


    def _update_cc_information(self, mkc_DB, cc_id, name_on_card, card_display):
        sql = "SELECT id FROM cc WHERE id=?;"
        row = mkc_DB.query(sql, "one", (cc_id, ))
        if row:
            sql = "UPDATE cc SET id=:cc_id "
            if name_on_card:
                sql += ",name=:name "
            if card_display:
                sql += ",display=:display "
            sql += "WHERE id=:cc_id;"
            mkc_DB.update(sql, {"cc_id":cc_id, "name":name_on_card, "display":card_display})
        else:
            sql = "INSERT INTO cc(id, name, display) VALUES(?,?,?);"
            mkc_DB.update(sql, (cc_id, name_on_card, card_display))


    def _update_upg(self, mkc_DB, oid, acct_id, preauthqId, amount, cc_id, trs_code, 
                    trs_msg, current_time, preauth_method, trs_type="PREAUTH"):
        sql = '''
                INSERT INTO upg(acct_id, pq_id, type, oid, 
                  amount, cc_id, result_code, result_msg, time, 
                  preauth_method, notes) 
                VALUES(?,?,?,?,?,?,?,?,?,?,?);
              '''
        if oid:
            return mkc_DB.update(sql, (acct_id, preauthqId, trs_type, 
                                   oid, amount, cc_id, trs_code, trs_msg,
                                   current_time, preauth_method, self.kioskId))
        else:
            return 0


    def _get_mkcDB(self):
        return Db(self._getDbPath("mkc"))

    def _get_upcDB(self):
        return Db(self._getDbPath("upc"))

    def _get_rfid_object(self, mkc_DB, rfid):
        rfid_obj = RFIDObject(rfid)
        query_sql = '''
                    SELECT upc, state, lock_time, lock_by, category_id, price_plan_dynamic, price_plan_id, sales_price
                    FROM rfids
                    where rfid = '%s';
                    '''
        result_set = mkc_DB.query(query_sql % rfid, "one")
        if result_set:
            upc, state, lock_time, lock_by, category_id, price_plan_dynamic, price_plan_id, sales_price = result_set
            rfid_obj.upc = upc
            rfid_obj.state = str(state).strip().lower()
            rfid_obj.lock_time = TimeUtils.time_string_to_datetime(lock_time)
            rfid_obj.lock_by = lock_by
            rfid_obj.category_id = category_id
            rfid_obj.price_plan_dynamic = price_plan_dynamic
            rfid_obj.price_plan_id = price_plan_id
            rfid_obj.sales_price = sales_price
        return rfid_obj


    def _get_upc_object(self, upc_DB, upc):
        upc_obj = UPCObject(upc)
        query_sql = '''
                    SELECT title, genre, dvd_release_date, dvd_version
                    FROM upc
                    where upc = '%s';
                    '''
        result_set = upc_DB.query(query_sql % upc, "one")
        if result_set:
            title, genre, dvd_release_date, dvd_version = result_set
            upc_obj.title = title
            upc_obj.dvd_release_date = dvd_release_date
            upc_obj.dvd_version = dvd_version
            upc_obj.genre = genre
        return upc_obj


    def _get_price_plan(self, mkc_DB, rfid_obj, upc_obj):
        def get_price_plan_by_category(mkc_DB, category_id):
            sql = "SELECT price_plan_id FROM category WHERE id=?;"
            row = mkc_DB.query(sql, "one", (category_id, ))
            if row and str(row[0]) != "":
                cppid = row[0] # category price plan id
                sql = "SELECT data, data_text FROM price_plans WHERE id=?;"
                row = mkc_DB.query(sql, "one", (cppid, ))
                if row and row[0] and row[1]:
                    return row
            return None, None

        def get_dynamic_price_plan(mkc_DB, upc_obj):
            weekday = time.strftime("%A")
            sql = '''
                    SELECT price_plan, price_plan_text,
                      price_plan_br, price_plan_text_br, 
                      price_plan_game, price_plan_text_game
                    FROM price_plans_week WHERE title LIKE ?;
                  '''
            row = mkc_DB.query(sql, "one", (weekday, ))
            if row:
                dyPP, dyPPT, dyPPBR, dyPPTBR, dyPPG, dyPPTG = row
            else:
                dyPP, dyPPT, dyPPBR, dyPPTBR, dyPPG, dyPPTG = None, None, None, None, None, None

            if upc_obj.is_game:
                return dyPPG, dyPPTG 
            elif upc_obj.is_blue_ray:
                return dyPPBR, dyPPTBR
            else:
                return dyPP, dyPPT
            return None, None


        sql = "SELECT data, data_text FROM price_plans WHERE id = '%s';"
        result = mkc_DB.query(sql % rfid_obj.price_plan_id, "one")
        pricePlan, pricePlanText = '', ''
        if result:
            pricePlan, pricePlanText = result
            if rfid_obj.is_dynamic_price_plan:
                plan, plan_text = get_dynamic_price_plan(mkc_DB, upc_obj)
                if plan and plan_text:
                    pricePlan, pricePlanText = plan, plan_text
            if rfid_obj.category_id:
                plan, plan_text = get_price_plan_by_category(mkc_DB, rfid_obj.category_id)
                if plan and plan_text:
                    pricePlan, pricePlanText = plan, plan_text
        return pricePlan, pricePlanText



    def _lock_rfid(self, mkc_DB, rfid, lock_by, lock_state):
        lock_sql = ''' 
                     UPDATE rfids 
                     SET lock_by = '%s',
                         lock_time = '%s',
                         state = '%s'
                     WHERE rfid = '%s';
                    '''
        mkc_DB.update(lock_sql % (lock_by, TimeUtils.get_current_time(), lock_state, rfid))

    def _get_slotID_by_rfid(self, mkc_DB, rfid):
        sql = "SELECT id FROM slots WHERE rfid ='%s';"
        result = mkc_DB.query(sql, "one")
        if result:
            slot_id, = result
        else:
            slot_id = None
        return slot_id

    def _get_reservedID(self, mkc_DB, rfid, cc_id, reserve_time, upg_id):
        sql = '''
                SELECT id 
                FROM reservations 
                WHERE rfid=? 
                  AND cc_id=? 
                  AND reserve_time=? 
                  AND upg_id=? 
                  AND state='reserved';
              '''
        row = mkc_DB.query(sql, "one", (rfid, cc_id, reserve_time, upg_id))
        reserveID, = row
        return reserveID


    def _release_rfid(self, mkc_DB, rfid, release_state):
        release_sql = ''' 
                         UPDATE rfids 
                         SET lock_by = NULL,
                             lock_time = NULL,
                             state = '%s'
                         WHERE rfid = '%s';
                        '''
        mkc_DB.update(release_sql % (release_state, rfid))


    def _get_rfid_object_list_by_upc(self, mkc_DB, upc):
        obj_list =[]
        query_sql = '''
                    SELECT rfid, state, lock_time, lock_by, category_id, price_plan_dynamic, price_plan_id, sales_price
                    FROM rfids
                    where upc = '%s';
                    '''
        result_set = mkc_DB.query(query_sql % upc)
        for item in result_set:
            rfid, state, lock_time, lock_by, category_id, price_plan_dynamic, price_plan_id, sales_price = item
            rfid_obj = RFIDObject(rfid)
            rfid_obj.upc = upc
            rfid_obj.state = str(state).strip().lower()
            rfid_obj.lock_time = TimeUtils.time_string_to_datetime(lock_time)
            rfid_obj.lock_by = lock_by
            rfid_obj.category_id = category_id
            rfid_obj.price_plan_dynamic = price_plan_dynamic
            rfid_obj.price_plan_id = price_plan_id
            rfid_obj.sales_price = sales_price
            obj_list.append(rfid_obj)
        return obj_list


    def _get_available_rfid_object_by_upc(self, mkc_DB, upc, lock_by, sales_price=None):
        if sales_price is not None:
            sales_price = int(round(float(sales_price), 2)*100)
        if type(upc) == type(""):
            upc = [upc]
        for u in upc:
            for rfid_obj in self._get_rfid_object_list_by_upc(mkc_DB, u):
                if rfid_obj.can_lock or rfid_obj.is_valid_lock_owner(lock_by):
                    if (sales_price is not None) and (int(round(float(rfid_obj.sales_price),2)*100) != sales_price):
                        continue
                    return rfid_obj
        return None


    def _clear_clock_by_owner(self, mkc_DB, owner):
        sql = '''
                UPDATE rfids SET lock_by='', lock_time='', state=substr(state, 0, length(state) - 5) 
                WHERE lock_time <> '' 
                    AND lock_time IS NOT NULL 
                    AND state LIKE '%%_lock' 
                    AND lock_by = '%s';
               '''
        mkc_DB.update(sql % owner)


    def _lock_disc_impl(self, upc, lock_by, sales_price=None):
        if not (upc and lock_by):
            return {'error_code': 101,'error_desc': 'Invalid parameters!'}

        try:
            mkc_DB = self._get_mkcDB()
            self._clear_clock_by_owner(mkc_DB, lock_by)
            rfid_obj = self._get_available_rfid_object_by_upc(mkc_DB, upc, lock_by, sales_price)
            if rfid_obj:
                self._lock_rfid(mkc_DB, rfid_obj.rfid, lock_by, rfid_obj.get_lock_state())
                upc_DB = self._get_upcDB()
                upc_obj = self._get_upc_object(upc_DB, rfid_obj.upc)
                pricePlan, pricePlanText = self._get_price_plan(mkc_DB, rfid_obj, upc_obj)
                data = {'sales_price':rfid_obj.sales_price, 
                        'price_plan':pricePlan,
                        'price_plan_text':pricePlanText,
                        'dvd_version':upc_obj.get_dvd_version(),
                        'rfid':rfid_obj.rfid}
            else:
                return {'error_code': 102,'error_desc': 'no available!'}
        except Exception, ex:
            return {'error_code': 1,'error_desc': 'system error : %s '%str(ex)}
        else:
            return {'error_code': 0,'error_desc': 'successful', 'data':data}


    def _release_disc_lock_impl(self, rfid, lock_by):
        if not (rfid and lock_by):
            return {'error_code': 201,'error_desc': 'Invalid parameters!'}

        try:
            mkc_DB = self._get_mkcDB()
            rfid_obj = self._get_rfid_object(mkc_DB, rfid)
            if rfid_obj.can_release and rfid_obj.is_valid_lock_owner(lock_by):
                self._release_rfid(mkc_DB, rfid, rfid_obj.get_release_state())
            else:
                return {'error_code': 202,'error_desc': 'cannot release!'}
        except Exception, ex:
            return {'error_code': 1,'error_desc': 'system error : %s '%str(ex)}
        else:
            return {'error_code': 0,'error_desc': 'successful'}

    ############################################################
    # end for online lock/release disc
    ############################################################


if __name__ == '__main__':
    a = KioskUtils()
    print a.lockdisc({'upc':"815300010006",'lock_by':'56','sales_price':'30.00'})
    print a.releasedisclock({'rfid':"002DD52730000104E0",'lock_by':'56'})
