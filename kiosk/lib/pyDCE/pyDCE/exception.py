
"""
pyDCE's exception class
Author:Richard Chai
Description: ...
"""
##root exception class
class DCEException(Exception):
    def __init__(self,msg=""):
        Exception.__init__(self,msg)

class NotImplementedException(DCEException):
    def __init__(self,msg=""):
        DCEException.__init__(self,msg)

class CommunicateException(DCEException):
    def __init__(self,msg=""):
        DCEException.__init__(self,msg)

class TimeoutException(DCEException):
    def __init__(self,msg=""):
        DCEException.__init__(self,msg)   
        
class ProtocolException(DCEException):
    def __init__(self,msg=""):
        DCEException.__init__(self,msg)   

class SSLException(DCEException):
    def __init__(self,msg=""):
        DCEException.__init__(self,msg)   

class NoObjectException(DCEException):
    def __init__(self,msg=""):
        DCEException.__init__(self,msg)   
        
class NoMethodException(DCEException):
    def __init__(self,msg=""):
        DCEException.__init__(self,msg)   
        
class UserException(DCEException):
    def __init__(self,msg="",err=0):
        DCEException.__init__(self,msg) 
        self.errorcode=err        

class NoAttributeException(DCEException):
    def __init__(self,msg=""):
        DCEException.__init__(self,msg)   

class ParameterErrorException(DCEException):
    def __init__(self,msg=""):
        DCEException.__init__(self,msg)   
    
class UnknownException(DCEException):
    def __init__(self,msg=""):
        DCEException.__init__(self,msg)    
        

if __name__=="__main__":
    try:
        raise NotImplementedException("Not Implemented")
    except Exception,ex:
        print "got exception:",ex
