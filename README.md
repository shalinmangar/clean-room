# clean-room

Clean room environment for Solr tests

## Goals

* Avoid false negative test failures
* Assign blame for failing test

## How it works

* Clean room only operates at the test suite level
* A test suite that can pass all filters can enter the clean room
* All test suites inside the clean room are run through filters nightly
* Tests that fail any filter exit the clean room and enter detention
* Detention job runs periodically filtering all test suites in detention and promotes to clean room if they pass
* A test suite exiting the clean room is definitely broken by a commit in the last 24 hours so we `git bisect` to assign blame
* A dashboard shows test suites in the clean room, in detention and blame information

## Filters

Any test wishing to enter the clean room must pass all filters

* `Scrubber`: Coarse grained filter. Runs a test once and allows through if the test run is successful.
* `Shower`: Beast a test 10 times and allows if beasting is successful
* `Air filter`: Beast a test 100 times and allows if beasting is successful

Multiple filters are executed in this order so that the most expensive filters are run the last

## Bootstrap process

* Run any test, not in clean room or detention already, through all filters. If it passes, promote to clean room, else send to detention

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
      "name" : "scrubber",
      "test" : "${ant} test-nocompile -Dtestcase=${test_name}"
    },
    {
      "name": "shower",
      "test" : "${ant} beast -Dbeast.iters=10 -Dtests.jvms=${tests_jvms} -Dtests.dups=2 -Dtestcase=${test_name}"
    },
    {
      "name" : "air_filter",
      "test" : "${ant} beast -Dbeast.iters=100 -Dtests.jvms=${tests_jvms} -Dtests.dups=4 -Dtestcase=${test_name}"
    }
  ]
}
``` 