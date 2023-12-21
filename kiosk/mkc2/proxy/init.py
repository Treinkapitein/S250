#!/usr/bin/python

"""
Change Log:
    2011-02-15 Modified by Kitch:
        add vacuum_upc_db_thread.pyc
    2009-10-23 Modified by Kitch:
        add auto_reduce.pyc
    2008-05-04 Create By Tim:
        Start all thread.
"""

import os
import time

# Must start before service.
needStartThread = ["/home/mm/kiosk/mkc2/proxy/db_sync_thread.pyc", 
                   "/home/mm/kiosk/mkc2/proxy/media_download_thread.pyc", 
                   "/home/mm/kiosk/mkc2/proxy/upg_postauth_thread.pyc",
                   "/home/mm/kiosk/mkc2/proxy/check_reserved_trs_thread.pyc",
                   "/home/mm/kiosk/mkc2/proxy/manage_kiosk_thread.pyc",
                   "/home/mm/kiosk/mkc2/proxy/auto_reduce.pyc",
                   "/home/mm/kiosk/mkc2/proxy/server_kiosk_sync_thread.pyc",
                   "/home/mm/kiosk/mkc2/proxy/upc_db_updation_thread.pyc",
                   "/home/mm/kiosk/mkc2/proxy/auto_arrangement_plan_thread.pyc",
                   "/home/mm/kiosk/mkc2/proxy/topup_for_cerepay_thread.pyc",
                   "/home/mm/kiosk/mkc2/proxy/vacuum_upc_db_thread.pyc",
                   "/home/mm/kiosk/mkc2/proxy/upload_video_thread.pyc",
                   ]

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
                #oid = os.fork()
                #result = "0"
                #if oid == 0:
                #     os.execl('/usr/bin/python', 'python', cmd)
                #else:
                #     result = '1'
                #time.sleep(10)
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

def startThread(threadFile):
    """ Start the thread 'threadFile'.
    """
    w = None
    r = None
    try:
        baseName = os.path.basename(threadFile)
        cmd = "ps aux | grep %s | grep -v 'grep %s'" % (baseName, baseName)
        lc = LinuxCmd()
        result = lc.execute(cmd)
        print result.strip()
        if result.find(baseName) < 0:
            folder = threadFile.replace(baseName, "")
            # The thread does not start, and start it now.
            cmd = "cd %s; nohup python %s > /tmp/%s 2>&1 &" % (folder, baseName, baseName)
            #cmd = threadFile
            #cmd = "nohup python %s &" % threadFile
            #result = lc.execute(cmd, True)
            result = os.system(cmd)

            #result = 0
            if str(result) == "0":
                # Start thread successfully.
                print "Start '%s' successfully." % threadFile
                cmd = "ps aux | grep %s | grep -v 'grep %s'" % (baseName, baseName)
                result = lc.execute(cmd)
                print result.strip()
            else:
                # Start thread failed.
                print "Start '%s' failed." % threadFile
        else:
            # The thread is running.
            print "'%s' is running." % threadFile
        print
    except Exception, ex:
        print "Error when start thread(%s): %s" % (threadFile, str(ex))

def main():
    for thread in needStartThread:
        startThread(thread)

if __name__ == "__main__":
    main()
