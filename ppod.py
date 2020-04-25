#!/bin/python

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
	return {}

def save_settings(settings):
	print 'save settings'

def load_subscriptions():
	subfile = './.subs'
	if not path.exists(subfile):
		save_subscriptions({})
	
	subs = json.load(open(subfile))
	return subs

def save_subscriptions(subs):
	print 'save_subscriptions'
	json.dump(subs, open('./.subs', 'w'))

def add_subscription(subs, feed_name, feed_url, etag=None, last_modified=None):
	subs[feed_url] = {
		'name': feed_name,
		'url': feed_url
	}
	
	if etag != None:
		subs[feed_url]['etag'] = etag
	
	if etag == None and last_modified != None:
		subs[feed_url]['last_modified'] = last_modified

def subscribe(feed_url):
	subs = load_subscriptions()
	print 'Subscribing to feed at ' + feed_url
	response = requests.get(feed_url)
	podcast = Podcast(response.content)
	print response.headers
	etag = None
	last_modified = None
	if response.headers['etag']:
		etag = response.headers['etag']
		print etag
	elif response.headers['Last-Modified']:
		last_modified = response.headers['Last-Modified']
		print last_modified
	
	print 'Show Title: ' + podcast.title
	print 'There are %d items in feed.' % len(podcast.items)
	
	add_subscription(subs, podcast.title, feed_url, etag, last_modified)
	save_subscriptions(subs)
	
	print 'Downloading latest item'
	url = podcast.items[0].enclosure_url
	#download(podcast.title, url)

def folder_for_feed(feed_name):
	local_folder_name = './' + feed_name
	
	# Does the folder not exist? Create it.
	if not path.exists(local_folder_name):
		try:
			os.mkdir(local_folder_name)
		except OSError:
			print 'Creation of feed directory %s failed.' % local_folder_name
			sys.exit(2)
	return local_folder_name


def local_filename_for_feed_item(feed_name, item_url):
	folder = folder_for_feed(feed_name)
	local_filename = folder + '/' + item_url.split('/')[-1].split('?')[0]
	print 'Local filename %s' % local_filename
	return local_filename

def download(feed_name, item_url):
	r = requests.get(item_url);
	local_filename = local_filename_for_feed_item(feed_name, item_url)
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
        print sub

def refresh_feed(feed_url):
    subs = load_subscriptions()
    etag = etag_for_sub(subs, feed_url)



def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('-r', '--refresh', help='Refresh subscriptions', action='store_true')
	parser.add_argument('-s', '--subscribe', help='Subscribe to feed.')
	args = parser.parse_args()
	
	if args.subscribe:
		subscribe(args.subscribe)
		
	if args.refresh:
		print 'Refreshing feeds.'
                refresh()
	
if __name__ == "__main__":
	main()
