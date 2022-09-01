import csv
import os


def create_csv(modem_model: str, downstream_channels: int, upstream_channels: int):
    '''Create csv files for long term plotting of data'''
    # if a folder does not exist create a folder with the modem name
    if not os.path.exists(modem_model):
        os.makedirs(modem_model)
    os.chdir(modem_model)

    # create the csv headers with a date and channel number
    downstream_header = ['Date']
    upstream_header = downstream_header.copy()
    for i in range(downstream_channels):
        downstream_header.append('ch' + str(i+1))
    for i in range(upstream_channels):
        upstream_header.append('ch' + str(i+1))

    # if files do not exist create csv files for downstream power, snr, error rates
    # upstream power and error rates
    downstream_files = ['down_power.csv', 'down_snr.csv', 'down_corr.csv', 'down_uncorr.csv']
    upstream_files = ['up_power.csv']
    for file in downstream_files:
        if not os.path.isfile(file):
            with open(file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(downstream_header)
    for file in upstream_files:
        if not os.path.isfile(file):
            with open(file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(upstream_header)

    os.chdir('..')
    return modem_model


if __name__ == '__main__':
    create_csv(modem_model='CM1200v2',downstream_channels=31, upstream_channels=4)
