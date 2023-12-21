#!/usr/bin/python
#Filename: main.py

"""
Main application
2009-07-02 created by Mavis
"""

import sys
import os
from PyQt4 import QtCore, QtGui
from control import MainControl

#############################
# Main application class
#############################

class MainApp(QtGui.QApplication):

	def __init__(self, argv):
		QtGui.QApplication.__init__(self, argv)

		self.control = MainControl()
		self.translate = QtCore.QTranslator()

	#############################
	# Execute command from controler
	#############################

	def execCmd(self, cmd):
		try:
			self.control.trace.info(cmd)
			cmd = cmd.toLocal8Bit().data()
			exec(cmd)
			#eval(str(cmd))
		except Exception, ex:
			#print '[execCmd] ERROR: %s command: [%s]' %(ex,cmd)
			self.control.trace.error("[execCmd] ERROR: %s command: [%s]" %(ex,cmd))
			import traceback
			self.control.trace.error(traceback.format_exc())

	##
	# Exit normally
	##
	def exitNormal(self):
		sys.exit()

	##
	# Init GUI
	##
	def initGUI(self, param=0):
		##
		# Create all forms
		##
		from forms import Forms
		global objforms
		objforms = Forms(param)
		objforms.show()

	##
	# Internationalization
	##
	def setLanguage(self):
		import config
		if os.path.isfile(config.transDir+config.transFile):
			self.translate.load(config.transFile, config.transDir)
			self.installTranslator(self.translate)
		else:
			self.removeTranslator(self.translate)

#############################
# Main entrance
#############################

if __name__ == "__main__":

	app = MainApp(sys.argv)
	app.connect(app.control, QtCore.SIGNAL("execCommand(QString)"), app.execCmd)
	app.control.start()
	app.setOverrideCursor(QtCore.Qt.BlankCursor)

	sys.exit(app.exec_())
