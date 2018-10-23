# clean-room

Clean room environment for Solr tests

## Goals

* Avoid false negative test failures
* Assign blame for failing test

## Preamble

Solr tests have a reliability problem. Some tests are flaky i.e. sometimes they fail in non-reproducible ways. This
sort of failure may be a false negative or may indicate a real problem. Finding out which failure is which is not easy
without spending considerable amount of time. Add to that, the sheer amount of such failures causes developers to drown
in the noise and ignore useful signals. When tests fail non-reproducibly, developers may ignore such failures believing
them to be irrelevant to their changes. Over time more and more tests become flaky. This is a vicious cycle.

Lucene/Solr has multiple Continuous Integration (CI) environments (generously contributed by various individuals and organizations)
and there is an aggregated Jenkins failure report that provides daily data on test failures for each jenkins jobs. We can
combine this data with focused automated testing and git bisection to provide:

* A definitive answer on which tests were not flaky earlier but have become flaky now and vice-versa
* An indication on which commit introduced a test failure (whether flaky or not)

A filtering process classifies tests into two rooms (categories) viz. clean room and detention.

### Clean room

A tests that has not failed for N days is sent to the clean room where it will remain until it fails on a CI 
environment or on local testing. All newly added tests are automatically sent to the clean room.

In essence, the clean room holds known-good tests that do not have a history of failing. Therefore, if and when a test
exits the clean room i.e. `demoted` to detention, it is a serious issue that warrants investigation.

### Detention

A test is demoted to the detention if it fails even once, either on CI environment or on local testing. A test will 
exit detention i.e. will be `promoted` to the clean room when it sees no failures (on CI environments) in the past N days 
and can pass all filters.

Therefore, tests in detention are either known-bad (they fail reproducibly or fail often enough that they were 
marked by `@BadApple` or `@AwaitsFix` annotations by developers) or generally unreliable enough that no conclusions 
can be drawn from their failures.

## How it works

* This projects tests and tracks failures only at the test suite level i.e. failure of single test method will send the entire suite to detention
* A test suite that can pass all filters can enter the clean room
* All test suites inside the clean room are run through filters nightly
* Tests that fail any filter exit the clean room and enter detention
* Detention job runs periodically filtering all test suites in detention and promotes to clean room if they pass
* A test suite exiting the clean room is definitely broken by a commit in the last 24 hours so we `git bisect` to assign blame
* A dashboard shows test suites in the clean room, in detention and blame information

## Filters

Any test wishing to enter the clean room must pass all filters

* `simple`: Coarse grained filter. Runs a test once and allows through if the test run is successful.
* `beast`: Beast a test 60 (10 times x 6 JVMs) times and allows if beasting is successful

Multiple filters are executed in this order so that the most expensive filters are run the last

## Running

### Bootstrap process

The bootstrap process will run any test, not in clean room or detention already, through all filters. If it passes, 
the test is promoted to clean room, else sent to detention. You can expect the bootstrap to take a long time on the 
first run when all tests have to be run through filters. Subsequent runs will only operate on new tests, if any, so
should take significantly lesser time.

```bash
python src/python/bootstrap.py -config /path/to/config.json [-revision <commit>] [-clean-build] [-build-artifacts] 
```

Parameters:
1. `-config /path/to/config.json`: Path to the configuration file (required)
1. `-revision [commit]`: the git SHA to be used for bootstrap (optional, defaults to HEAD on master branch)
1. `-clean-build`: If specified, the entire checkout directory, Ivy cache and ant lib directories will be deleted before checkout (optional)
1. `-build-artifacts`: If specified, `ant package` is also executed in the `solr` directory to build tgz and zip artifacts (optional)

At this time, the bootstrap script should be considered work in progress.

### Jenkins Clean Room

This script will download the jenkins failure report for the given date, and place tests in either clean room or detention
depending on the failed tests in the reports. The downloaded jenkins failure report is placed in `$output_dir/jenkins-archive`

```bash
python src/python/jenkins_clean_room.py -config /path/to/config.json [-test-date <%Y.%m.%d.%H.%M.%S>] [-debug] [-fail-report-path /path/to/jenkins/failure/report.csv.gz] [-clean-build] [-revision]
``` 

Parameters:
1. `-config /path/to/config.json`: Path to the configuration file (required)
1. `-test-date <%Y.%m.%d.%H.%M.%S>`: The test-date for which the jenkins failure reports are to be processed. (optional, defaults to yesterday i.e. NOW-1DAY)
1. `-revision [commit]`: the git SHA to be used for processing (optional, defaults to the last commit as on `-test-date` on the master branch)
1. `-clean-build`: If specified, the entire checkout directory, Ivy cache and ant lib directories will be deleted before checkout (optional)
1. `-debug`: If specified, debug level logging is enabled (optional)
1. `-fail-report-path /path/to/jenkins/failure/report.csv.gz`: If specified then the given failure report is used to classify tests (optional)
1. `-skip-filters`: If specified, filters are not run when promoting a test to clean room

Output:
1. `$output_dir/current_date/output.txt` -- the full path will be printed at the end of the execution.
1. `$output_dir/clean_room_data.json` and `$output_dir/detention_room_data.json` will contain the tests in each along with their entry date and the commit SHA on which they were promoted/demoted.
1. `$report_dir/test_data/report.json` will also be generated with the snapshot of the state as on the given test_date including lists of new tests, tests in each room, details of promotion and detention along with basic stats.

### Jenkins back test

The back testing script can invoke the jenkins clean room script repeatedly for each date within the given range. This allows us
to quickly build up historical data for further testing.

```bash
python src/python/jenkins_back_test.py -config /path/to/config.json -start-date <%Y.%m.%d.%H.%M.%S> -end-date -start-date <%Y.%m.%d.%H.%M.%S> [-interval-days <number_of_days>] [-debug]
``` 

Parameters:
1. `-config /path/to/config.json`: Path to the configuration file (required)
1. `-start-date <%Y.%m.%d.%H.%M.%S>`: The start test-date from which the jenkins failure reports are to be processed. (required)
1. `-end-date <%Y.%m.%d.%H.%M.%S>`: The end test-date till which the jenkins failure reports are to be processed. (required)
1. `-interval-days number_of_days`: The number of days to skip from the previous test date to select the next test date (optional, defaults to 7)
1. `-debug`: If specified, debug level logging is enabled (optional)

Any extra parameters are passed as-is to the Jenkins clean room script.

### Reports

The report script will generate a `consolidated.json` by going over the `report.json` generated for each test date.

```bash
python src/python/reports.py -config /path/to/config.json
```

Parameters:
1. `-config /path/to/config.json`: Path to the configuration file (required)

Output:
1. `$report_dir/consolidated.json`: Contains aggregated information over all test dates
2. `$report_dir/[name]_report.html`: HTML with graphs of test reliability by date, number of tests in each room and promotions/demotions. The `[name]` refers to the name in the given configuration file. 

### Blame

The blame script tries to find the commit responsible for a single demotion. It uses `git log` and `git bisect` to find the offending commit.

```bash
python src/python/blame.py -config /path/to/config.json -test <Test_Name> -good-sha <commit> -bad-sha <commit> [-test-date <%Y.%m.%d.%H.%M.%S>] [-new-test] [-debug]
```

Parameters:
1. `-config /path/to/config.json`: Path to the configuration file (required)
1. `-test <Test_Name>`: The name of the test which we need to investigate (required)
1. `-good-sha <commit>`: The known good commit_sha. This is usually the entry date of this test in the clean room before eviction. (required)
1. `-bad-sha <commit>`: The known bad commit_sha. This is usually the entry date of this test in the detention room. (required)
1. `-test-date <%Y.%m.%d.%H.%M.%S>`: The test date which caused the demotion. (optional)
1. `-new-test`: If specified, the test is assumed to be a new one and therefore we use git log to find the commit that introduced the test instead of running a git bisect. (optional)
1. `-debug`: If specified, debug level logging is enabled (optional)

Output:
1. Information about the offending commit including its commit SHA, author and commit message.

### Bisect

This script is given to `git bisect run` to find whether a commit is good or bad. It returns the appropriate exit codes
so that git can decide whether to mark a commit as good or bad or to skip it entirely.

```bash
python src/python/bisect.py -config /path/to/config.json -test [Test_Name]
```
Parameters:
1. `-config /path/to/config.json`: Path to the configuration file (required)
1. `-test <Test_Name>`: The name of the test which we need to investigate (required)

## Configuration

Configuration is provided in a JSON file whose path is passed as a command line argument to the python script. Here's an example for Solr:

```json
{
  "name" : "solr",
  "repo" : "https://github.com/apache/lucene-solr.git",
  "branch" : "master",
  "checkout" : "/solr-clean-room/checkout",
  "output" : "/solr-clean-room/output",
  "report" : "/solr-clean-room/report",
  "include" : "*/org/apache/solr/cloud/*/*Test.java|*/org/apache/solr/cloud/*/Test*.java",
  "exclude" : "*/org/apache/solr/cloud/cdcr/*",
  "tests_jvms" : 6,
  "filters" : [
    {
      "name" : "simple",
      "test" : "${ant} test -Dtestcase=${test_name} -Dtests.nightly=false -Dtests.badapples=false -Dtests.awaitsfix=false"
    },
    {
      "name": "beast",
      "test" : "${ant} beast -Dbeast.iters=10 -Dtests.jvms=${tests_jvms} -Dtestcase=${test_name} -Dtests.nightly=false -Dtests.badapples=false -Dtests.awaitsfix=false"
    }
  ]
}
```

Some additional configuration is in a `constants.py` file:
```python
ANT_EXE = 'ant'
GIT_EXE = '/usr/bin/git'
ANT_LIB_DIR = '/home/user/.ant/lib'
IVY_LIB_CACHE = '/home/user/.ivy2/cache'
```