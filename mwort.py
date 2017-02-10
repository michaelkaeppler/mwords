# -*- coding: utf-8 -*-
"""
Created on Tue Jan 31 21:53:56 2017

@author: Mael
"""

from os.path import getsize, isfile
import argparse
import logging
import collections
from tqdm import trange
from multiprocessing import Process, Manager, cpu_count
import re

musical_regex = re.compile(r'^([a-hs]|cis|dis|fis|gis)+$', flags=(re.IGNORECASE))

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s:%(levelname)s:%(name)s:%(message)s',
    filename="mwort.log",
    filemode='w'
)

def get_args():
    parser = argparse.ArgumentParser()
    cpus = cpu_count()
    parser.add_argument("filename", help="File that shall be parsed")
    parser.add_argument("-m", "--min-length", type=int, default=3, help="Minimum word length to parse")
    parser.add_argument("-p", "--processes", type=int, default=cpus, help="Number of processes")
    parser.add_argument("-c", "--chunk_size", type=int, default=100, help="Size of chunks in KByte, that are read at once")
    return parser.parse_args()
    
def worker(nr, input_queue, mword_list):
     logger = logging.getLogger("Process "+str(nr))
     logger.debug("Starting")
     while True:
        queue_item = input_queue.get()
        if queue_item is None:
            logger.debug("Queue is empty, terminating")
            return
        else:
            chunk_nr, word_string = queue_item
            logger.debug("Getting chunk {} from queue".format(chunk_nr))
            words = word_string.split()
            logger.debug("Split chunk {} in {} words".format(chunk_nr, len(words)))
            mwords = [word for word in words if musical_regex.match(word)]
            logger.debug("Got {} musical words".format(len(mwords)))
            mword_list.extend(mwords)
    
def get_worker_pool(num, worker, input_queue, mword_list):
    pool = []
    for i in xrange(num):
        p = Process(target=worker, args=(i, input_queue, mword_list))
        p.start()
        pool.append(p)
    return pool
        
def get_chunk(f, size):
    chunk = f.read(size)
    while True: # Read additional characters until whitespace 
        ch = f.read(1)
        if ch.isspace() or (not ch):
            break
        chunk += ch
    return chunk
    
def postprocess_list(mwords, **kwargs):
    if kwargs is None: # No kwargs passed, use default values in kwargs.get
        kwargs = {}
    sortorder = kwargs.get('sortorder', 'alphabetic')
    minlen = kwargs.get('minlen', 3)
    minocc = kwargs.get('minocc', 1)
    remove_upper = kwargs.get('removeupper', True)
    mwords_count = collections.Counter(mwords)
    props = {}
    props['total'] = sum(mwords_count.values())
    # Remove words that 
    # 1. are shorter than minlen
    # 2. occur less frequently than minocc
    mwords_count = {k:v for k,v in mwords_count.items() if
                        (len(k) >= minlen) and (v >= minocc)}
    # Remove words than consist from only uppercase characters
    if remove_upper:
        mwords_count = {k:v for k,v in mwords_count.items() if
                        k.upper() != k}
    if sortorder == 'alphabetic':
        mwords_unique = sorted(mwords_count)
    props['unique'] = len(mwords_unique)
    return (mwords_count, mwords_unique, props)
    
        
def main():
    args = get_args()
    fname = args.filename
    processes = args.processes
    chunk_size = args.chunk_size*1000 # Size is given in KByte, internal calculation is done in Bytes
    
    main_logger = logging.getLogger("Main")
    
    if isfile(fname):
        fsize = getsize(fname) # Returns size in bytes
        with open(fname) as f:
            print "Opened file {}, size {:,} bytes".format(fname, fsize) 
            chunks = fsize // chunk_size
            if fsize % chunk_size != 0:
                chunks += 1
            print "Splitting file in {} chunks of size {:,} bytes".format(chunks, chunk_size)
            manager = Manager()
            mwords = manager.list()
            work = manager.Queue(processes)
            print "Starting {} processes...".format(processes)
            pool = get_worker_pool(processes, worker, work, mwords)
            
            for chunk_nr in trange(1, chunks+1):
                chunk = get_chunk(f, chunk_size)
                work.put((chunk_nr, chunk))
                main_logger.debug("Working on chunk {} of {}".format(chunk_nr, chunk_size))
            
            for i in xrange(processes):
                work.put(None) # Send termination signal for each process
            
            for p in pool:
                p.join()
                
            mwords_count, mwords_unique, props = postprocess_list(mwords)
            print 'Found {} musical words, {} of them unique'.format(props['total'], props['unique'])
            for k, v in mwords_count.items():
                print '{}: {} times'.format(k, v)
                                                                            
    else:
        print "Can't find file {}, exiting.".format(fname)

if __name__ == "__main__":
    main()
