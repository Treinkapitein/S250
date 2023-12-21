#-*- coding: utf-8 -*-

"""
2009-06-23 Modified by Tim
Change the log file path.
Author: Richard
Date:2008-05-03
"""
import sys,os
sys.path.insert(0,os.pardir)
import cPickle
import logging
import logging.handlers
import SocketServer
import struct
from pyDCE.config import *
import os.path
#from dcecommon import Singleton

def init_log(name,
             log_file_root=LOG_FILE_ROOT,
             format=LOG_FORMAT,
             level=LOG_LEVEL,
             mode=LOG_MODE,
             remote_host=LOG_REMOTE_HOST,remote_port=LOG_REMOTE_PORT ):
    logging.basicConfig(level=level,
                        format=format,
    #                    filename=os.path.join(log_file_root,name),
                        filemode='a')
    rootLogger=logging.getLogger(name)
    formatter=logging.Formatter(format)
    if mode&LOG_MODE_TTY:
        console=logging.StreamHandler()
        console.setLevel(LOG_CONSOLE_LEVEL)
        console.setFormatter(formatter)
        rootLogger.addHandler(console)
    if mode&LOG_MODE_REMOTE:
        socketHandler=logging.handlers.SocketHandler(LOG_REMOTE_HOST, LOG_REMOTE_PORT )
        socketHandler.setFormatter(formatter)
        rootLogger.addHandler(socketHandler)
    if LOG_ROTATE_SIZE:
        rotateHandler=logging.handlers.RotatingFileHandler(os.path.join(log_file_root,name),
                                                'a',LOG_ROTATE_SIZE, LOG_ROTATE_COUNT)
        #rotateHandler.setLevel(level)
        rotateHandler.setFormatter(formatter)
        rootLogger.addHandler(rotateHandler)
    return rootLogger

"""
The following code was borrowed from Python Lib Reference
In fact, this is not what I originally wanted
"""
class LogRecordStreamHandler(SocketServer.StreamRequestHandler):
    def handle(self):
        """
        Handle multiple requests - each expected to be a 4-byte length,
        followed by the LogRecord in pickle format. Logs the record
        according to whatever policy is configured locally.
        """
        while 1:
            chunk = self.connection.recv(4)
            if len(chunk) < 4:
                break
            slen = struct.unpack(">L", chunk)[0]
            chunk = self.connection.recv(slen)
            while len(chunk) < slen:
                chunk = chunk + self.connection.recv(slen - len(chunk))
            obj = self.unPickle(chunk)
            record = logging.makeLogRecord(obj)
            self.handleLogRecord(record)

    def unPickle(self, data):
        return cPickle.loads(data)

    def handleLogRecord(self, record):
        # if a name is specified, we use the named logger rather than the one
        # implied by the record.
        if self.server.logname is not None:
            name = self.server.logname
        else:
            name = record.name
        logger = logging.getLogger(name)
        # N.B. EVERY record gets logged. This is because Logger.handle
        # is normally called AFTER logger-level filtering. If you want
        # to do filtering, do it at the client end to save wasting
        # cycles and network bandwidth!
        logger.handle(record)

class LogRecordSocketReceiver(SocketServer.ThreadingTCPServer):
    """simple TCP socket-based logging receiver suitable for testing.
    """
    allow_reuse_address = 1
    def __init__(self, host=LOG_REMOTE_HOST,
                 port=LOG_REMOTE_PORT,
                 handler=LogRecordStreamHandler):
        SocketServer.ThreadingTCPServer.__init__(self, (host, port), handler)
        self.abort = 0
        self.timeout = 1
        self.logname = None

    def serve_until_stopped(self):
        import select
        abort = 0
        while not abort:
            rd, wr, ex = select.select([self.socket.fileno()],
                                       [], [],
                                       self.timeout)
            if rd:
                self.handle_request()
            abort = self.abort

def main():
    logging.basicConfig(
        format=LOG_FORMAT)
    tcpserver = LogRecordSocketReceiver()
    print "About to start TCP server..."
    tcpserver.serve_until_stopped()

if __name__ == "__main__":
    main()
