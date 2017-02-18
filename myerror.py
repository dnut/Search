import sys
import traceback

class MyError(Exception):
	def __init__(self):
		sys.excepthook = self.exception_handler

	def exception_handler(self, etype, value, tb):
		if issubclass(etype, MyError):
			lim = len(traceback.extract_tb(tb))
			traceback.print_exception(etype, value, tb, limit=lim-1)
		else:
			sys.__excepthook__(etype, value, tb)

class PageNotFoundError(MyError):
	"""Exception raised for errors in the input.
	Attributes:
		expression -- input expression in which the error occurred
		message -- explanation of the error
	"""
	def __init__(self, expression, message=None):
		super().__init__()
		self.expression = expression
		if message:
			self.message = message
		else:
			self.message = 'There is no page called'

	def __str__(self):
		return '{} "{}"'.format(self.message, self.expression)
