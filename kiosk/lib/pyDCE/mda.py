#!/usr/bin/python

"""
try:
    import sqlite3 as sqlite
    from sqlite3 import DatabaseError
except:
"""
from pysqlite2 import dbapi2 as sqlite
from pysqlite2.dbapi2 import DatabaseError

class Db(object):
    """
    All database access utility.
    """
    def __init__(self, dbFile):
        #dbPath = os.path.join(dbDir(), 'mdc', dbFile)
        dbPath = dbFile
        self.con = sqlite.connect(dbPath, isolation_level='EXCLUSIVE', timeout=10, check_same_thread=False)
        self.con.text_factory = str

    def __del__(self):
        if hasattr(self.con, "close"):
            self.con.close()

    def query(self, sql, fetch='all', params=()):
        if fetch == 'all':
            rev = self.con.execute(sql, params).fetchall()
        else:
            rev = self.con.execute(sql, params).fetchone()
        return rev

    def update(self, sql, params = ()):
        cur = self.con.cursor()
        cur.execute(sql, params)
        self.con.commit()
        lastrowid = cur.lastrowid
        cur.close()
        return lastrowid

    def updateMany(self, sql, paramsList = []):
        cur = self.con.cursor()
        cur.executemany(sql, paramsList)
        self.con.commit()
        cur.close()
        return

    def executeScript(self, sql):
        self.con.executescript(sql)
        return

    def setFunction(self, i, funObj):
        self.con.create_function(funObj.func_name, int(i), funObj)
        return

    def updateTrs(self, sqlList):
        cur = self.con.cursor()
        try:
            try:
                for sql in sqlList:
                    cur.execute(sql)
                self.con.commit()
            except:
                self.con.rollback()
                raise
        finally:
            cur.close()
        return

    def updateTrs2(self, trsList):
        """
        @Params: trsList(list): [{"sql":xx, "params":xx, "type":(single/many)}]
        """
        cur = self.con.cursor()
        try:
            try:
                for trs in trsList:
                    trsType = trs.get("type", "single")
                    if trsType == "single":
                        cur.execute(trs["sql"], trs.get("params", {}))
                    elif trsType == "many":
                        cur.executemany(trs["sql"], trs.get("params", []))
                    else:
                        cur.execute(trs["sql"])
                self.con.commit()
            except Exception, ex:
                self.con.rollback()
                raise
        finally:
            cur.close() 

