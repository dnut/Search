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
		""" detailed info for one result """
		#if isinstance(self.results[i], tuple):
		try:
			return '{}: {}\n{}\n{}'.format(
				i + 1,
				self.results[i]['title'],
				self.results[i]['link'],
				self.results[i]['snippet']
			)
		except KeyError as e:
			if str(e) == '\'snippet\'':
				return self.search(self.results[i]['title'])
			else:
				raise

	def brief(self, i):
		""" brief info for one result """
		res = self.results[i]
		return '{}: {} - {}'.format(str(i + 1), res['title'], res['link'])

	def summary(self):
		""" brief overview for all results """
		r = [self.brief(i) for i in range(1, min(len(self.results), self.first))]
		return '\n'.join([self.details(0)] + r)

	def more(self):
		""" continued info for all results """
		ret = []
		if len(self.results) <= self.first:
			return 'No more results.'
		for i in range(self.first, len(self.results)):
			ret.append(self.brief(i))
		return '\n'.join(ret)

	def complete(self):
		""" detailed info for all results """
		ret = ()
		for i, result in enumerate(self.results):
			try:
				snippet = self.results[i]['snippet']
			except KeyError as e:
				if str(e) == '\'snippet\'':
					snippet = ''
				else:
					raise
			ret += (
				'[' + str(i+1) + '] - ' + self.results[i]['title'],
				self.results[i]['link'],
				
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

	def is_redirect(self, title, markup=None):
		if not markup:
			markup = self.markup(title)
		return markup[:9] == '#REDIRECT'

	def is_disambig(self, title, markup=None):
		if not markup:
			markup = self.markup(title)
		return bool(re.search(r'{{disambig(uation)?}}', markup))

	def get_redirect(self, title, markup=None):
		if not markup:
			markup = self.markup(title)
		return self.search(
			re.search(r'\[\[([^]]*)\]\]', markup).expand(r'\1')
		)

	def get_links(self, title, markup=None):
		if not markup:
			markup = self.markup(title)
		link = re.compile(r'\[\[([^]|]*)\]\]|\[\[([^]|]*)\|[^]|]*\]\]')
		ret = []
		for p in link.findall(markup):
			subtitle = [i for i in p if i][0]
			ret.append({'title': subtitle, 'link': self.url(subtitle)})
		return ret

	def article(self, title):
		""" Finds page with title, returns string in format:
		'title
		url (to view in browser)
		introduction to article (plain text)'
		"""
		data = self.data(title, 'api', 'article')
		try:
			markup = self.markup(title)
		except KeyError:
			pass
		(k, v), = data['query']['pages'].items()
		if k == '-1':
			raise PageNotFoundError(title)
		elif self.is_redirect(title, markup):
			return self.get_redirect(title, markup)
		article = (v['title'], self.url(v['title']), v['extract'])
		if self.is_disambig(title, markup):
			self.results = self.get_links(title, markup)
			for i, j in enumerate(self.results):
				article += (self.brief(i),)
				if i == 2: break
			self.first = 3
		else:
			# Set up other search results
			self.list_search(title, True)
			self.first = 1
		if len(self.results) > self.first:
			article += ('-- NOTE: Use !m for more. --',)
		return '\n'.join(article)

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
