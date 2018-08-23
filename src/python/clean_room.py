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

import json


class Room:
    entered = []
    exited = []

    def __init__(self, name, room_data):
        self.name = name
        self.json_data = room_data
        if 'tests' in self.json_data:
            self.entry_log = self.json_data['tests']
        else:
            self.entry_log = {}
            self.json_data['tests'] = self.entry_log

    def as_json(self):
        return json.dumps(self.json_data, sort_keys=True, indent=4)

    def enter(self, name, date_s, git_sha):
        # add or update the entry for the given name
        self.entry_log[name] = {'name': name, 'entry_date': date_s, 'git_sha' : git_sha}
        self.entered.append(self.entry_log[name])

    def exit(self, name):
        if name in self.entry_log:
            self.exited.append(self.entry_log[name])
            del self.entry_log[name]
            return True
        else:
            return False

    def get_tests(self):
        list = []
        for t in self.entry_log:
            list.append(t)
        return list

    def num_tests(self):
        tests = self.json_data['tests']
        return len(tests)

    def has(self, test_name):
        return test_name in self.entry_log

    def get_data(self):
        return self.json_data

    def get_entered(self):
        return self.entered

    def get_exited(self):
        return self.exited

