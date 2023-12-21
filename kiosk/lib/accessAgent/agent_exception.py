#!/usr/bin/python
""" Exceptions of the access agent.
"""

#======================================================
#                    Exception
#======================================================
class BaseException( Exception ):
    def __init__(self,msg=""):
        Exception.__init__(self,msg)

class ProtocolException( BaseException ):
    def __init__(self,msg=""):
        BaseException.__init__(self,msg)

class CodecException( BaseException ):
    def __init__(self,msg=""):
        BaseException.__init__(self,msg)

class CommunicateException( BaseException ):
    def __init__(self,msg=""):
        BaseException.__init__(self,msg)

class UnkownException( BaseException ):
    def __init__(self,msg=""):
        BaseException.__init__(self,msg)

class NoMethodException( BaseException ):
    def __init__(self,msg=""):
        BaseException.__init__(self,msg)

class UserException( BaseException ):
    def __init__(self,msg="",err=0):
        BaseException.__init__(self,msg)
        self.errorcode=err