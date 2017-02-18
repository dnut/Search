import json
import re
from urllib.request import urlopen
from pprint import pprint
import html
from myerror import PageNotFoundError
from googleapiclient.discovery import build as google_build

class Search:
	def __init__(self):
		self.first = 3

	def details(self, i):
		return '{}: {}\n{}\n{}'.format(
			i + 1,
			self.results[i]['title'],
			self.results[i]['link'],
			self.results[i]['snippet']
		)

	def summary(self):
		ret = [self.details(0)]
		for i in range(1, min(len(self.results), self.first)):
			ret.append(str(i+1) + ': ' + self.results[i]['title'])
		return '\n'.join(ret)

	def more(self):
		ret = []
		if len(self.results) <= self.first:
			return 'No more results.'
		for i in range(self.first, len(self.results)):
			ret.append(str(i+1) + ': ' + self.results[i]['title'])
		return '\n'.join(ret)

	def complete(self):
		ret = ()
		for i, result in enumerate(self.results):
			ret += (
				'[' + str(i+1) + '] - ' + self.results[i]['title'],
				self.results[i]['link'],
				self.results[i]['snippet']
			)
		return '\n'.join(ret)


class Google(Search):
	def __init__(self):
		super().__init__()
		self.svc = google_build(
			'customsearch',
			'v1',
			developerKey='redacted'
		)

	def api_search(self, search_string):
		query = '+'.join(search_string.split())
		response = self.svc.cse().list(
			q=query,
			cx='redacted',
		).execute()
		return response['items']

	def search(self, query):
		self.results = self.api_search(query)
		return self.summary()


class Wikipedia(Search):
	url_base = {
		'website': 'https://en.wikipedia.org/wiki/',
		'api': 'https://en.wikipedia.org/w/api.php?format=json&',
	}
	url_ext = {
		'article': 'explaintext&exintro&action=query&prop=extracts&titles=',
		'search': 'explaintext&action=query&list=search&srsearch=',
		'markup': 'action=query&prop=revisions&rvprop=content&titles=',
		None: '', '': ''
	}

	def url(self, title, base='website', ext=None):
		return self.url_base[base] + self.url_ext[ext] + '%20'.join(title.split())

	def data(self, *args):
		return json.loads(urlopen(self.url(*args)).read())

	def markup(self, title):
		data = self.data(title, 'api', 'markup')
		(k, v), = data['query']['pages'].items()
		return v['revisions'][0]['*']

	def is_redirect(self, title):
		return self.markup(title)[:9] == '#REDIRECT'

	def get_redirect(self, title):
		return self.search(
			re.search(r'\[\[([^]]*)\]\]', self.markup(title)).expand(r'\1')
		)

	def article(self, title):
		""" Finds page with title, returns string in format:
		'title
		url (to view in browser)
		introduction to article (plain text)'
		"""
		data = self.data(title, 'api', 'article')
		(k, v), = data['query']['pages'].items()
		if k == '-1':
			raise PageNotFoundError(title)
		elif len(v['extract']) == 0 and self.is_redirect(title):
			return self.get_redirect(title)
		article = (v['title'], self.url(v['title']), v['extract'])
		self.list_search(title, True)
		self.first = 1
		return '{}\n{}\n{}'.format(*article)

	def list_search(self, title, force=False):
		data = self.data(title, 'api', 'search')
		results = data['query']['search']
		# If no results, look for a recommendation to fix a typo
		if len(results) == 0:
			try:
				return self.search(data['query']['searchinfo']['suggestion'])
			except KeyError:
				return 'No results for "' + title + '."'
		un_html = lambda x: html.unescape(re.sub(r'<[^>]*>', '', x))
		alnum = lambda x: re.sub(r'\W+', '', x).lower()
		for r in results:
			for (k, v) in r.items():
				if isinstance(v, str):
					r[k] = un_html(r[k])
			if alnum(r['title']) == alnum(title) and not force:
				return self.search(r['title'])
			r['link'] = self.url(r['title'])
		self.results = results
		self.first = 3
		return self.summary()

	def search(self, title):
		try:
			return self.article(title)
		except PageNotFoundError:
			return self.list_search(title)
