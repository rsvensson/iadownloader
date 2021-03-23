#!/usr/bin/env python

from dlthread import DownloadThread

import argparse
import json
import os
import requests
import sys
from lxml import html
from queue import Queue


dlurl = "https://archive.org/download/"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="URL or path to json/csv file")
    parser.add_argument("-o", "--output_dir", help="Path to output directory.", default=os.getcwd())

    args = parser.parse_args()

    if not str(args.url).startswith("http://") and not str(args.url).startswith("https://") \
       and not str(args.url).endswith(".json") and not str(args.url).endswith(".csv"):
        print("Error: Invalid URL.")
        sys.exit(1)

    return args


def json2list(path: str) -> list:
    """
    Parses a json file from IA's advanced search into a list of urls.
    :param path: Path to the json file.
    :return: List of download urls.
    """

    urls = list()
    try:
        text = open(path, "r").read()
    except FileNotFoundError:
        print(f"Error: No such json file: {path}")
        sys.exit(1)
    text = text.replace("callback(", "")  # Remove non-json leading text
    data = json.loads(text.rstrip(")"))  # Don't include the trailing ")"
    docs = data["response"]["docs"]

    for entry in docs:
        urls.append(dlurl + entry["identifier"])

    return urls


def csv2list(path: str) -> list:
    """
    Parses a csv file from IA's advanced search into a list of urls.
    :param path: Path to the csv file.
    :return: List of download urls.
    """

    urls = list()
    try:
        with open(path, "r") as fd:
            for line in fd.readlines():
                if line.find('"identifier"') != -1:
                    continue  # Skip header
                line = line.replace('"', '')  # Remove surrounding quote marks
                urls.append(dlurl + line.rstrip("\n"))  # Remove potential newlines
    except FileNotFoundError:
        print(f"Error: No such csv file: {path}")
        sys.exit(1)

    return urls


def get_download_links(url: str) -> list:
    """
    Returns the links in a download url.
    """

    page = requests.get(url)
    webpage = html.fromstring(page.content)
    rawlinks = webpage.xpath("//a/@href")
    links = list()

    for link in rawlinks:
        if link.startswith("http://")  or link.startswith("https://") \
           or link.find("#maincontent") != -1 or link.find("/details/") != -1 \
           or link.endswith("/"):
            # Skip links that are not for file downloads
            continue
        links.append(dlurl + url.split("/")[-1] + "/" + link)

    return links


def download(urls: list, output_dir: str, numthreads: int = 4):
    queue = Queue()
    for url in urls:
        queue.put(url)

    for i in range(numthreads):
        t = DownloadThread(queue, output_dir)
        t.start()

    queue.join()


def main():
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    if args.url.startswith("http://") or args.url.startswith("https://"):
        links = get_download_links(args.url)
        download(links, args.output_dir)
        return
    elif args.url.endswith(".csv"):
        urls = csv2list(args.url)
    elif args.url.endswith(".json"):
        urls = json2list(args.url)
    else:
        print("Something went wrong")
        sys.exit(1)

    for url in urls:
       dlpath = os.path.join(args.output_dir, url.split("/")[-1])
       os.makedirs(dlpath, exist_ok=True)
       links = get_download_links(url)
       download(links, dlpath)

if __name__ == "__main__":
    main()
