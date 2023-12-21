
try:
    import DCEConfig
except:
    pass
import sys

try:
    if len(sys.argv) > 1:
        exec("import %s as DCEConfig" % sys.argv[1])
except:
    pass

try:
    import pyDCE.config
    pyDCE.config.__dict__.update(DCEConfig.dce_config)
except:
    pass


