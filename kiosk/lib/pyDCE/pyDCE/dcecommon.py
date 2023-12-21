#-*- coding: utf-8 -*- 
"""
Author: Richard
Date: 2008-04-18
Common libraries our application needs
""" 

import sys,os
#sys.path.insert(0,os.pardir) 
import signal
import util

"""
Singleton Implementation, borrowed from Python Cook
"""
class Singleton(object):
    def __new__(cls,*args,**kwargs):
        if '_inst' not in vars(cls):
            cls._inst=object.__new__(cls,*args,**kwargs)
        return cls._inst
#####################################################

class Singleton2(object):
    def __new__(cls,*args,**kwargs):
        if '_inst' not in vars(cls):
            cls._inst=object.__new__(cls,*args,**kwargs)
            cls._inst.init()
        return cls._inst
#####################################################

exit=0

"""
some signal handlers
"""
def exit_handler(signum, frame):
    print 'got signal %i exit...' % signum
    global exit
    exit=1

def do_nothing_handler(signum,frame):
    print 'got signal %i do nothing' % signum
    pass

"""
UApplication is another Singleton
"""
class UApplication(object):
    def on_init(self):
        print 'application init'
        """
        signal.signal(signal.SIGHUP, handler)
        """
        
    def run(self):
        global exit
        while exit==0:
            #print 'exit value:%i'% exit
            self.do_loop()
        #print 'out of do loop'
        self.on_exit()
    
    def do_loop(self):
        pass
    
    def on_exit(self):
        print 'application exit'
        pass
    
    def __new__(cls,*args,**kwargs):
        if '_inst' not in vars(cls):
            cls._inst=object.__new__(cls,*args,**kwargs)
            cls._inst.on_init()
        return cls._inst
#    def __delete__(self, instance):
#        instance.on_exit()
#########################################################


class DCEObject:
    def __init__(self,uuid=None):
        if uuid:
            self._uuid=uuid
        else:
            self._uuid=util.getuuid()
        
    def getID(self):
        return self._uuid
    
