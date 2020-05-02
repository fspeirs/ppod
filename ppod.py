#!/usr/bin/python

import argparse, sys
from pyPodcastParser.Podcast import Podcast
import requests
from io import BytesIO
import os
from os import path
import datetime
import json

def usage():
	print "ppod is a Python Podcast downloader."
	print "Usage: ppod [-rh]"   

def load_settings():
	conf = './.ppod.conf'
	if not path.exists(conf):
		save_settings({})
	
	conf = json.load(open(conf))
	return conf

def save_settings(settings):
	json.dump(settings, open('./.ppod.conf', 'w'))

#################################
# Functions to manage subscriptions
#################################

# Returns a dictionary of subscriptions whose keys are feed URLs
def load_subscriptions():
	subfile = './.subs'
	if not path.exists(subfile):
		save_subscriptions({})
	
	subs = json.load(open(subfile))
	return subs

# Saves a dictionary of subscriptions
def save_subscriptions(subs):
	json.dump(subs, open('./.subs', 'w'))

# Adds a subscription with optional etag and last modified time
def add_subscription(subs, feed_name, feed_url, etag=None, last_modified=None):
	subs[feed_url] = {
		'name': feed_name,
		'url': feed_url
	}
	
	if etag != None:
		subs[feed_url]['etag'] = etag
	
	if etag == None and last_modified != None:
		subs[feed_url]['last_modified'] = last_modified

# Returns the etag for a given feed
def etag_for_sub(subs, feed_url):
	return subs[feed_url].get('etag')

def save_etag_for_sub(subs, feed_url, etag):
	subs[feed_url]['etag'] = etag

def last_modified_for_sub(subs, feed_url):
	return subs[feed_url].get('last_modified')

def save_last_modified_for_sub(subs, feed_url, last_modified):
	subs[feed_url]['last_modified'] = last_modified
	
#############################
# Subscribing
#############################

# Subscribing loads a feed URL to check it is valid and get the feed title and etag.
def subscribe(feed_url):
	print 'Subscribing to feed at ' + feed_url
	
	response = requests.get(feed_url)
	# print response.headers
	if response.status_code != 200:
		print 'URL not valid (%d)' % response.status_code
		sys.exit(2)
	
	podcast = Podcast(response.content)
	if not podcast.is_valid_podcast:
		print 'URL is not a podcast feed.'
		sys.exit(2)
		
	etag = None
	last_modified = None
	if response.headers.get('etag'):
		etag = response.headers['etag']
	elif response.headers.get('Last-Modified'):
		last_modified = response.headers['Last-Modified']
	
	print 'Show Title: ' + podcast.title
	print 'There are %d items in feed.' % len(podcast.items)
	
	subs = load_subscriptions()
	add_subscription(subs, podcast.title, feed_url, etag, last_modified)
	save_subscriptions(subs)
	print 'Subscribed.'

# Lists Subscriptions
def list_subscriptions():
	subs = load_subscriptions()
	i=1
	for s in subs:
		print '%d: %s' % (i, subs[s]['name'])
		i += 1
		
# Unsubscribe from podcast
def unsubscribe(index):
	subs = load_subscriptions()
	delete_sub_at_index(subs, index)
	save_subscriptions(subs)

def folder_for_feed(feed_name):
	subfolder = './'
	settings = load_settings()
	if settings.get('media_dir'):
		subfolder = settings['media_dir']
		
	local_folder_name = subfolder + feed_name
	
	# Does the folder not exist? Create it.
	if not path.exists(local_folder_name):
		try:
			os.makedirs(local_folder_name)
		except OSError:
			print 'Creation of feed directory %s failed.' % local_folder_name
			sys.exit(2)
	return local_folder_name


def local_filename_for_feed_item(feed_name, item_url, item_title, item_datetime):
	folder = folder_for_feed(feed_name)
	source_file_name = item_url.split('/')[-1].split('?')[0]
	source_extension = source_file_name.split('.')[-1]
	
	cleaned_title = item_title.replace(':', '-')
	local_filename = '%s/%s - %s.%s' % (folder, item_datetime.strftime('%Y-%m-%d'), cleaned_title, source_extension)
	return local_filename

# Downloads a given item from a feed.
def download(feed_name, item):
	item_url = item.enclosure_url
	local_filename = local_filename_for_feed_item(feed_name, item.enclosure_url, item.title, item.date_time)
	
	r = requests.get(item_url);
	# NOTE the stream=True parameter below
	with requests.get(item_url, stream=True) as r:
		r.raise_for_status()
		with open(local_filename, 'wb') as f:
			for chunk in r.iter_content(chunk_size=8192): 
				if chunk: # filter out keep-alive new chunks
					f.write(chunk)
					# f.flush()
		return local_filename

########################################
## Refreshing Feeds
########################################
def refresh():
    subs = load_subscriptions()
    for sub in subs:
        print 'Refreshing: %s' % subs[sub]['name']
        refresh_feed(sub)

def refresh_feed(feed_url):
	subs = load_subscriptions()
	etag = etag_for_sub(subs, feed_url)
	last_modified = last_modified_for_sub(subs, feed_url)
	
	headers = {
		'If-None-Match': etag,
		'Last-Modified': last_modified
	}
	r = requests.get(feed_url, headers)
	
	if r.status_code == 200:
		new_etag = r.headers.get('ETag')
		new_last_modified = r.headers.get('Last-Modified')
		save_etag_for_sub(subs, feed_url, new_etag)
		save_last_modified_for_sub(subs, feed_url, new_last_modified)
		save_subscriptions(subs)
		
		podcast = Podcast(r.content)
		download_new_episodes(podcast, 1)

#
# Checks through podcast's items feed up to limit to find any files we don't have
#
def download_new_episodes(podcast, limit=-1):
	if limit < 0:
		limit = len(podcast.items)
	for i in range(limit):
		item = podcast.items[i]
		download_url = item.enclosure_url
		local_file = local_filename_for_feed_item(podcast.title, item.enclosure_url, item.title, item.date_time)
		if not path.exists(local_file):
			print 'Downloading episode: %s (%s)' % (podcast.items[i].title, item.date_time.isoformat())
			download(podcast.title, podcast.items[i])

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('-r', '--refresh', help='Refresh subscriptions', action='store_true')
	parser.add_argument('-s', '--subscribe', help='Subscribe to feed.')
	parser.add_argument('-u', '--unsubscribe', help='Unsubscribe from feed')
	parser.add_argument('-l', '--list', help='List subscriptions.', action='store_true')
	args = parser.parse_args()
	
	if args.subscribe:
		subscribe(args.subscribe)
		
	if args.refresh:
		print 'Refreshing feeds.'
		refresh()
	
	if args.list:
		list_subscriptions()
	
	if args.unsubscribe:
		unsubscribe(int(args.unsubscribe))
	
if __name__ == "__main__":
	main()
