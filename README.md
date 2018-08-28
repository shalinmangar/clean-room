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
      "name" : "simple",
      "test" : "${ant} test-nocompile -Dtestcase=${test_name} -Dtests.nightly=false -Dtests.badapples=false -Dtests.awaitsfix=false"
    },
    {
      "name": "beast",
      "test" : "${ant} beast -Dbeast.iters=10 -Dtests.jvms=${tests_jvms} -Dtestcase=${test_name} -Dtests.nightly=false -Dtests.badapples=false -Dtests.awaitsfix=false"
    }
  ]
}
``` 