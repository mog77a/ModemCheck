#!/usr/bin/env python
#
# ModemCheck.py - A simple script to monitor a Netgear CM1150V Cable Modem.
#                 It may or may not work for other Netgear Cable Modems.
#
# Copyright (c) 2020 Howard Holm
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
import argparse
import getpass
import json
import logging
from pickle import NONE
from pydoc import pager
import os
import re
import site
import datetime
import csv
import requests
from bs4 import BeautifulSoup as bs
import sys
from datetime import timedelta
from pytimeparse.timeparse import timeparse

from requests.auth import HTTPBasicAuth
from time import gmtime, mktime, sleep, strftime, strptime

from create_csv import create_csv

version = '1.0'

prev_run = 0       # Global - retain data between runs to avoid disk read
prev_boot = 0      # Global - retain data between runs to avoid disk read
prev_uptime = 0    # Global - retain data between runs to avoid disk read
running_data = {}  # Global - retain data between runs to avoid disk read
logger = logging.getLogger(__name__)


def ISO_time(epochtime):
    """  Essentially shorthand for datetime.isoformat() without having to
         import datetime or deal with the vagaries of datetime objects
         when they're otherwise unneeded.
    """
    # local_offset = -7 # MST
    # local_offset *= 3600
    return strftime('%Y-%m-%dT%H:%M:%SZ', gmtime(epochtime))
    # return strftime('%Y-%m-%dT%H:%M:%S%z', gmtime(epochtime + local_offset))


def fetch_stats(password, user='admin', datafile_name='modem_stats.json'):
    """ Function to call the modem and compare statistics to its current set.
        We can't just parse the HTML because for some unfathamable reason
        the data we need is in string arrays in the JavaScript functions.
     """

    global prev_run  # holds the previous run version of freqs
    global prev_boot
    global prev_uptime
    global running_data

    folder = create_csv(modem_model='CM1200v2',downstream_channels=31, upstream_channels=4)


    # A dictionary of dictionaries indexed by channel number of current
    # downstream channel data in form {'status':, 'modulation':, 'channel ID':,
    # 'Frequency':, 'Power':, 'SNR':, 'Correctable Codewords':, 'UnCorrectable Codewords':}
    channels = {}
    upchannels = {}

    # A dictionary of dictionaries indexed by frequecy of current downstream
    # data in form {'Channel ID':, 'Power':, 'SNR':, 'Correctable Codewords':,
    # 'UnCorrectable Codewords':}
    freqs = {}

    # get the page of data ( JavaScript) from the modem
    while(1):
        try:
            # I usually wouldn't hard code URLs, but they're hard coded in the
            # modem, so why not. The while loop is because if the modem is
            # rebooting the script aborts unless we "keep trying" until page.ok
            with requests.Session() as s:
                page = s.get('http://192.168.100.1/GenieLogin.asp')
                bs_content = bs(page.content, "html.parser")
                token = bs_content.find("input", {"name":"webToken"})["value"]
                login_data = {"loginUsername":user,"loginPassword":password,"login": 1, "webToken":token}
                res = s.post("http://192.168.100.1/goform/GenieLogin",login_data)
                page = s.get("http://192.168.100.1/DocsisStatus.asp")

        except Exception as e:
            logger.error('Error(s) trying to access modem URL')
            logger.error(e)
            sleep(10)
        if page.ok:
            break

    # scrape the page.content for the "interesting" downstream channel data
    bs_content = bs(page.content, 'html.parser')
    if bs_content is not None:

        # regex number finder compile
        num = re.compile(r"[-+]?[.]?[\d]+(?:,\d\d\d)*[\.]?\d*(?:[eE][-+]?\d+)?")

        downstream = bs_content.find("table", attrs={"id": 'dsTable'})
        # Get data from table
        downstream_data = [[cell.text for cell in row("td")] for row in downstream("tr")]
        if downstream is not None:
            downstream_data.pop(0) # remove column identifiers
            for row in downstream_data:
                # skip non-locked channels
                if row[1] == 'Not Locked':
                    continue
                channel_num = int(row[0])
                channels[channel_num] = {}
                channels[channel_num][
                    'Status'] = row[1]
                channels[channel_num][
                    'Modulation'] = row[2]
                channels[channel_num][
                    'Channel ID'] = int(row[3])
                channels[channel_num][
                    'Frequency [MHz]'] = float(num.findall(row[4])[0])/1e6
                channels[channel_num][
                    'Power [dBmV]'] = float(num.findall(row[5])[0])
                channels[channel_num][
                    'SNR [dB]'] = float(num.findall(row[6])[0])
                channels[channel_num][
                    'Unerrored Codewords'] = int(row[7])
                channels[channel_num][
                    'Correctable Codewords'] = int(row[8])
                channels[channel_num][
                    'UnCorrectable Codewords'] = int(row[9])
            logger.debug(f'Channels dict: {channels}')


        # place downstream power into csv with
        # frequency as the index
        
        



        # scrape page.content for upstream data
        upstream = bs_content.find("table", attrs={"id": 'usTable'})
        # Get data from table
        upstream_data = [[cell.text for cell in row("td")] for row in upstream("tr")]
        if upstream is not None:
            upstream_data.pop(0)
            for row in upstream_data:
                if row[1] == 'Not Locked':
                    continue
                upchannels_num = int(row[0])
                upchannels[upchannels_num] = {}
                upchannels[upchannels_num]['Status'] = row[1]
                upchannels[upchannels_num]['Modulation'] = row[2]
                upchannels[upchannels_num]['Channel ID'] = int(row[3])
                upchannels[upchannels_num]['Frequency [MHz]'] = float(num.findall(row[4])[0])/1e6
                upchannels[upchannels_num]['Power [dBmV]'] = float(num.findall(row[5])[0])
            logger.debug(f'Upchannels dict: {upchannels}')


        # scrape the page.content for the current modem uptime
        # system_time between </b> and \n</
        system_time = str(bs_content.find("td", attrs={"id": 'Current_systemtime'}))
        system_time = re.search(r'(?<=</b>)(.*)(?=\n</)', system_time)[0]
        
        # uptime between </b> and </f
        uptime = str(bs_content.find("td", attrs={"id": 'SystemUpTime'}))
        uptime = re.search(r'(?<=</b>)(.*)(?=</f)', uptime)[0]

        sys_time = int(mktime(strptime((system_time))))
        # Convert the "Uptime" to seconds since epoch
        uptime = timeparse(uptime)
        boot_time = sys_time - uptime
        logger.debug(f'SysTime::{ISO_time(sys_time)}  ' +
                     f'Uptime::{timedelta(seconds=uptime)}')
    else:
        logger.error(f'Web page contained bogus data: {page.content}')
        raise ValueError('Web page contained bogus time data.')

    # Downstream Power append to csv
    down_power_array = [ISO_time(sys_time)]
    down_snr_array = [ISO_time(sys_time)]
    down_corr_array = [ISO_time(sys_time)]
    down_uncorr_array = [ISO_time(sys_time)]
    up_power_array = [ISO_time(sys_time)]
    for channel in channels:
        down_power_array.append(channels[channel]['Power [dBmV]'])
        down_snr_array.append(channels[channel]['SNR [dB]'])
        down_corr_array.append(channels[channel]['Correctable Codewords'])
        down_uncorr_array.append(channels[channel]['UnCorrectable Codewords'])

    for channel in upchannels:
        up_power_array.append(upchannels[channel]['Power [dBmV]'])

    # Save the data to csv files
    os.chdir(folder)
    with open('down_power.csv', 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(down_power_array)
    with open('down_snr.csv', 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(down_snr_array)
    with open('down_corr.csv', 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(down_corr_array)
    with open('down_uncorr.csv', 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(down_uncorr_array)
    with open('up_power.csv', 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(up_power_array)
    os.chdir('..')


    # Create a frequency vs. channel number based structure
    # We won't need to save everything we have for the channel
    # and we'll do some checks while we walk the channels
    for chan_idx in channels:
        chan_dict = channels[chan_idx]
        chan_freq = chan_dict['Frequency [MHz]']
        freqs[chan_freq] = {}
        freqs[chan_freq]['Channel ID'] = chan_dict['Channel ID']
        freqs[chan_freq]['Power [dBmV]'] = chan_dict['Power [dBmV]']
        freqs[chan_freq]['SNR [dB]'] = chan_dict['SNR [dB]']
        freqs[chan_freq]['Unerrored Codewords'] = chan_dict['Unerrored Codewords']
        freqs[chan_freq]['Correctable Codewords'] = chan_dict['Correctable Codewords']
        freqs[chan_freq]['UnCorrectable Codewords'] = chan_dict['UnCorrectable Codewords']
        # Check if SNR outside range
        if chan_dict['SNR [dB]'] < 36.0:
            logger.warning(f'{ISO_time(sys_time)}: Channel {chan_freq} ' +
                           f'SNR too low: {chan_dict["SNR [dB]"]}')
        # Check if Power outside range
        if abs(chan_dict['Power [dBmV]']) > 7.0:
            logger.warning(f'{ISO_time(sys_time)}: Channel {chan_freq} ' +
                           f' Power too high: {chan_dict["Power [dBmV]"]}')
    logger.debug(f'Frequency dict: {freqs}')

    # prev_run is defined from the previous globals run then use it for
    # efficiency  otherwise, pull it from the data file, if no data file
    # then must be new installation
    if not prev_run:
        try:
            # Check to see if we have saved stats stored on disk
            with open(datafile_name) as f:
                (prev_run, running_data, prev_boot, prev_uptime) = json.load(f)
                logger.debug(f'Recovered Prev_run dict: {prev_run}')
                logger.debug(f'Recovered Running dict: {running_data}')
                logger.debug(f'Recovered Previous Boot: {prev_boot}')
                logger.debug(f'Recovered Previous Uptime: {prev_uptime}')
        except IOError:
            # Assume the file doesn't exist
            # initialize prev_run so the compares don't traceback
            prev_run = freqs
            prev_boot = boot_time
            prev_uptime = uptime
            logger.debug(
                'No existing prev_run. Setting prev_run to current data.')

    # Sometimes on critical modem errors boot_time moves back a few seconds
    # and there seems to be a few second "jitter" in the uptime.
    if boot_time > prev_boot + 60:
        # Error rates must have been reset to zero by a reboot,
        # so baseline every frequency as zero
        prev_run = freqs
        for channel in prev_run:
            prev_run[channel]['Correctable Codewords'] = 0
            prev_run[channel]['UnCorrectable Codewords'] = 0
        logger.info(f'Modem Rebooted at {ISO_time(boot_time)} ' +
                    f'Currently up {timedelta(seconds=uptime)}')
        logger.info(f'Previous boot at {ISO_time(prev_boot)} ' +
                    f'Last up {timedelta(seconds=prev_uptime)}')

    # see if we have any new errors to report/keep track of
    # If the modem sees enough critial errors it will reset without
    # "rebooting" so uptime looks good, even though all the counters
    # have reset.  This is hard to detect, but we do our best.
    new_data = {}
    for chan_freq in prev_run:
        if chan_freq in list(freqs.keys()):
            new_correctable = freqs[chan_freq][
                'Correctable Codewords'] - prev_run[chan_freq]['Correctable Codewords']
            new_uncorrectable = freqs[chan_freq][
                'UnCorrectable Codewords'] - prev_run[chan_freq]['UnCorrectable Codewords']
            # if any channel goes bad, reset them all and break out
            if new_correctable < 0 or new_uncorrectable < 0:
                logger.info(f'Channel: {chan_freq} Negative errors'
                            ' - resetting previous counters')
                for old_freq in prev_run:
                    prev_run[old_freq]['Correctable Codewords'] = 0
                    prev_run[old_freq]['UnCorrectable Codewords'] = 0
                break

    for chan_freq in prev_run:
        if chan_freq in list(freqs.keys()):
            new_correctable = freqs[chan_freq][
                'Correctable Codewords'] - prev_run[chan_freq]['Correctable Codewords']
            new_uncorrectable = freqs[chan_freq][
                'UnCorrectable Codewords'] - prev_run[chan_freq]['UnCorrectable Codewords']
            if (new_correctable or new_uncorrectable):
                new_data[chan_freq] = (new_correctable, new_uncorrectable)
        else:
            new_data[chan_freq] = (0, 0)
            logger.info(f'Channel: {chan_freq} no longer utiltized')
            logger.debug(f'Channel: {chan_freq} Freqs keys: ' +
                         f'{list(freqs.keys())}')

    for chan_freq in freqs:
        # Check for new frequencies (not in previous run) that have errors
        if chan_freq not in list(prev_run.keys()):
            new_correctable = freqs[chan_freq]['Correctable Codewords']
            new_uncorrectable = freqs[chan_freq]['UnCorrectable Codewords']
            if (new_correctable or new_uncorrectable):
                new_data[chan_freq] = (new_correctable, new_uncorrectable)

    if new_data:
        running_data[sys_time] = new_data
        logger.info(f'New errors at {ISO_time(sys_time)}: {new_data}')
    logger.debug(f'Running data now: {running_data}')

    prev_run = freqs
    prev_boot = boot_time
    prev_uptime = uptime
    with open(datafile_name, 'w') as f:
        json.dump((prev_run, running_data, boot_time, uptime), f)
    logger.debug(f'Data refreshed Boot Time ({boot_time}) ' +
                 f'{ISO_time(boot_time)}')
    logger.debug(f'Data refreshed Uptime ' +
                 f'({uptime}) {timedelta(seconds=uptime)}')
    logger.info(f'Data refreshed System Time ({sys_time}) ' +
                f'{ISO_time(sys_time)}')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=('A script to monitor the signal quality of a Netgear'
                     'CMXXXX cable modem'),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-q', '--quiet', action='store_true',
                        default=None, help='display only critical errors')
    parser.add_argument('-v', '--verbose', action='count', default=None,
                        help='optional multiple increases in logging')
    parser.add_argument('-V', '--version', action='version',
                        version=f'{parser.prog} {version}')
    parser.add_argument('-l', '--log',
                        help='optional log file (will be appended)')
    parser.add_argument('-d', '--datafile', help='file name of data store',
                        default='ModemData.json')
    parser.add_argument('-p', '--passfile',
                        help='specify file to read modem password from')
    args = parser.parse_args()

    # set up log destination and verbosity from the command line
    logger.setLevel(logging.DEBUG)
    # create formatter
    stamped_formatter = logging.Formatter(
        '%(asctime)s::%(levelname)s::%(name)s::%(message)s')
    unstamped_formatter = logging.Formatter(
        '%(levelname)s:%(name)s:%(message)s')
    if args.log:
        # set up a log file and stderr
        fh = logging.FileHandler(args.log)
        fh.setFormatter(stamped_formatter)
        ch = logging.StreamHandler()
        ch.setFormatter(unstamped_formatter)
        if not args.quiet:
            ch.setLevel(logging.WARNING)
        else:
            ch.setLevel(logging.CRITICAL)
        logger.addHandler(ch)
    elif args.quiet and args.verbose:
        parser.error('Can not have both verbose and quiet unless using a log' +
                     ' file (in which case the quiet applies to the console.)')
    else:
        # file handler is stderr
        fh = logging.StreamHandler()
        fh.setFormatter(unstamped_formatter)
    if args.quiet:
        fh.setLevel(logging.CRITICAL)
    if args.verbose is None:
        # default of error
        fh.setLevel(logging.ERROR)
    elif args.verbose == 1:
        # level up one to info
        fh.setLevel(logging.WARNING)
    elif args.verbose == 2:
        # go for our current max of debug
        fh.setLevel(logging.INFO)
    elif args.verbose >= 3:
        # go for our current max of debug
        fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)

    # Get the modem password
    if args.passfile:
        with open(args.passfile) as pf:
            modem_password = pf.readline().rstrip('\n')
            print(modem_password)
    else:
        # modem_password = getpass.getpass('Modem Password: ')
        modem_password = 'woodengate_0'
        print(modem_password)
    logger.debug(f"Password argument set to {modem_password}")

    while (1):
        try:
            print(f'{datetime.datetime.now()}: Checking modem data')
            fetch_stats(password=modem_password, datafile_name=args.datafile)
            print('done')
            sleep(15)
        except Exception as e:
            logger.critical(f'Exception: {e}')
