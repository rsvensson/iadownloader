import os
import requests
import threading
import time
from datetime import datetime
from queue import Queue
from tqdm import tqdm


# Graciously stolen and adapted from Anurag Uniyal @ https://stackoverflow.com/a/18883984

class DownloadThread(threading.Thread):
    def __init__(self, queue: Queue, output_dir: str):
        super(DownloadThread, self).__init__()
        self.queue = queue
        self.output_dir = output_dir
        self.daemon = True

    def run(self):
        while True:
            url = self.queue.get()
            try:
                self.download_url(url)
            except Exception as e:
                print(f"Error: {e}")
            self.queue.task_done()

    def download_url(self, url):
        filename = requests.utils.unquote(url.split("/")[-1])
        dlpath = os.path.join(self.output_dir, filename)

        # Handle resuming a download
        resume_pos = 0
        if os.path.exists(dlpath):
            header = requests.head(url, allow_redirects=True)
            remote_size = int(header.headers.get("content-length", 0))
            local_size = os.path.getsize(dlpath)
            if local_size == remote_size and local_size > 0:
                print(f"{filename} already downloaded. Skipping.\n")
                return
            else:
                resume_pos = local_size

        if resume_pos > 0:
            print(f"Resuming download at {resume_pos} bytes.")
        with requests.get(url, stream=True, headers={"Range": f"bytes={resume_pos}-"}) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("content-length", 0))
            block_size = 8192
            progress_bar = tqdm(total=total_size, unit='iB', unit_scale=True)
            progress_bar.set_description(filename)  # Prefix filename to output
            try:  # Try getting last modified time
                last_mod = r.headers.get("last-modified")
                mod_date = datetime.strptime(last_mod, "%a, %d %b %Y %H:%M:%S %Z")
                mod_time = time.mktime(mod_date).timetuple()
            except TypeError:
                mod_time = time.mktime(datetime.now().timetuple())
            mode = "wb" if resume_pos == 0 else "ab"
            with open(dlpath, mode) as fd:
                for block in r.iter_content(block_size):
                    progress_bar.update(len(block))
                    fd.write(block)
            progress_bar.close()
        # Set last modified time
        os.utime(dlpath, (mod_time, mod_time))
