#!/bin/python

import datetime
import sys
import os
import logging
import json

import bootstrap
import jenkins_clean_room


def main():
    start = datetime.datetime.now()
    time_stamp = '%04d.%02d.%02d.%02d.%02d.%02d' % (
        start.year, start.month, start.day, start.hour, start.minute, start.second)

    start_date = datetime.datetime.now()
    end_date = start_date
    interval_days = 7

    date_format = '%Y.%m.%d.%H.%M.%S'
    if '-start-date' in sys.argv:
        index = sys.argv.index('-start-date')
        start_date_s = sys.argv[index + 1]
        start_date = datetime.datetime.strptime(start_date_s, date_format)

    if '-end-date' in sys.argv:
        index = sys.argv.index('-end-date')
        end_date_s = sys.argv[index + 1]
        end_date = datetime.datetime.strptime(end_date_s, date_format)

    if '-interval-days' in sys.argv:
        index = sys.argv.index('-interval-days')
        interval_days = int(sys.argv[index + 1])

    delta_days = datetime.timedelta(days=interval_days)
    config = bootstrap.get_config()

    # setup output directory
    output_dir = config['output']
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    level = logging.INFO
    if '-debug' in sys.argv:
        level = logging.DEBUG

    bootstrap.setup_logging(output_dir, time_stamp, level)

    back_test_path = os.path.join(output_dir, 'jenkins_back_test.json')
    if not os.path.exists(back_test_path):
        dates = []
        st = start_date
        while st < end_date:
            st = st + delta_days
            if st < end_date:
                dates.append(st.strftime(date_format))
        with open(back_test_path, 'w') as f:
            json.dump(dates, f)

    with open(back_test_path, 'r') as f:
        dates = json.load(f)

    test_date = None
    if len(dates) == 0:
        logging.info('No dates left to back test')
        exit(0)
    else:
        logging.info('Back testing %d dates: %s' % (len(dates), dates))
        test_date = datetime.datetime.strptime(dates[0], date_format)

    logging.info('Selected date %s' % test_date)
    jenkins_clean_room.do_work(test_date, config)
    dates.remove(test_date.strftime(date_format))
    with open(back_test_path, 'w') as f:
        json.dump(dates, f)


if __name__ == '__main__':
    main()
