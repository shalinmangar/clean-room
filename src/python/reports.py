#!/bin/python

# Copyright 2018 Shalin Shekhar Mangar
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import json
import datetime

import bootstrap


def html_escape(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def header(w, title):
    w('<html>')
    w('<head>')
    w('<title>%s</title>' % html_escape(title))
    w('<style type="text/css">')
    w('BODY { font-family:verdana; }')
    w('</style>')
    w('<script src="https://www.gstatic.com/charts/loader.js"></script>\n')
    w('</head>')
    w('<body>')


def footer(w):
    w('<br>')
    w(
        '<br><em>[last updated: %s; send questions to <a href="mailto:shalin@apache.org">Shalin Shekhar Mangar</a>]</em>' % datetime.datetime.now())
    w('</body>')
    w('</html>')


def main():
    config = bootstrap.get_config()
    reports_dir = config['report']
    if not os.path.exists(reports_dir):
        print('Nothing to report')
        exit(1)

    reports = []
    for root, dirs, files in os.walk(reports_dir):
        if 'report.json' in files:
            reports.append(os.path.join(root, 'report.json'))

    consolidated = {}
    for r in reports:
        with open(r, 'r') as f:
            data = json.load(f)
            consolidated[data['test_date']] = {
                'test_date': data['test_date'],
                'num_promotions': data['num_promotions'],
                'num_demotions': data['num_demotions'],
                'delta_promote_demote': data['num_promotions'] - data['num_demotions'],
                'num_clean': data['num_clean'],
                'num_detention': data['num_detention'],
                'delta_clean_detention': data['num_clean'] - data['num_detention'],
                'time_stamp': data['time_stamp']
            }
    with open(os.path.join(reports_dir, 'consolidated.json'), 'w') as f:
        json.dump(consolidated, f, indent=8, sort_keys=True)

    f = open('%s/report.html' % reports_dir, 'w')
    w = f.write
    header(w, 'Solr clean room')
    w('<h1>Solr clean room status</h1>\n')
    w('<br>')
    draw_graph(consolidated, w)
    footer(w)
    f.close()


def draw_graph(consolidated, w):
    w('<div id="chart_div_clean_detention"></div>')
    w('<br>')
    w('<br>')
    w('<div id="chart_div_promote_demote"></div>')

    w('<script type="text/javascript">')
    w("""
          google.charts.load('current', {'packages':['line']});
      google.charts.setOnLoadCallback(drawChart);

    function drawChart() {

      var clean_detention_data = new google.visualization.DataTable();
      clean_detention_data.addColumn('datetime', 'Test Date');
      clean_detention_data.addColumn('number', 'Clean Room');
      clean_detention_data.addColumn('number', 'Detention');
      """)
    w('clean_detention_data.addRows([')
    for k in sorted(consolidated):
        data = consolidated[k]
        test_date = datetime.datetime.strptime(data['test_date'], '%Y-%m-%d %H-%M-%S')
        # IMPORTANT: In Javascript months are 0-indexed and go upto 11
        w('[new Date(%d,%d,%d), %d, %d],'
          % (test_date.year, test_date.month - 1, test_date.day, data['num_clean'], data['num_detention']))
    w('  ]);')
    w("""
      var options = {
        chart: {
          title: 'Number of tests in clean room and detention',
          subtitle: 'by date'
        },
        width: 900,
        height: 500,
        hAxis: {
            format: 'M/d/yy',
            gridlines: {count: 15}
        }
      };
      
      var formatter = new google.visualization.DateFormat({formatType: 'short'});
      formatter.format(clean_detention_data, 0);

      var chart = new google.charts.Line(document.getElementById('chart_div_clean_detention'));
      chart.draw(clean_detention_data, google.charts.Line.convertOptions(options));
      
      
    }
    """)
    w('</script>')


if __name__ == '__main__':
    main()
