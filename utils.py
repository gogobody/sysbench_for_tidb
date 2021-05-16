#!/usr/bin/env python

import sys
import logging
import signal
import pymysql
import time
from warnings import filterwarnings
import subprocess

filterwarnings("error", category=pymysql.Warning)


class MySQL(object):

    def __init__(self, config):
        self.my_config = config
        try:
            self.cnn = pymysql.connect(**self.my_config)
            self.cursor = self.cnn.cursor()
        except Exception as e:
            raise Exception(e)

    def execute(self, sql):
        try:
            self.cursor.execute(sql)
            self.cnn.commit()
        except pymysql.Warning as e:
            return 0
        except Exception as e:
            raise Exception(e)
        return 1

    def __del__(self):
        try:
            self.cursor.close()
            self.cnn.close()
        except:
            pass
    def getInstance(self):
        return self.cursor


def logger(logfile):
    format = '%(asctime)s [%(filename)s][%(levelname)s] %(message)s'
    logging.basicConfig(level=logging.DEBUG, filename=logfile, filemode='a', format=format)
    logger = logging.getLogger()
    return logger


def run_cmd(cmd, display):
    def _makeresetsigpipe():
        """ Make a function to reset SIGPIPE to SIG_DFL (for use in subprocesses).
            Doing subprocess.Popen(..., preexec_fn=makeresetsigpipe()) will prevent
            Python's SIGPIPE handler (SIG_IGN) from being inherited by the child process.
        """
        return lambda: signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    p = subprocess.Popen(cmd,
                         bufsize=-1,
                         shell=True,
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         preexec_fn=_makeresetsigpipe())
    try:
        if display == 0:
            """
            Read data from stdout and stderr, until end-of-file is reached.  
            """
            out, err = p.communicate()
            return p.returncode, out, err
        elif display == 1:
            res_list = []
            # None 在运行
            while p.poll() is None:
                r = p.stdout.readline().decode('utf8').strip()
                if r:
                    print(r)
                    res_list.append(r)
            if p.poll() != 0:
                err = p.stderr.read().decode('utf8').strip()
                print(err)
            else:
                err = ''
            return p.returncode, res_list, err
        else:
            display = int(display) + 1
            while True:
                rescode = subprocess.Popen.poll(p)
                # 正常结束
                if rescode == 0:
                    break
                # None 在运行
                elif rescode is None:
                    process_bar = ShowProcess(display)
                    for i in range(display):
                        process_bar.show_process()
                        time.sleep(1)
            return p.returncode, '', ''
    except Exception as ex:
        raise ex


class ShowProcess:
    i = 0
    max_steps = 0
    max_arrow = 50
    infoDone = 'done'

    def __init__(self, max_steps, info_done='Done'):
        self.max_steps = max_steps
        self.i = 0
        self.infoDone = info_done

    def show_process(self, i=None):
        if i is not None:
            self.i = i
        else:
            self.i += 1
        num_arrow = int(self.i * self.max_arrow / self.max_steps)
        num_line = self.max_arrow - num_arrow
        percent = self.i * 100.0 / self.max_steps
        process_bar = '[' + '>' * num_arrow + '-' * num_line + ']' \
                      + '%.2f' % percent + '%' + '\r'
        sys.stdout.write(process_bar)
        sys.stdout.flush()
        if self.i >= self.max_steps:
            self.close()

    def close(self):
        # print('')
        # print(self.infoDone)
        self.i = 0

