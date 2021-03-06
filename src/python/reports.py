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
    w("""
        <link href="https://unpkg.com/tabulator-tables@4.0.5/dist/css/tabulator.min.css" rel="stylesheet">
        <script type="text/javascript" src="https://unpkg.com/tabulator-tables@4.0.5/dist/js/tabulator.min.js"></script>
    """)
    w('</head>')
    w('<body>')


def footer(w, config):
    w('<hr>')
    w('<br>')
    w('<ul>')
    w('<li><em>Source:</em> <a href="https://github.com/shalinmangar/clean-room">clean-room</a></li>')
    w('<li>Tests failure status determined using jenkins '
      'failure reports from <a href="http://fucit.org/solr-jenkins-reports/failure-report.html">'
      'Lucene/Solr Jenkins Test Failure Report</a></li>')
    w('<li>Tests are promoted to clean room if not failed for <em>%d days</em></li>'
      % config['promote_if_not_failed_days'])
    w('<li>Tests are demoted to detention on any failure in jenkins jobs: <em>%s</em></li>' % ','.join(config['jenkins_jobs']))
    w('</ul>')
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

    report_path = '%s/%s_report.html' % (reports_dir, config['name'].strip().replace(' ', '_'))
    f = open(report_path, 'w')
    w = f.write
    header(w, 'Lucene/Solr Clean Room Status: %s' % config['name'])
    w('<h1>Lucene/Solr Clean Room Status: %s</h1>\n' % config['name'])
    w('<br>')
    draw_graph(consolidated, w)
    w('<br>')
    write_room_tables(config, consolidated, w, reports_dir)
    w('<br>')
    w('<h3>Full logs</h3>')
    w('<ul>')
    for k in sorted(consolidated):
        data = consolidated[k]
        test_date = datetime.datetime.strptime(data['test_date'], '%Y-%m-%d %H-%M-%S')
        test_date_str = test_date.strftime('%Y.%m.%d.%H.%M.%S')
        w('<li>%s: <a href="../output/%s/output.txt">Logs</a>, '
          'Report: <a href="./%s/report.json">JSON</a></li>'
          % (test_date, data['time_stamp'], test_date_str))
    w('</ul>')
    footer(w, config)
    f.close()
    print('Report written to: %s' % report_path)


def write_room_tables(config, consolidated, w, reports_dir):
    last_test_date = sorted(consolidated).pop()
    last_test_date = datetime.datetime.strptime(last_test_date, '%Y-%m-%d %H-%M-%S')
    last_test_date_str = last_test_date.strftime('%Y.%m.%d.%H.%M.%S')
    w('<h3>Tests in clean room as on %s</h3>' % last_test_date)
    w('<div id="clean-room-table" style="width:70%"></div>')
    w('<br>')
    w('<br>')
    w('<h3>Tests in detention as on %s</h3>' % last_test_date)
    w('<div id="detention-table" style="width:70%"></div>')
    w('<script type="text/javascript">')
    w("""
        var cleanTable = new Tabulator("#clean-room-table", {
            height:"40%",
            layout:"fitData",
            columns:[
            {title:"Test name", field:"test", headerFilter:true},
            {title:"Entry Date", field:"entry_date", sorter:"date", headerFilter:true},
            {title:"Git SHA", field:"git_sha", headerFilter:true},
            {title:"Module", field:"module", headerFilter:true},
            ],
        });
        
        var cleanRoomData = [
        """)
    report = None
    with open(os.path.join(os.path.join(reports_dir, last_test_date_str), 'report.json')) as f:
        report = json.load(f)
    test_data = report['clean']['tests']
    for t in test_data:
        module = test_data[t]['module'] if 'module' in test_data[t] and test_data[t]['module'] is not None else ''
        idx = module.find(config['checkout'])
        if idx != -1:
            module = module[idx + len(config['checkout']) + 1:]
        w('{test:"%s", entry_date: "%s", git_sha: "%s", module: "%s"},\n' % (test_data[t]['name'], test_data[t]['entry_date'], test_data[t]['git_sha'], module))
    w("""
        ];
        
        cleanTable.setData(cleanRoomData);
        
        var detentionTable = new Tabulator("#detention-table", {
            height:"40%",
            layout:"fitData",
            columns:[
            {title:"Test name", field:"test", headerFilter:true},
            {title:"Entry Date", field:"entry_date", sorter:"date", headerFilter:true},
            {title:"Reproducible", field:"reproducible", headerFilter:true},
            {title:"Bad SHA", field:"git_sha", headerFilter:true},
            {title:"Good SHA", field:"good_sha", headerFilter:true},
            {title:"Module", field:"module", headerFilter:true},            
            ],
        });
        
        var detentionData = [
    """)
    test_data = report['detention']['tests']
    for t in test_data:
        test = test_data[t]
        module = test['module'] if 'module' in test and test['module'] is not None else ''
        idx = module.find(config['checkout'])
        if idx != -1:
            module = module[idx + len(config['checkout']) + 1:]
        reproducible = str(test['extra_info']['reproducible']) if 'extra_info' in test and 'reproducible' in test['extra_info'] else 'Unknown'
        good_sha = test['extra_info']['good_sha'] if 'extra_info' in test and 'good_sha' in test['extra_info'] and test['extra_info']['good_sha'] is not None else 'Unknown'
        w('{test:"%s", entry_date: "%s", git_sha: "%s", module: "%s", good_sha: "%s", reproducible: "%s"},\n'
          % (test['name'], test['entry_date'], test['git_sha'], module, good_sha, reproducible))
    w("""
        ];
        
        detentionTable.setData(detentionData);
    """)
    w('</script>')


def draw_graph(consolidated, w):
    w('<div id="chart_div_reliability"></div>')
    w('<br>')
    w('<br>')
    w('<div id="chart_div_clean_detention"></div>')
    w('<br>')
    w('<br>')
    w('<div id="chart_div_promote_demote"></div>')
    w('<br>')

    w('<script type="text/javascript">')
    w("""
          google.charts.load('current', {'packages':['line']});
      google.charts.setOnLoadCallback(drawChart);

    function drawChart() {
    
      var reliability_data = new google.visualization.DataTable();
      reliability_data.addColumn('datetime', 'Test Date');
      reliability_data.addColumn('number', 'Test Reliability');
      reliability_data.addRows([
      """)
    for k in sorted(consolidated):
        data = consolidated[k]
        test_date = datetime.datetime.strptime(data['test_date'], '%Y-%m-%d %H-%M-%S')
        # IMPORTANT: In Javascript months are 0-indexed and go upto 11
        w('[new Date(%d,%d,%d), %d],'
          % (test_date.year, test_date.month - 1, test_date.day, data['num_clean'] - data['num_detention']))
    w("""
      ]);
      
      var options_reliability = {
        chart: {
          title: 'Test Reliability',
          subtitle: 'Tests in clean room less tests in detention, by date'
        },
        width: 900,
        height: 500,
        hAxis: {
            format: 'M/d/yy',
            gridlines: {count: 15}
        },
        vAxis: {
            format: 'decimal'
        }
      };
      
      var formatter = new google.visualization.DateFormat({formatType: 'short'});
      formatter.format(reliability_data, 0);
      
      var chart_reliability = new google.charts.Line(document.getElementById('chart_div_reliability'));
      chart_reliability.draw(reliability_data, google.charts.Line.convertOptions(options_reliability));

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
      var options_clean_detention = {
        chart: {
          title: 'Number of tests in clean room and detention',
          subtitle: 'by date'
        },
        width: 900,
        height: 500,
        hAxis: {
            format: 'M/d/yy',
            gridlines: {count: 15}
        },
        vAxis: {
            format: 'decimal'
        }
      };
            
      formatter.format(clean_detention_data, 0);

      var chart_clean_detention = new google.charts.Line(document.getElementById('chart_div_clean_detention'));
      chart_clean_detention.draw(clean_detention_data, google.charts.Line.convertOptions(options_clean_detention));
      
      var promote_demote_data = new google.visualization.DataTable();
      promote_demote_data.addColumn('datetime', 'Test Date');
      promote_demote_data.addColumn('number', 'Promotions to clean room');
      promote_demote_data.addColumn('number', 'Demotions to detention');
      
      promote_demote_data.addRows([
      """)
    for k in sorted(consolidated):
        data = consolidated[k]
        test_date = datetime.datetime.strptime(data['test_date'], '%Y-%m-%d %H-%M-%S')
        # IMPORTANT: In Javascript months are 0-indexed and go upto 11
        w('[new Date(%d,%d,%d), %d, %d],'
          % (test_date.year, test_date.month - 1, test_date.day, data['num_promotions'], data['num_demotions']))

    w("""
      ]);
      var options_promote_demote = {
        chart: {
          title: 'Number of tests promoted/demoted',
          subtitle: 'by date'
        },
        width: 900,
        height: 500,
        hAxis: {
            format: 'M/d/yy',
            gridlines: {count: 15}
        },
        vAxis: {
            format: 'decimal'
        }
      };
      var chart_promote_demote = new google.charts.Line(document.getElementById('chart_div_promote_demote'));
      chart_promote_demote.draw(promote_demote_data, google.charts.Line.convertOptions(options_promote_demote));
      
    }
    """)
    w('</script>')


if __name__ == '__main__':
    main()
