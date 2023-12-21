#!/usr/bin/env python

"""
Created on 2010-2-8
@author: andrew.lu@cereson.com
"""

import os
import sys
import Queue
import traceback
import pexpect
import optparse
from threading import Thread

urlList = [('http', 'update.cereson.com', 80),
           ('ssh', 'update.cereson.com', 22),
           ('ssh', 'remote.cereson.com', 22),
           ('ssh', 'remote2.cereson.com', 22),
           ('http', 'upg1.waven.com', 80),
           ('https', 'upg1.waven.com', 443),
           ('http', 'umg.cereson.com', 8673),
           ('http', 'umgdl.waven.com', 80),
           ('http', 'atlas.cereson.com', 7675),
           ('http', 'cereson.mydvdkiosks.net', 80),
           ('ssh', 'backup.cereson.com', 22)]

class Job:
    job_id = 0
    
    def __init__(self, protocol, url, port):
        self.id = Job.job_id
        Job.job_id += 1
        self.protocol = protocol
        self.url = url
        self.port = port
        self.result = ""
        self.description = ""
    
    def __cmp__(self, oj):
        return self.id - oj.id
    
    def __str__(self):
        if self.description:
            return self.description
        else:
            return "connect to host %s port %s: %s" % (self.url, self.port, self.result)

class NetworkChecker(Thread):
    worker_count = 0
    timeout = 0.1
    
    def __init__(self, workQueue, resultQueue, single, **kwds):
        super(NetworkChecker, self).__init__(**kwds)
        self.id = NetworkChecker.worker_count
        NetworkChecker.worker_count += 1
        self.setDaemon(True)
        self.workQueue = workQueue
        self.resultQueue = resultQueue
        self.single = single
        self.start()
    
    def _setResult(self, job, result, description=""):
        job.result = result
        job.description = description
        self.resultQueue.put(job)
    
    def _checkSSH(self, job):
        self.remove_file("/home/mm/.ssh/known_hosts")
        self.remove_file("/root/.ssh/known_hosts")
        cmd = "ssh -p%s %s" % (job.port, job.url)
        child = pexpect.spawn(cmd)
        
        try:
            prompt = "%s's password:" % job.url
            index = child.expect(["continue connecting", prompt], timeout = 30)
            if index == 0:
                child.sendline("yes")
                
                index = child.expect(prompt, timeout = 30)
                if index == 0:
                    self._setResult(job, "ok")
            elif index == 1:
                self._setResult(job, "ok")
            else:
                self._setResult(job, "fail")
                raise Exception("Except Unknown Error")
        except pexpect.TIMEOUT:
            self._setResult(job, "fail", "connect to host %s port %s: Time out" % (job.url, job.port))
        except pexpect.EOF:
            self._setResult(job, "fail", child.before.strip())
        except Exception:
            self._setResult(job, "fail")
            raise
        finally:
            child.close()
    
    def _checkHTTP(self, job):
        cmd = "wget %s://%s:%s -O /dev/null" % (job.protocol, job.url, job.port)
        if job.protocol == "https":
            cmd +=" --no-check-certificate"
        
        child = pexpect.spawn(cmd)
        
        try:
            index = child.expect("`/dev/null' saved", timeout = 30)
            if index == 0:
                self._setResult(job, "ok")
            else:
                self._setResult(job, "fail")
                raise Exception("Except Unknown Error")
        except pexpect.TIMEOUT:
            self._setResult(job, "fail", "connect to host %s port %s: Time out" % (job.url, job.port))
        except pexpect.EOF:
            error = child.before.strip()
            des = error.split('\n')[-1]
            self._setResult(job, "fail", des)
        except Exception:
            self._setResult(job, "fail")
            raise
        finally:
            child.close()
    
    def doJob(self, job):
        try:
            if job.protocol == "ssh":
                self._checkSSH(job)
            elif job.protocol == "http":
                self._checkHTTP(job)
            elif job.protocol == "https":
                self._checkHTTP(job)
            else:
                raise Exception("Invalid job type.")
        except:
            print traceback.format_exc()
    
    def run( self ):
        """the get-some-work, do-some-work main loop of worker threads"""
        while True:
            try:
                job = self.workQueue.get(timeout=NetworkChecker.timeout)
                self.doJob(job)
                
                if self.single:
                    print job
            except Queue.Empty:
                break
            except:
                print "NetworkChecker[%2d]" % self.id, sys.exc_info()[:2]
                raise
                
    def remove_file(self, file_path):
        """ remove the file if the file exists
        """
        if os.path.exists(file_path):
            os.system("rm %s" % file_path)

class WorkerManager:
    def __init__( self, num=10, timeout=1):
        self.workQueue = Queue.Queue()
        self.resultQueue = Queue.Queue()
        self.checkers = []
        self.timeout = timeout
        self.checkerNo = num
    
    def start(self):
        if self.checkerNo == 1:
            single = True
        else:
            single = False
        
        for i in range(self.checkerNo):
            checker = NetworkChecker(self.workQueue, self.resultQueue, single)
            self.checkers.append(checker)
    
    def join(self):
        while len(self.checkers):
            checker = self.checkers.pop()
            checker.join()
    
    def addJob(self, protocol, url, port):
        self.workQueue.put(Job(protocol, url, port))
    
    def addJobList(self, jobList):
        for l in jobList:
            self.workQueue.put(Job(l[0], l[1], l[2]))
    
    def printResult(self):
        res = []
        while not self.resultQueue.empty():
            result = self.resultQueue.get_nowait()
            res.append(result)
        
        res.sort()
        for r in res:
            print "%s" % r

if __name__ == "__main__":
    usage = "usage: %prog [-m multithread]"
    
    parser = optparse.OptionParser(usage)
    parser.add_option("-m", "--multithread", action="store_true",
                      dest="multithread", help="use multi-thread to check connections.", default=False)
    
    options, args = parser.parse_args()
    
    if options.multithread:
        wm = WorkerManager()
    else:
        wm = WorkerManager(1)
    wm.addJobList(urlList)
    wm.start()
    wm.join()
    if options.multithread:
        wm.printResult()
    
    sys.exit(0)
